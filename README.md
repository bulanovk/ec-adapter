# 🔥 Кастомный Modbus-компонент для Home Assistant — устройства ectoControl

Кастомный Modbus-компонент для Home Assistant, предназначенный для работы с устройствами **ectoControl**.

Интеграция предназначена для подключения устройств **ectoControl** по протоколу Modbus. Поддерживаются адаптеры котлов (eBUS, OpenTherm v2, Navien), датчики температуры и влажности, универсальные контактные датчики, контактные сплиттеры (8 / 10 каналов), а также релейные модули (2 / 10 каналов). Выбор конкретного устройства и набора сущностей происходит автоматически при настройке.

## Возможности

### ✔ Автоматическое создание сенсоров
Интеграция формирует сенсоры для всех **MODBUS-регистров чтения**, описанных в документации адаптера.
Это позволяет получать актуальные параметры устройства — температуру, влажность, состояние контактов, параметры котла и другие данные (зависит от типа устройства) — и создавать собственные автоматизации на их основе.

### ✔ Создание элементов управления
Для всех **MODBUS-регистров записи** создаются соответствующие управляющие сущности (числовые регуляторы, селекторы, переключатели, кнопки).
Это даёт возможность изменять параметры устройства из Home Assistant и создавать собственные автоматизации с использованием данных сущностей.

### ✔ Несколько транспортов Modbus
TCP, UDP, Serial (RS-232/RS-485), RTU-over-TCP — выбор на этапе настройки интеграции.

### ✔ Пул соединений и несколько slave ID на одной шине
Несколько config-entry, указывающих на один физический порт, **разделяют один Modbus-клиент** с подсчётом ссылок. Это позволяет добавлять устройства на тот же Serial без конфликта блокировки порта и держать несколько slave ID на одной шине.

### ✔ Автоматическое определение типа устройства
Интеграция автоматически определяет тип подключенного устройства при настройке, считывая информационные регистры `0x0000–0x0003` (тип устройства, 24-битный UID, число каналов).
Это позволяет адаптировать набор создаваемых сущностей под возможности конкретного устройства.

### ✔ Управление отдельными битами регистров
Поддерживается создание независимых переключателей для управления отдельными битами в одном регистре.
Это позволяет удобно управлять различными функциями, упакованными в один регистр (например, релейными каналами или режимами котла).

### ✔ Производные значения через конвертеры
Из одного read-регистра можно получить несколько сущностей: например, аптайм устройства автоматически превращается в `datetime` последней загрузки.

### ✔ Несколько scan-интервалов
Регистры автоматически группируются по их `scan_interval` — критичные значения опрашиваются чаще, конфигурация — реже.

### ✔ Иерархия устройств: основное устройство + подустройства
Для устройств с подчинённой периферией интеграция создаёт **иерархию устройств** со связью `via_device` в Home Assistant. Например, для адаптеров котлов (OpenTherm, eBUS, Navien) — основное устройство *Адаптер* и подчинённое *Котёл*.

### ✔ Мониторинг связи с устройством
Интеграция отслеживает состояние подключения к устройству и отображает соответствующий статус в Home Assistant.

### ✔ Безопасный read-modify-write
При установке битов в регистре мастер читает текущее значение, модифицирует бит и пишет обратно. Под каждый адрес регистра создаётся отдельный `asyncio.Lock`, поэтому одновременные изменения разных битов одного регистра не затирают друг друга.

### ✔ Верификация записи
После каждой записи мастер поллит status-регистр до нескольких попыток. Запись считается успешной, когда статус подтверждает применение значения.

### ✔ Автоматическая отправка необходимых параметров
При установлении соединения интеграция отправляет все требуемые параметры (`write_after_connected`), обеспечивая корректный запуск и работу оборудования при перезапусках.

### ✔ Stateless-реле
Релейные модули **не сохраняют состояние** между отключениями питания. Home Assistant остаётся источником истины: switch-сущности используют `assumed_state=True` и при восстановлении связи возвращают актуальное состояние регистра обратно в устройство.

### ✔ Удобный config-flow
Двухшаговая настройка в UI: общие параметры → параметры соединения (зависят от выбранного типа Modbus). Валидация пытается прочитать дескриптор устройства через **уже существующее** pooled-соединение, если оно есть — без открытия нового порта.

### ✔ Подробная диагностика
В debug-режиме логируются внутренние тайминги и весь обмен с pymodbus — удобно для диагностики медленных шин или реконнектов.

