# 🔥 ectoControl Adapter для Home Assistant

**Кастомный Modbus-компонент для Home Assistant** для работы с устройствами **ectoControl**.

Интеграция предназначена для подключения адаптеров **ectoControl**, обеспечивающих управление газовыми и электрическими котлами по различным коммуникационным шинам. В зависимости от модели адаптера поддерживаются такие протоколы, как **eBUS**, **OpenTherm**, **Navien** и другие.

## Возможности

### ✔ Автоматическое создание сенсоров
Интеграция формирует сенсоры для всех **MODBUS-регистров чтения**, описанных в документации адаптера.
Это позволяет получать актуальные параметры работы котла — температуру в контурах, статус, расход и другие данные (зависит от модели котла) — и создавать собственные автоматизации на их основе.

### ✔ Создание элементов управления
Для всех **MODBUS-регистров записи** создаются соответствующие управляющие сущности (числовые регуляторы, селекторы, переключатели, кнопки).
Это даёт возможность изменять параметры работы котла из Home Assistant и создавать собственные автоматизации с использованием данных сущностей.

### ✔ Несколько транспортов Modbus
TCP, UDP, Serial (RS-232/RS-485), RTU-over-TCP — выбор на этапе настройки интеграции.

### ✔ Пул соединений и несколько slave ID на одной шине
Несколько config-entry, указывающих на один физический порт, **разделяют один Modbus-клиент** с подсчётом ссылок. Это позволяет добавлять устройства на тот же Serial без конфликта блокировки порта и держать несколько slave ID на одной шине.

### ✔ Автоматическое определение типа устройства
Интеграция автоматически определяет тип подключенного адаптера при настройке, считывая информационные регистры `0x0000–0x0003` (тип устройства, 24-битный UID, число каналов).
Это позволяет адаптировать набор создаваемых сущностей под возможности конкретного устройства (OpenTherm v2, eBUS, Navien, датчики температуры, контактные сплиттеры, релейные модули и т. д.).

### ✔ Управление отдельными битами регистров
Поддерживается создание независимых переключателей для управления отдельными битами в одном регистре.
Это позволяет удобно управлять различными функциями котла, упакованными в один регистр (например, включение контуров отопления, ГВС и т. п.).

### ✔ Производные значения через конвертеры
Из одного read-регистра можно получить несколько сущностей: например, аптайм адаптера автоматически превращается в `datetime` последней загрузки.

### ✔ Несколько scan-интервалов
Регистры автоматически группируются по их `scan_interval` (5/15/60/300 с) — критичные значения (статус горелки, температуры) опрашиваются чаще, конфигурация котла — реже.

### ✔ Иерархия устройств: Адаптер + подустройство «Котёл»
Для типов устройств с коммуникацией с котлом (OpenTherm, eBUS, Navien) интеграция создаёт **два устройства**: основное — *Адаптер* (статус, прошивка, подключение, настройки Modbus) и подчинённое — *Котёл* со связью `via_device` на адаптер. На подустройстве живут температуры контуров и ГВС, ошибки, статусы горелки, уставки, режимы и команды. Это даёт в Home Assistant чёткое разделение между диагностикой адаптера и мониторингом/управлением котлом.

### ✔ Категория DIAGNOSTIC для всех сущностей
Все сущности (адаптерные и котельные) получают `EntityCategory.DIAGNOSTIC`. Это совместимо с ограничениями Home Assistant — в частности, `binary_sensor` не допускает категорию `CONFIG`, поэтому OpenTherm-ошибки и битовые статусы не блокируются при регистрации.

### ✔ Мониторинг связи с котлом
Интеграция отслеживает состояние подключения адаптера к котлу по **биту 3 LSB регистра 0x0010** и отображает соответствующий статус в Home Assistant. Все котельные сущности автоматически уходят в `unavailable`, пока связь с котлом не восстановится.

