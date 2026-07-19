# Исследование: «Modernizing Modbus in Home Assistant» и что это значит для `ec-adapter`

## Контекст

Блог разработчиков Home Assistant (Paulus Schoutsen, пост от **5 июля 2026**,
обновление **16 июля 2026**) объявляет новый способ подключения Modbus-устройств
в HA, который заменяет YAML-карту регистров, которую пользователь пишет
руками, на UI-first поток, где каждое устройство — отдельная интеграция.
Изменение строится на трёх слоях:

1. **Core-интеграция `modbus_connection`** — владеет физическим транспортом
   (serial, TCP, UDP, RTU-over-TCP) и выдаёт per-unit handles
   потребительским интеграциям.
2. **Backend-neutral Python-библиотека `modbus-connection`** на PyPI
   (текущая версия 3.8.1) — определяет протоколы `ModbusConnection` /
   `ModbusUnit`, содержит фреймворк `modbus_connection.model` для
   моделирования устройств и pytest-плагин с in-memory мок-бэкендом.
3. **Интеграции для конкретных устройств** — берут `ModbusUnit` через
   `async_get_unit(hass, connection_entry_id, unit_id)`, передают его в
   device-библиотеку и публикуют сущности. Канонический пример — пара
   `trovis-modbus` (библиотека) + `trovis557x` (HA-интеграция).

В обновлении от 16 июля Paulus прямо говорит: *«фундамент не меняется:
всё по-прежнему строится вокруг PyPI-пакета modbus-connection, и
device-библиотеки на его основе — правильная инвестиция. Мы
переосмысливаем то, как соединения выглядят внутри Home Assistant, где
хотим сосредоточиться на лучшем UX. Если вы работаете над интеграцией
устройства — пока не подключайте её к modbus_connection, мы скоро
поделимся обновлённым подходом»*.

Вывод для `ec-adapter` (этот репозиторий): прямо сейчас **ничего не
переподключаем**, но готовим рефакторинг так, чтобы он совпал с новой
формой и не заводил нас в угол. Ниже — суть нового подхода, мэппинг
текущего кода и варианты миграции с рисками.

## Что именно меняет новый подход

### Модель соединения
* **Сейчас:** каждая интеграция открывает свой pymodbus-клиент
  (`helpers.create_modbus_client`); serial-порты шарились только потому,
  что `pool.py` строит внутрипроцессный `ModbusClientPool` с ключами
  `serial:…` / `tcp:…` / `udp:…` / `rtuovertcp:…`.
* **Будет:** один `modbus_connection` config entry владеет транспортом,
  все потребители берут `ModbusUnit` (1–247) через
  `homeassistant.components.modbus_connection.async_get_unit`. Библиотека
  `modbus-connection` — backend-neutral шов; pymodbus и tmodbus
  взаимозаменяемы.

### Config flow
* **Сейчас** (`config_flow.py`): пользователь выбирает тип транспорта,
  host/port, параметры serial, таймаут **и** slave ID, затем интеграция
  сама пингует регистр `0x0003` для валидации.
* **Будет:** пользователь один раз добавляет `modbus_connection` entry
  (транспорт + unit ID), а *device*-интеграция в своём config flow
  предлагает `ConfigEntrySelector(integration="modbus_connection")` плюс
  `NumberSelector(1, 247, BOX)` для slave/unit. Валидация slave ID,
  пробирование регистров и определение модели — забота библиотеки, а
  не config flow.

### Моделирование устройства
* **Сейчас:** `registers.py` (~28 КБ) вручную описывает `REGISTERS_R` /
  `REGISTERS_W`. Каждая запись смешивает поля транспорта (`count`,
  `data_type`, `input_type`, `scan_interval`) с полями HA-сущности
  (`name`, `device_class`, `unit_of_measurement`, `category`, `bitmasks`,
  `converters`). Device type — числовой код в записи (`0x14`, `0x15`, …),
  варианты (`(0x59, 8)`, `(0xC0, 2)`) собираются вручную.