### ✔ Поддержка всех HA-платформ
Сущности создаются для всех платформ Home Assistant: `sensor`, `binary_sensor`, `number`, `select`, `switch`, `button`.

### ✔ Корректная работа после рестарта Home Assistant
После перезапуска Home Assistant интеграция отслеживает собственный запуск, восстанавливает соединение через пул и повторно отправляет необходимые значения для восстановления корректной работы.

---

# 🔥 Custom Modbus component for Home Assistant — ectoControl devices

A custom Modbus component for Home Assistant that works with **ectoControl** devices.

This integration connects **ectoControl** devices over the Modbus protocol. Supported devices include boiler adapters (eBUS, OpenTherm v2, Navien), temperature and humidity sensors, universal contact sensors, contact splitters (8 / 10 channels), and relay modules (2 / 10 channels). The specific device and set of entities are detected automatically during setup.

## Features

### ✔ Automatic sensor creation
The integration generates sensors for all **MODBUS read registers** described in the adapter documentation.
This allows Home Assistant to receive up-to-date device parameters — temperature, humidity, contact state, boiler readings, and other values (depending on the device type) — and use them to build custom automations.

### ✔ Creation of control entities
For all **MODBUS write registers**, the integration creates corresponding control entities (numeric, selectors, switches, buttons).
This makes it possible to adjust device parameters directly from Home Assistant and build automations using these entities.

### ✔ Multiple Modbus transports
TCP, UDP, Serial (RS-232/RS-485), and RTU-over-TCP — selectable during integration setup.

### ✔ Connection pool and multiple slave IDs on one bus
Multiple config entries pointing at the same physical port **share a single Modbus client** through reference counting. Lets you add devices on the same Serial without port-lock conflicts and run several slave IDs on one bus.

### ✔ Automatic device type detection
The integration automatically detects the type of connected device during setup by reading registers `0x0000–0x0003` (device type, 24-bit UID, channel count).
This allows the integration to adapt the set of created entities to the capabilities of the specific device.

### ✔ Individual bit control
The integration supports creating independent switches for controlling individual bits within a single register.
This provides convenient control over various functions packed into one register (e.g., relay channels or boiler modes).

### ✔ Derived values via converters
A single read register can spawn multiple entities — e.g. device uptime is automatically converted into a boot-time `datetime`.

### ✔ Multiple scan intervals
Registers are automatically grouped by their `scan_interval` — critical values are polled more often than configuration.

### ✔ Device hierarchy: main device + sub-devices
For devices with attached peripherals, the integration creates a **device hierarchy** linked via `via_device` in Home Assistant. For boiler adapters (OpenTherm, eBUS, Navien) it produces a main *Adapter* device and a *Boiler* sub-device.

### ✔ Device connectivity monitoring
The integration continuously monitors the connection status of the device and exposes it in Home Assistant.

### ✔ Safe read-modify-write
Bit-level writes read the current value, mutate the bit, and write it back. Each register address has its own `asyncio.Lock`, so concurrent writes to different bits of the same register never clobber each other.

### ✔ Write verification
After every write, the master polls the status register for a few attempts. The write is reported successful only when the status confirms the value has been applied.

### ✔ Automatic transmission of required parameters
When the device is ready, the integration automatically sends all required configuration parameters (`write_after_connected`), ensuring proper startup and operation during reconnections.

### ✔ Stateless relay handling
Relay modules **lose state on power loss**. Home Assistant stays the source of truth: switch entities use `assumed_state=True` and re-push the desired state to the device once connectivity is restored.

### ✔ Pool-aware config flow
Two-step UI setup: common parameters → connection parameters (depend on the selected Modbus type). Validation reads the device descriptor through the **existing** pooled connection when one is available, so adding devices on the same port does not open a second handle.

### ✔ Verbose diagnostics
At `debug` level the integration logs internal timings and the full pymodbus exchange — handy for diagnosing slow buses or reconnect storms.

### ✔ All Home Assistant platforms
Entities are generated for every HA platform: `sensor`, `binary_sensor`, `number`, `select`, `switch`, `button`.

### ✔ Proper behavior after Home Assistant restarts
After HA restarts, the integration detects its own initialization, re-acquires the pooled connection and re-sends the values the device needs to resume correct operation.

---

## Документация / Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — пул, координаторы, жизненный цикл.
- **[docs/PROTOCOL.md](docs/PROTOCOL.md)** — карта регистров и bit-раскладки.
- **[CLAUDE.md](CLAUDE.md)** — гайд для контрибьюторов.
