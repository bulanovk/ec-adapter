# ectoControl Adapter Documentation

## Documents

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, component design, data flow diagrams |
| [PROTOCOL.md](PROTOCOL.md) | Modbus protocol definition, register maps, communication specs |

## Quick Links

### For Developers

- [Architecture Overview](ARCHITECTURE.md#overview) - High-level system design
- [Connection Pooling](ARCHITECTURE.md#connection-pooling) - How multiple devices share connections
- [Entity Generation](ARCHITECTURE.md#entity-generation) - How entities are created from registers

### For Protocol Implementation

- [Generic Device Info](PROTOCOL.md#generic-device-info-registers-all-types) - Device identification registers
- [Register Map](PROTOCOL.md#register-map-template) - Address ranges and usage
- [Write Verification](PROTOCOL.md#write-verification) - How writes are confirmed

## Related Files

| File | Location | Purpose |
|------|----------|---------|
| CLAUDE.md | Root | AI assistant guidance (code patterns, conventions) |
| registers.py | Component | Register definitions and device type configurations |
| const.py | Component | Constants and configuration options |

## Development Workflow

1. **Adding a new register**: See [CLAUDE.md](../CLAUDE.md#adding-a-new-read-register)
2. **Adding a new device type**: See [CLAUDE.md](../CLAUDE.md#adding-a-new-device-type)
3. **Understanding the architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
4. **Protocol details**: See [PROTOCOL.md](PROTOCOL.md)
