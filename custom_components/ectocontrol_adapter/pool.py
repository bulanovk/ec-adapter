"""Modbus client connection pool for sharing connections across config entries.

Design follows the HA Modbus integration's approach:
- ``asyncio.Lock`` serialises operations (no background queue task).
- No ``ensure_connected()`` before every operation — pymodbus's built-in
  ``TransactionManager.execute()`` tries to reconnect if ``transport`` is None.
- Background reconnect is handled by pymodbus (``reconnect_delay`` on
  ``CommParams``) — the pool never forces a synchronous reconnect.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Tuple, Union

from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient, AsyncModbusUdpClient

from .helpers import create_modbus_client

_LOGGER = logging.getLogger(__name__)

POOL_KEY = "pool"

# Type alias for Modbus async clients
ModbusAsyncClient = Union[AsyncModbusTcpClient, AsyncModbusUdpClient, AsyncModbusSerialClient]


def _get_pool_key(config: Dict[str, Any]) -> str:
    """Generate a unique key for connection pooling based on connection config."""
    from .const import (
        OPT_BAUDRATE,
        OPT_BYTESIZE,
        OPT_DEVICE,
        OPT_HOST,
        OPT_MODBUS_TYPE,
        OPT_PARITY,
        OPT_PORT,
        OPT_STOPBITS,
    )

    modbus_type = config.get(OPT_MODBUS_TYPE, "")

    if modbus_type == "serial":
        return (
            f"serial:{config.get(OPT_DEVICE)}:{config.get(OPT_BAUDRATE)}:"
            f"{config.get(OPT_PARITY)}:{config.get(OPT_STOPBITS)}:{config.get(OPT_BYTESIZE)}"
        )
    elif modbus_type in ("tcp", "udp", "rtuovertcp"):
        return f"{modbus_type}:{config.get(OPT_HOST)}:{config.get(OPT_PORT)}"
    else:
        return f"unknown:{id(config)}"


class PooledClient:
    """A pooled Modbus client with reference counting and serialised access.

    Follows the HA Modbus ``ModbusHub`` pattern: a single ``asyncio.Lock``
    gates all operations so that only one Modbus transaction is in-flight at
    any time.  There is **no** background queue-processing task — callers
    await the lock directly in ``submit_operation``.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the pooled client.

        Args:
            config: Connection configuration dictionary.
        """
        self._config = config
        self._client: Optional[ModbusAsyncClient] = None
        self._ref_count = 0
        self._lock = asyncio.Lock()

    # -- reference counting ---------------------------------------------------

    async def acquire(self) -> bool:
        """Acquire a reference.  Connects on first reference."""
        self._ref_count += 1
        _LOGGER.debug("PooledClient acquired, ref_count=%d", self._ref_count)

        if self._ref_count == 1:
            await self._connect()

        return self._client is not None and self._client.connected

    async def release(self):
        """Release a reference.  Disconnects on last reference."""
        if self._ref_count > 0:
            self._ref_count -= 1
            _LOGGER.debug("PooledClient released, ref_count=%d", self._ref_count)

        if self._ref_count == 0:
            if self._client:
                self._client.close()
                self._client = None
            _LOGGER.debug("PooledClient stopped (no more references)")

    # -- connection -----------------------------------------------------------

    def _install_diag_hooks(self) -> None:
        """Monkey-patch TransactionManager with sub-millisecond timing diag."""
        if self._client is None:
            return
        ctx = self._client.ctx  # TransactionManager
        _orig_execute = ctx.execute
        _orig_callback_data = ctx.callback_data
        _orig_send = ctx.send
        _orig_connect = ctx.connect

        async def _diag_execute(no_response_expected, request):
            t_entry = time.monotonic()
            try:
                return await _orig_execute(no_response_expected, request)
            finally:
                elapsed = time.monotonic() - t_entry
                _LOGGER.debug(
                    "⏱️ PYLIB.execute dev=%s fc=%s tid=%s → %.3fs",
                    request.dev_id,
                    request.function_code,
                    request.transaction_id,
                    elapsed,
                )

        def _diag_callback_data(data, addr=None):
            t0 = time.monotonic()
            cut = _orig_callback_data(data, addr)
            elapsed = time.monotonic() - t0
            pdu = ctx.last_pdu
            _LOGGER.debug(
                "⏱️ PYLIB.callback_data len=%d cut=%d pdu=%s → %.3fs",
                len(data),
                cut,
                pdu.__class__.__name__ if pdu else "None",
                elapsed,
            )
            return cut

        def _diag_send(data, addr=None):
            t0 = time.monotonic()
            result = _orig_send(data, addr)
            elapsed = time.monotonic() - t0
            _LOGGER.debug("⏱️ PYLIB.send len=%d → %.3fs", len(data), elapsed)
            return result

        async def _diag_connect():
            t0 = time.monotonic()
            result = await _orig_connect()
            elapsed = time.monotonic() - t0
            _LOGGER.debug("⏱️ PYLIB.connect → %.3fs (success=%s)", elapsed, result)
            return result

        ctx.execute = _diag_execute  # type: ignore[method-assign]
        ctx.callback_data = _diag_callback_data  # type: ignore[method-assign]
        ctx.send = _diag_send  # type: ignore[method-assign]
        ctx.connect = _diag_connect  # type: ignore[method-assign]

    async def _connect(self):
        """Create client and connect (one-shot, no retry loop)."""
        if self._client:
            self._client.close()
            self._client = None

        try:
            self._client = create_modbus_client(self._config)
            self._install_diag_hooks()
            result = await self._client.connect()
            if not result:
                _LOGGER.error("Failed to connect to Modbus device")
            else:
                _LOGGER.info("PooledClient connected successfully")
        except Exception as e:
            _LOGGER.error("Error connecting to Modbus: %s", e)

    # -- operations -----------------------------------------------------------

    async def submit_operation(self, op: str, data: Dict[str, Any]) -> Any:
        """Execute a Modbus operation under the shared lock.

        Follows HA Modbus ``async_pb_call``: acquire lock → (optional wait)
        → call pymodbus directly.  No explicit ``ensure_connected`` —
        pymodbus's ``TransactionManager.execute()`` handles reconnection
        internally when ``transport`` is None.
        """
        async with self._lock:
            return await self._execute_client_operation(op, data)

    async def _execute_client_operation(self, op: str, data: Dict[str, Any]) -> Any:
        """Dispatch to the underlying pymodbus client."""
        if self._client is None:
            raise RuntimeError("Modbus client not initialized")

        dev_id = data.get("device_id", "?")
        addr = data.get("address", "?")
        t0 = time.monotonic()

        try:
            if op == "read_holding_registers":
                result = await self._client.read_holding_registers(
                    address=data["address"], count=data["count"], device_id=data["device_id"]
                )
            elif op == "read_input_registers":
                result = await self._client.read_input_registers(
                    address=data["address"], count=data["count"], device_id=data["device_id"]
                )
            elif op == "write_registers":
                result = await self._client.write_registers(
                    address=data["address"], values=data["values"], device_id=data["device_id"]
                )
            else:
                raise ValueError(f"Unknown operation type: {op}")
        finally:
            elapsed = time.monotonic() - t0
            _LOGGER.debug(
                "⏱️ TIMING op=%s addr=0x%04X dev=%s → %.3fs",
                op,
                addr,
                dev_id,
                elapsed,
            )

        return result

    @property
    def ref_count(self) -> int:
        """Current reference count."""
        return self._ref_count

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._client is not None and self._client.connected


class ModbusClientPool:
    """Pool of shared Modbus clients keyed by connection configuration."""

    def __init__(self):
        """Initialize the client pool."""
        self._pools: Dict[str, PooledClient] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, config: Dict[str, Any]) -> Tuple[str, PooledClient]:
        """
        Acquire a pooled client for the given configuration.

        Returns:
            Tuple of (pool_key, pooled_client)
        """
        pool_key = _get_pool_key(config)

        async with self._lock:
            if pool_key not in self._pools:
                _LOGGER.info("Creating new PooledClient for key: %s", pool_key)
                self._pools[pool_key] = PooledClient(config)

            pooled_client = self._pools[pool_key]
            await pooled_client.acquire()

        return pool_key, pooled_client

    async def release(self, pool_key: str):
        """Release a reference to a pooled client."""
        async with self._lock:
            if pool_key in self._pools:
                pooled_client = self._pools[pool_key]
                await pooled_client.release()

                if pooled_client.ref_count == 0:
                    _LOGGER.info("Removing PooledClient for key: %s", pool_key)
                    del self._pools[pool_key]

    def get(self, pool_key: str) -> Optional[PooledClient]:
        """Get a pooled client by key without acquiring."""
        return self._pools.get(pool_key)

    async def close_all(self):
        """Close all pooled clients."""
        async with self._lock:
            for pool_key, pooled_client in list(self._pools.items()):
                _LOGGER.info("Closing PooledClient for key: %s", pool_key)
                await pooled_client.release()
            self._pools.clear()
