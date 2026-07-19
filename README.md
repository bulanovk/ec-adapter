# 🔥 Кастомный Modbus-компонент для Home Assistant — устройства ectoControl

Кастомный Modbus-компонент для Home Assistant, предназначенный для работы с устройствами **ectoControl**.

Интеграция предназначена для подключения устройств **ectoControl** по протоколу Modbus. Выбор конкретного устройства и набора сущностей происходит автоматически при настройке.

## Поддерживаемые устройства

### Адаптеры котлов (OpenTherm v2, eBUS)
Подключение газовых и электрических котлов через шину **OpenTherm v2** или **eBUS**. В Home Assistant создаётся основное устройство *Адаптер* и подчинённое *Котёл* со связью `via_device`.

**На адаптере:** статус подключения, тип шины, версии прошивки и железа, аптайм и время последней загрузки, коды вендора и модели, код последней перезагрузки.

**На котле:** температуры контуров отопления и ГВС (текущие и уставки min/max), давление, расход, модуляция горелки, статус горелки (общий / отопление / ГВС), температура наружного воздуха, основной и дополнительный коды ошибок, набор флагов ошибок OpenTherm (обслуживание, блокировка, низкое давление, ошибка розжига, низкое давление воздуха, перегрев теплоносителя).

**Управление:** уставки температуры (min/max по контуру и ГВС), выбор типа подключения, режимы и команды котла. Все параметры, требующие повторной отправки после восстановления связи, отправляются автоматически.

*(Поддержка адаптеров **Navien** заявлена в типах устройств, описание регистров в разработке.)*

### Контактные сплиттеры (8 / 10 каналов)
Многоканальные модули для контроля состояния контактов (двери, окна, ворота, датчики протечки и т. п.). Создаются до **8 или 10 бинарных сенсоров** `contact_1…contact_10` с классом устройства `opening`. Вариант определяется автоматически по числу каналов.

### Релейные модули (2 / 10 каналов)
Модули с дискретными выходами для коммутации нагрузки. Создаются **2 или 10 переключателей** `relay_1…relay_10` (по одному на канал), а также **таймеры автоотключения** на каждый канал с шагом 0,5 с. Состояние реле не сохраняется между отключениями питания — Home Assistant остаётся источником истины и восстанавливает его после потери связи.

### Датчики температуры, влажности, универсальные контактные датчики
Базовые типы устройств заявлены и автоматически распознаются при настройке. Подробное описание регистров — в разработке; при обнаружении такого устройства интеграция создаст соответствующие сенсоры.

## Возможности

### ✔ Автоматическое создание сенсоров
Интеграция формирует сенсоры для всех **MODBUS-регистров чтения**, описанных в документации адаптера.
Это позволяет получать актуальные параметры устройства и создавать собственные автоматизации на их основе.

### ✔ Создание элементов управления
Для всех **MODBUS-регистров записи** создаются соответствующие управляющие сущности (числовые регуляторы, селекторы, переключатели, кнопки).

### ✔ Несколько транспортов Modbus
TCP, UDP, Serial (RS-232/RS-485), RTU-over-TCP — выбор на этапе настройки интеграции.

### ✔ Пул соединений и несколько slave ID на одной шине
Несколько config-entry, указывающих на один физический порт, **разделяют один Modbus-клиент** с подсчётом ссылок. Это позволяет добавлять устройства на тот же Serial без конфликта блокировки порта и держать несколько slave ID на одной шине.

### ✔ Автоматическое определение типа устройства
Интеграция автоматически определяет тип подключенного устройства при настройке, считывая информационные регистры `0x0000–0x0003` (тип устройства, 24-битный UID, число каналов).

### ✔ Управление отдельными битами регистров
Поддерживается создание независимых переключателей и бинарных сенсоров для отдельных битов в одном регистре.

### ✔ Производные значения через конвертеры
Из одного read-регистра можно получить несколько сущностей: например, аптайм устройства автоматически превращается в `datetime` последней загрузки.

### ✔ Несколько scan-интервалов
Регистры автоматически группируются по их `scan_interval` — критичные значения опрашиваются чаще, конфигурация — реже.

### ✔ Иерархия устройств
Для устройств с подчинённой периферией интеграция создаёт **иерархию устройств** со связью `via_device` в Home Assistant.

### ✔ Мониторинг связи с устройством
Интеграция отслеживает состояние подключения к устройству и отображает соответствующий статус в Home Assistant. Сущности подчинённого устройства автоматически уходят в `unavailable`, пока связь не восстановится.

