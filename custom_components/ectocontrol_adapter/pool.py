"""Modbus client connection pool for sharing connections across config entries."""

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

from .const import QUEUE_TIMEOUT
from .helpers import create_modbus_client

_LOGGER = logging.getLogger(__name__)

POOL_KEY = "pool"


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
    """A pooled Modbus client with reference counting and operation queue."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the pooled client.

        Args:
            config: Connection configuration dictionary.
        """
        self._config = config
        self._client = None
        self._ref_count = 0
        self._queue = asyncio.Queue()
        self._processing_task = None
        self._is_running = False
        self._operation_lock = asyncio.Lock()
        self._current_operation = None

    async def acquire(self) -> bool:
        """Acquire a reference to this client. Starts processing if first ref."""
        self._ref_count += 1
        _LOGGER.debug("PooledClient acquired, ref_count=%d", self._ref_count)

        if self._ref_count == 1:
            # First reference - start processing and connect
            self._is_running = True
            self._processing_task = asyncio.create_task(self._process_queue())
            await self._connect()

        return self._client is not None and self._client.connected

    async def release(self):
        """Release a reference. Stops processing and disconnects if last ref."""
        if self._ref_count > 0:
            self._ref_count -= 1
            _LOGGER.debug("PooledClient released, ref_count=%d", self._ref_count)

        if self._ref_count == 0:
            # Last reference - stop processing and disconnect
            self._is_running = False
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass
                self._processing_task = None

            if self._client:
                self._client.close()
                self._client = None
            _LOGGER.debug("PooledClient stopped (no more references)")

    async def _connect(self):
        """Connect to Modbus device."""
        if self._client:
            self._client.close()
            self._client = None

        try:
            self._client = create_modbus_client(self._config)
            result = await self._client.connect()
            if not result:
                _LOGGER.error("Failed to connect to Modbus device")
            else:
                _LOGGER.info("PooledClient connected successfully")
        except Exception as e:
            _LOGGER.error("Error connecting to Modbus: %s", e)

    async def ensure_connected(self) -> bool:
        """Ensure client is connected, reconnecting if necessary."""
        if self._client and self._client.connected:
            return True

        await self._connect()
        return self._client is not None and self._client.connected

    async def _process_queue(self):
        """Process queued Modbus commands."""
        while self._is_running:
            try:
                operation_id, operation_type, operation_data, future = await asyncio.wait_for(
                    self._queue.get(), timeout=QUEUE_TIMEOUT
                )

                async with self._operation_lock:
                    self._current_operation = operation_id
                    try:
                        result = await self._execute_operation(operation_type, operation_data)
                        if not future.done():
                            future.set_result(result)
                    except Exception as e:
                        if not future.done():
                            future.set_exception(e)
                        _LOGGER.error("Operation %s failed: %s", operation_id, e)
                    finally:
                        self._current_operation = None
                        self._queue.task_done()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error("Unexpected error in queue processing: %s", e)

    async def _execute_operation(self, op: str, data: Dict[str, Any]) -> Any:
        """Execute a Modbus operation."""
        if not await self.ensure_connected():
            raise Exception("Modbus device not connected")

        return await self._execute_client_operation(op, data)

    async def _execute_client_operation(self, op: str, data: Dict[str, Any]) -> Any:
        """Execute operation on the client."""
        if op == "read_holding_registers":
            return await self._client.read_holding_registers(
                address=data["address"], count=data["count"], device_id=data["device_id"]
            )
        elif op == "read_input_registers":
            return await self._client.read_input_registers(
                address=data["address"], count=data["count"], device_id=data["device_id"]
            )
        elif op == "write_registers":
            return await self._client.write_registers(
                address=data["address"], values=data["values"], device_id=data["device_id"]
            )
        else:
            raise ValueError(f"Unknown operation type: {op}")

    async def submit_operation(self, op: str, data: Dict[str, Any]) -> Any:
        """Submit an operation to the queue and wait for result."""
        if not self._is_running:
            raise RuntimeError("PooledClient is not running")

        operation_id = f"{op}_{id(data)}"
        future = asyncio.Future()

        await self._queue.put((operation_id, op, data, future))
        return await future

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