* **Будет:** device-библиотека использует `modbus_connection.model.Component`
  / `ComponentGroup` с field-хелперами (`gauge`, `uint32`, `coil`, `enum`,
  `raw_register`) и metadata-классами (`NumberMetadata`, `EnumMetadata`,
  `BooleanMetadata`, `TemporalMetadata`). Чтения батчатся в минимальное
  число Modbus-вызовов с учётом range / coil-границ контроллера (как в
  trovis — `ranges_for_model(model)`). HA-интеграция только маппит
  `DatapointMetadata` на платформенные сущности.

### Polling и запись
* **Сейчас:** `ModbusDataUpdateCoordinator` группирует регистры по
  `scan_interval` и шлёт по одному чтению на регистр; записи идут через
  `ModbusMasterCoordinator.write_registers()` с собственным поллингом
  status-регистра (`REG_STATUS_OFFSET`, `REG_STATUS_OK`,
  `REG_DEFAULT_MAX_RETRIES`, `REG_DEFAULT_RETRY_DELAY`).
* **Будет:** device-библиотека владеет планом `ComponentGroup.async_update()`
  и отдаёт типизированные значения; интеграция просто дёргает
  refresh координатора и прокидывает записи через
  `component.async_write_datapoint(field, value)`. Свой поллинг status
  не нужен, если библиотека умеет бросать исключения при ошибках
  устройства (в trovis — `TrovisWriteAccessError` и т. п.).

### Жизненный цикл соединения
* **Сейчас:** интеграция сама владеет соединением, открывает на первом
  `pool.acquire()` и закрывает на последнем `pool.release()`; реконнект —
  то, что делает pymodbus, плюс ручной monkey-patch в `pool.py`
  (`_diag_execute`, `_diag_callback_data`).
* **Будет:** `modbus_connection` сам реконнектится. Потребитель
  подписывается на `unit.on_connection_lost(lambda: hass.config_entries.
  async_schedule_reload(entry.entry_id))` — handle перепривязывается к
  новой сессии.

## Сопоставление текущего кода `ec-adapter` с новой моделью

| Задача                       | Текущий файл                                  | Эквивалент в новом мире                                      | Разрыв |
|------------------------------|-----------------------------------------------|--------------------------------------------------------------|--------|
| Фабрика транспорта           | `helpers.py`                                  | config flow `modbus_connection`                              | полный |
| Пул / рефкаунт               | `pool.py` (`ModbusClientPool`, `PooledClient`)| не нужен — в core-интеграции                                 | полный |
| Обёртка клиента              | `master.py` (`ModbusMasterCoordinator`)       | `modbus_connection.ModbusUnit`                               | полный |
| Словарь регистров            | `registers.py`                                | `modbus-connection.model.Component` + наследники             | частичный |
| Определение типа устройства   | `__init__.py` строки 83–107 + `master.detect_device_type` | `async_probe()` device-библиотеки (как `Trovis557x.async_probe`) | дизайн |
| Polling-координатор          | `coordinator.py`                              | HA `DataUpdateCoordinator`, драйвер — `async_update` библиотеки | маленький |
| Polling статуса записи       | `master._verify_write_status`, `REG_STATUS_*` | `async_write_datapoint` библиотеки бросает на ошибке         | полный |
| Bitmask-переключатели        | `switch.py` (`BITMASK_SWITCH_INPUT`) + `master.write_register_bit` | `coil(writable=True)` в библиотеке + `SwitchEntity` поверх  | полный |
| Config flow                  | `config_flow.py` (транспорт + slave)          | `ConfigEntrySelector(integration="modbus_connection")` + unit ID | полный |
| `manifest.json requirements` | `pymodbus==3.13.1`                            | `trovis-modbus`-style device library (или прямой `modbus-connection`) | полный |
| Доступность связи с котлом   | `coordinator._BOILER_COMM_OK`, `master.boiler_comm_ok` | библиотека отдаёт `connectivity` через `gauge`/`coil`        | маленький |
| Под-устройство «котёл»       | `__init__.py` (`via_device` для boiler)       | не меняется — `device_info` остаётся в интеграции            | нет |

## Риски при действии уже сейчас

1. **HA-сторона в движении.** Обновление от 16 июля прямо просит
   повременить с подключением к `modbus_connection`: «мы скоро поделимся
   обновлённым подходом». Код, привязанный к текущей форме
   consumer-интеграции, скорее всего, придётся переписывать.