### ✔ RS-485 inter-frame delay
На Serial-подключениях после каждой Modbus-транзакции добавляется пауза **30 мс** — это даёт шине и адаптеру время на обработку и предотвращает слипание фреймов и ложные ошибки CRC.

### ✔ Безопасный read-modify-write
При установке битов в регистре мастер читает текущее значение, модифицирует бит и пишет обратно. Под каждый адрес регистра создаётся отдельный `asyncio.Lock`, поэтому одновременные изменения разных битов одного регистра (например, двух relay-каналов) не затирают друг друга.

### ✔ Верификация записи
После каждой записи мастер поллит status-регистр (смещение `REG_STATUS_OFFSET` от адреса записи) до `REG_DEFAULT_MAX_RETRIES` попыток с паузой `REG_DEFAULT_RETRY_DELAY`. Запись считается успешной, когда статус равен `REG_STATUS_OK`.

### ✔ Автоматическая отправка необходимых параметров
При установлении соединения адаптера с котлом интеграция отправляет все требуемые параметры (`write_after_connected`), обеспечивая корректный запуск и работу отопительного оборудования при перезапусках.

### ✔ Stateless-реле
Релейные модули (`0xC0`, `0xC1`) **не сохраняют состояние** между отключениями питания. Home Assistant остаётся источником истины: switch-сущности используют `assumed_state=True` и при восстановлении связи возвращают актуальное состояние регистра обратно в устройство.

### ✔ Удобный config-flow
Двухшаговая настройка в UI: общие параметры → параметры соединения (зависят от выбранного типа Modbus). Валидация пытается прочитать регистр `0x0003` через **уже существующее** pooled-соединение, если оно есть — без открытия нового порта.

### ✔ Подробная диагностика
В debug-режиме логируются внутренние тайминги (`COORD_SCAN`, `COORD_CYCLE`, `PYLIB.*`, `TIMING`) и весь обмен с pymodbus — удобно для диагностики медленных шин или реконнектов.

### ✔ Поддержка всех HA-платформ
Сущности создаются для всех платформ Home Assistant: `sensor`, `binary_sensor`, `number`, `select`, `switch`, `button`.

### ✔ Корректная работа после рестарта Home Assistant
После перезапуска Home Assistant интеграция отслеживает собственный запуск, восстанавливает соединение через пул и повторно отправляет котлу необходимые значения для восстановления корректной работы.

---

# 🔥 ectoControl Adapter Integration for Home Assistant

**A custom Modbus component for Home Assistant** for working with **ectoControl** devices.

This integration connects **ectoControl** adapters that provide control of gas and electric boilers via various communication buses. Depending on the adapter model, supported protocols include **eBUS**, **OpenTherm**, **Navien**, and others.

## Features

### ✔ Automatic sensor creation
The integration generates sensors for all **MODBUS read registers** described in the adapter documentation.
This allows Home Assistant to receive up-to-date boiler parameters — such as circuit temperatures, system status, flow rate, and other values (depending on the boiler model) — and use them to build custom automations.

### ✔ Creation of control entities
For all **MODBUS write registers**, the integration creates corresponding control entities (numeric, selectors, switches, buttons).
This makes it possible to adjust boiler parameters directly from Home Assistant and build automations using these entities.

### ✔ Multiple Modbus transports
TCP, UDP, Serial (RS-232/RS-485), and RTU-over-TCP — selectable during integration setup.

### ✔ Connection pool and multiple slave IDs on one bus
Multiple config entries pointing at the same physical port **share a single Modbus client** through reference counting. Lets you add devices on the same Serial without port-lock conflicts and run several slave IDs on one bus.

### ✔ Automatic device type detection
The integration automatically detects the type of connected adapter during setup by reading registers `0x0000–0x0003` (device type, 24-bit UID, channel count).
This allows the integration to adapt the set of created entities to the capabilities of the specific device (OpenTherm v2, eBUS, Navien, temperature sensors, contact splitters, relay modules, etc.).