### ✔ Безопасный read-modify-write
При установке битов в регистре мастер читает текущее значение, модифицирует бит и пишет обратно. Под каждый адрес регистра создаётся отдельный `asyncio.Lock`, поэтому одновременные изменения разных битов одного регистра не затирают друг друга.

### ✔ Верификация записи
После каждой записи мастер поллит status-регистр до нескольких попыток. Запись считается успешной, когда статус подтверждает применение значения.

### ✔ Автоматическая отправка необходимых параметров
При установлении соединения интеграция отправляет все требуемые параметры (`write_after_connected`), обеспечивая корректный запуск и работу оборудования при перезапусках.

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

This integration connects **ectoControl** devices over the Modbus protocol. The specific device and set of entities are detected automatically during setup.

## Supported devices

### Boiler adapters (OpenTherm v2, eBUS)
Control of gas and electric boilers over **OpenTherm v2** or **eBUS**. Home Assistant shows a main *Adapter* device and a *Boiler* sub-device linked via `via_device`.

**On the adapter:** connectivity status, bus type, firmware and hardware versions, uptime and last boot time, vendor and model codes, last reboot code.

**On the boiler:** heating and DHW circuit temperatures (current and min/max setpoints), pressure, flow rate, burner modulation, burner status (overall / heating / DHW), outside temperature, main and additional error codes, OpenTherm error flag set (service required, blocked, low water pressure, ignition fault, low air pressure, overheating).

**Control:** temperature setpoints (min/max for heating and DHW), connection type, modes and boiler commands. All parameters that need to be re-sent after a reconnect are pushed automatically.

*(Navien adapter support is declared in the device-type registry; register descriptions are pending.)*

### Contact splitters (8 / 10 channels)
Multi-channel modules for monitoring contact states (doors, windows, gates, leak sensors, etc.). Creates up to **8 or 10 binary sensors** `contact_1…contact_10` with `opening` device class. The variant is detected automatically from the channel count.

### Relay modules (2 / 10 channels)
Modules with discrete outputs for switching loads. Creates **2 or 10 switches** `relay_1…relay_10` (one per channel), plus **auto-off timers** per channel with 0.5 s steps. Relays lose state on power loss — Home Assistant stays the source of truth and restores the desired state once connectivity is back.

### Temperature, humidity and universal contact sensors
Base device types are declared and recognized automatically during setup. Detailed register descriptions are pending; on detection the integration will create the corresponding sensors.

## Features

### ✔ Automatic sensor creation
The integration generates sensors for all **MODBUS read registers** described in the adapter documentation. Use them to build custom automations on real-time device parameters.

### ✔ Creation of control entities
For all **MODBUS write registers**, the integration creates corresponding control entities (numeric, selectors, switches, buttons).

### ✔ Multiple Modbus transports
TCP, UDP, Serial (RS-232/RS-485), and RTU-over-TCP — selectable during integration setup.

### ✔ Connection pool and multiple slave IDs on one bus
Multiple config entries pointing at the same physical port **share a single Modbus client** through reference counting. Lets you add devices on the same Serial without port-lock conflicts and run several slave IDs on one bus.

### ✔ Automatic device type detection
The integration automatically detects the type of connected device during setup by reading registers `0x0000–0x0003` (device type, 24-bit UID, channel count).

### ✔ Individual bit control
The integration supports independent switches and binary sensors for individual bits within a single register.

### ✔ Derived values via converters
A single read register can spawn multiple entities — e.g. device uptime is automatically converted into a boot-time `datetime`.

### ✔ Multiple scan intervals
Registers are automatically grouped by their `scan_interval` — critical values are polled more often than configuration.

### ✔ Device hierarchy
For devices with attached peripherals, the integration creates a **device hierarchy** linked via `via_device` in Home Assistant.

### ✔ Device connectivity monitoring
The integration continuously monitors the connection status of the device and exposes it in Home Assistant. Sub-device entities switch to `unavailable` while the link is down.

### ✔ Safe read-modify-write
Bit-level writes read the current value, mutate the bit, and write it back. Each register address has its own `asyncio.Lock`, so concurrent writes to different bits of the same register never clobber each other.

### ✔ Write verification
After every write, the master polls the status register for a few attempts. The write is reported successful only when the status confirms the value has been applied.

### ✔ Automatic transmission of required parameters
When the device is ready, the integration automatically sends all required configuration parameters (`write_after_connected`), ensuring proper startup and operation during reconnections.

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