2. **`modbus-connection` 3.8.1 уже на PyPI** и помечен как
   «фундамент, который не меняется». Выделение device-библиотеки,
   зависящей от него — обратимая инвестиция, даже если HA-сторона
   изменится.
3. `trovis-modbus` / `trovis557x` — канонический референс. Семейство
   ectoControl — другой производитель, но **форма** (типизированный
   объект устройства + метаданные по каждой точке + `ComponentGroup`)
   переносится безболезненно.
4. Текущая логика **поллинга статуса записи** по
   `address + REG_STATUS_OFFSET` никуда не денется: если библиотека
   не умеет сама прочитать status, его можно оставить в слое библиотеки
   (например, `try_write_then_verify` хелпер).
5. **Соединительный пул** сейчас — наш собственный код, не зависящий от
   HA. Его удаление означает, что сериализация уходит из наших рук
   (это хорошо, но это и изменение поведения для пользователей, которые
   полагались на разделение между *разными* custom-компонентами — им
   придётся сначала добавить `modbus_connection` entry и перепривязать
   к нему каждую custom-интеграцию).
6. `BITMASK_SWITCH_INPUT` в `switch.py` плотно привязан к
   `ModbusMasterCoordinator.write_register_bit` (read-modify-write
   `0x0010`). В новом мире это выражается как `coil(writable=True)` +
   `SwitchEntity` поверх него, но нужно аккуратно смоделировать
   «регистр из битов» в `modbus_connection.model` (например, по
   `BitfieldRegister`-полю на каждый канал).

## Варианты миграции (без кода прямо сейчас)

### Вариант A — Roadmap без изменений (рекомендуется сейчас)
Сохраняем текущий стек pymodbus + pool + master + coordinator, но:
* добавляем в `docs/ARCHITECTURE.md` раздел «Будущая миграция на
  `modbus_connection`»;
* отслеживаем релизы `home-assistant-libs/modbus-connection`;
* публикуем `docs/MODERNIZING_MODBUS.md` со ссылкой на блог-пост и
  объяснением, что ec-adapter переедет, как только стабилизируется
  HA-сторона.

**Стоимость:** очень низкая. **Риск:** продолжаем копить собственный
connection-код, который рано или поздно будет удалён.

### Вариант B — Вынести только device-библиотеку `ectocontrol-modbus`
Оформляем PyPI-пакет по образцу `trovis-modbus` (структура
`src/ectocontrol_modbus/{__init__,device,components,…}.py`), зависящий
от `modbus-connection`, с одним классом на семейство устройств
(`OpenThermAdapter`, `EbusAdapter`, `ContactSplitter`, `RelayBlock`…).
HA-интеграция сохраняет свой config flow + coordinator, но берёт
`ModbusUnit` вместо собственного пула.

**Стоимость:** средняя — делим регистры на компоненты библиотеки,
добавляем слой метаданных, выбрасываем `pool.py` и `helpers.py`.
**Риск:** поддерживать два репозитория; HA-сторону всё равно придётся
переписывать позже; `manifest.json` `requirements` становится
device-библиотекой.

### Вариант C — Полный переход (B + `modbus_connection` config flow)
Device-библиотека + переписанный `custom_components/ectocontrol_adapter`
с `dependencies: ["modbus_connection"]` и config flow, который выбирает
`modbus_connection` entry и unit ID. Удаляем `pool.py`, `master.py`,
`helpers.py` и транспортные куски `config_flow.py`.

**Стоимость:** высокая — самое заметное пользователю изменение,
существующие config entries не мигрируют автоматически (потребуется
`ConfigEntry.migrate`), пробирование `0x0003` уходит из config flow.
**Риск:** максимальный, и обновление от 16 июля прямо предостерегает
от этого. Не выпускать до стабилизации HA-стороны.

## Рекомендованный следующий шаг (прямо сейчас) — Вариант A

1. Добавить в `docs/ARCHITECTURE.md` секцию «Modernizing Modbus
   roadmap» со ссылкой на блог-пост и обновление от 16 июля, описанием
   вариантов A/B/C и пометкой, что **код не меняем до стабилизации**.
2. Создать `docs/MODERNIZING_MODBUS.md` — короткий документ для
   пользователей: «что такое новый подход, что значит для ec-adapter,
   когда ждать». Содержит контекст, ссылки, FAQ.