### ✔ Individual bit control
The integration supports creating independent switches for controlling individual bits within a single register.
This provides convenient control over various boiler functions packed into one register (e.g., enabling heating circuits, DHW, etc.).

### ✔ Derived values via converters
A single read register can spawn multiple entities — e.g. adapter uptime is automatically converted into a boot-time `datetime`.

### ✔ Multiple scan intervals
Registers are automatically grouped by their `scan_interval` (5/15/60/300 s) — critical values (burner status, temperatures) are polled more often than boiler configuration.

### ✔ Device hierarchy: Adapter + Boiler sub-device
For device types that communicate with the boiler (OpenTherm, eBUS, Navien) the integration creates **two devices**: a main *Adapter* (status, firmware, connectivity, Modbus settings) and a *Boiler* sub-device linked via `via_device`. The sub-device hosts circuit and DHW temperatures, errors, burner statuses, setpoints, modes and commands. This gives a clean split between adapter diagnostics and boiler monitoring/control in Home Assistant.

### ✔ DIAGNOSTIC category for every entity
All entities (adapter-side and boiler-side) get `EntityCategory.DIAGNOSTIC`. This is compatible with Home Assistant restrictions — notably `binary_sensor` does not permit `CONFIG`, so OpenTherm error flags and bit-level statuses register cleanly.

### ✔ Monitoring of the boiler connection
The integration continuously monitors the connection status between the adapter and the boiler through **bit 3 of the LSB of register 0x0010** and exposes this status in Home Assistant. All boiler entities automatically switch to `unavailable` while the link to the boiler is down.

### ✔ RS-485 inter-frame delay
On Serial connections, each Modbus transaction is followed by a **30 ms** pause. Gives the bus and the adapter time to recover and avoids frame collisions and spurious CRC errors.

### ✔ Safe read-modify-write
Bit-level writes read the current value, mutate the bit, and write it back. Each register address has its own `asyncio.Lock`, so concurrent writes to different bits of the same register (e.g. two relay channels) never clobber each other.

### ✔ Write verification
After every write, the master polls the status register at `address + REG_STATUS_OFFSET` for up to `REG_DEFAULT_MAX_RETRIES` attempts spaced by `REG_DEFAULT_RETRY_DELAY`. The write is reported successful only when the status equals `REG_STATUS_OK`.

### ✔ Automatic transmission of required parameters
When the adapter establishes a connection with the boiler, the integration automatically sends all required configuration parameters (`write_after_connected`), ensuring proper boiler startup and operation during reconnections.

### ✔ Stateless relay handling
Relay modules (`0xC0`, `0xC1`) **lose state on power loss**. Home Assistant stays the source of truth: switch entities use `assumed_state=True` and re-push the desired state to the device once connectivity is restored.

### ✔ Pool-aware config flow
Two-step UI setup: common parameters → connection parameters (depend on the selected Modbus type). Validation reads register `0x0003` through the **existing** pooled connection when one is available, so adding devices on the same port does not open a second handle.

### ✔ Verbose diagnostics
At `debug` level the integration logs internal timings (`COORD_SCAN`, `COORD_CYCLE`, `PYLIB.*`, `TIMING`) and the full pymodbus exchange — handy for diagnosing slow buses or reconnect storms.

### ✔ All Home Assistant platforms
Entities are generated for every HA platform: `sensor`, `binary_sensor`, `number`, `select`, `switch`, `button`.

### ✔ Proper behavior after Home Assistant restarts
After HA restarts, the integration detects its own initialization, re-acquires the pooled connection and re-sends the values the boiler needs to resume correct operation.

---

## Документация / Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — пул, координаторы, жизненный цикл.
- **[docs/PROTOCOL.md](docs/PROTOCOL.md)** — карта регистров и bit-раскладки.
- **[CLAUDE.md](CLAUDE.md)** — гайд для контрибьюторов.