3. Завести tracking-issue «Adopt new Modbus stack» со ссылками на блог,
   обновление, `home-assistant-libs/modbus-connection` и этот план.
4. Подписаться на watch-лист репозитория
   `home-assistant-libs/modbus-connection`, чтобы не пропустить
   breaking change по core-стороне.

## Spike: скелет будущей `ectocontrol-modbus` device-библиотеки

(Без кода прямо сейчас — это эскиз структуры по образцу `trovis-modbus`,
который можно поднять как отдельный spike после стабилизации HA-стороны.)

Целевая раскладка пакета:

```
ectocontrol-modbus/
├── pyproject.toml
├── README.md
├── src/ectocontrol_modbus/
│   ├── __init__.py            # публичный API
│   ├── exceptions.py          # EcReadError, EcWriteAccessError, ...
│   ├── enums.py               # OperatingMode, BurnerState, BoilerFamily, ...
│   ├── addresses.py           # register_address(0x0010) → плоский int
│   ├── metadata.py            # Number/Enum/Bool/Time metadata + attach
│   ├── ranges.py              # REGISTER_RANGES / COIL_RANGES per device family
│   ├── model.py               # Component-обёртки (BoilerStatus, TemperatureSensor, ...)
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── opentherm.py       # OpenThermAdapter: info, burner, temps, errors
│   │   ├── ebus.py            # EbusAdapter
│   │   ├── navien.py          # NavienAdapter
│   │   ├── contact_splitter.py# ContactSplitter: bitfield каналов
│   │   └── relay_block.py     # RelayBlock: bitfield + timer registers
│   └── cli.py                 # `python -m ectocontrol_modbus tcp 192.168.1.50 --unit 1`
└── tests/
    └── conftest.py            # использует modbus_connection.mock
```

Ключевые принципы (по образцу `trovis-modbus`):

* `Component` верхнего уровня = один адаптер; его `async_probe(unit)`
  читает только безопасные identity-регистры (`0x0001`–`0x0003`) и
  возвращает dataclass вроде `EcProbe(family, uid, channels)`.
* `ComponentGroup.async_update()` батчит регистры в минимальное число
  Modbus-запросов, уважая `REGISTER_RANGES[family]`.
* Каждое поле — типизированное (`gauge`, `uint32`, `coil`, `enum`),
  декоратор `attach_metadata(...)` навешивает `NumberMetadata` /
  `EnumMetadata` / … для HA-стороны.
* `datapoint.async_write_datapoint(field, value)` сам заботится о
  scaling, signed-conversion и preconditions (для котлов —
  enable-write-access перед записью параметра).
* Никаких упоминаний Home Assistant в пакете (только `modbus_connection`
  и стандартная библиотека) — это позволит использовать его в любых
  Python-проектах.

Тесты — на in-memory mock из `modbus_connection` (`pytest` плагин,
по аналогии с `libtest.sh` у trovis), без физического устройства.

## Верификация (после любых изменений в этой зоне)

* `pytest` (или актуальный раннер проекта) продолжает зеленеть —
  текущие тесты покрывают парсинг регистров и поллинг статуса записи,
  оба упражняются через нынешний pool/master-путь.
* Ручной smoke-тест: настроить устройство на serial, добавить второй
  `ec-adapter` entry на тот же порт с другим slave ID, убедиться, что
  физически открыто одно соединение (в новом мире пользователь сначала
  добавляет один `modbus_connection` entry и привязывает оба устройства
  к нему).
* Линтеры из `CLAUDE.md`: `.venv/bin/python -m flake8` и `mypy`
  должны остаться зелёными.

## Открытые вопросы (зафиксировать при следующей итерации)

* Какой набор семейств устройств (`DEVICE_TYPE_NAMES`) целесообразно
  моделировать в первом релизе библиотеки? Датчики температуры/влажности
  тривиальны, можно отложить.
* Выделять `ectocontrol-modbus` как самостоятельный PyPI-пакет
  (вариант B) или хранить вендоризованную копию в `vendor/` внутри HACS
  интеграции (минус публикация, плюс больше связности)?
* Нужен ли CLI-инструмент (как `script/query.py` у trovis) для
  диагностики на месте, или достаточно HA-сущностей?
