# AI Smart Home Voice Assistant — Hardware Firmware

![ESP32](https://img.shields.io/badge/ESP32-000000?style=flat&logo=espressif&logoColor=white)
![PlatformIO](https://img.shields.io/badge/PlatformIO-FF7F00?style=flat&logo=platformio&logoColor=white)
![Arduino](https://img.shields.io/badge/Arduino-00878F?style=flat&logo=arduino&logoColor=white)
![C++17](https://img.shields.io/badge/C%2B%2B-17-00599C?style=flat&logo=cplusplus&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat)

---

## Project Overview

Embedded firmware for an ESP32 DevKit V1 that powers a **Smart Home Voice Assistant** hardware node. The firmware provides a modular, non-blocking control system for lighting indication, audio feedback, and environmental sensing — all coordinated over a simple text-based UART protocol.

Designed for voice-assistant integration, this node can be driven by an external host (e.g., a Raspberry Pi running the voice pipeline) via serial commands.

**Key design principles:**

- **No `delay()`** — all timing uses `millis()`-based finite-state machines
- **No `String` class** — fixed C-string buffers only
- **No dynamic allocation** — everything is statically allocated at compile time
- **No JSON** — lightweight text protocol, parsed without `strtok`
- **C++17** with `-std=gnu++17`
- **Single coordinator architecture** — `SerialManager` is the only module that calls other modules

---

## Features

| Feature | Implementation |
|---|---|
| LED indication (4 channels) | Non-blocking state machine with static on/off and configurable blink sequences |
| Audio feedback | Active buzzer with three distinct patterns: success, error, warning |
| Temperature & humidity monitoring | DHT22 cached via Adafruit library, polled at a configurable interval |
| Serial command interface | Case-insensitive text protocol, fixed 64-byte line buffer, manual parser |
| Authentication | Password-based gate; all commands except AUTH require prior authentication |
| Status reporting | Multi-line status output with current system state |

---

## Hardware Components

| Component | Quantity | Purpose |
|---|---|---|
| ESP32 DevKit V1 | 1 | Main microcontroller |
| LED (any colour) | 4 | Auth, Light, Music, Error indication |
| Resistor 220 Ω | 4 | Current limiting for LEDs |
| Active buzzer | 1 | Audio feedback (3.3 V) |
| DHT22 | 1 | Temperature and humidity sensor |
| Pull-up resistor 10 kΩ | 1 | DHT22 data line |

---

## Pin Mapping

| Pin | Signal | Notes |
|---|---|---|
| GPIO 2 | Auth LED | Built-in LED (active HIGH) |
| GPIO 4 | Light LED | WiFi / Light status (active HIGH) |
| GPIO 5 | Music LED | Voice / Music status (active HIGH) |
| GPIO 15 | Error LED | Error indicator (active HIGH) |
| GPIO 16 | Buzzer | Active buzzer (HIGH = on) |
| GPIO 23 | DHT22 Data | Digital pin with 10 kΩ pull-up |

> **Note:** Pin assignments are defined in `include/config.h` and can be changed without modifying application logic.

---

## Firmware Architecture

The firmware follows a **polled-coordinator** pattern. Every module exposes a three-method lifecycle (`begin()`, `update()`, and a module-specific configuration API). All modules are ticked from the global `loop()` once per iteration.

```
┌──────────────────────────────────────────────────┐
│                    main.cpp                       │
│  setup():  begin() each module                    │
│  loop():   update() each module                   │
└──────┬──────────┬──────────┬──────────┬───────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
  │ Light  │ │ Buzzer │ │  DHT   │ │  Serial    │
  │Control │ │        │ │ Sensor │ │  Manager   │
  └────────┘ └────────┘ └────────┘ └─────┬──────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              ┌────────────┐       ┌────────┐          ┌──────────┐
              │  Light     │       │ Buzzer │          │   DHT    │
              │ Controller │       │        │          │  Sensor  │
              └────────────┘       └────────┘          └──────────┘
```

**`SerialManager` is the sole coordinator.** It holds pointers to the other modules (injected via setter methods during `setup()`) and is the only class allowed to call methods on other modules. There is no cross-module communication — all hardware events are triggered by serial commands.

### Module Descriptions

| Module | Responsibility | Key Methods |
|---|---|---|
| `LightController` | LED state machine with blink support | `authOn/Off()`, `lightOn/Off()`, `musicOn/Off()`, `blinkAuth/Light/Music()`, `isAuth/Light/MusicOn()` |
| `Buzzer` | Non-blocking audio patterns | `success()`, `error()`, `warning()`, `stop()`, `isPlaying()` |
| `DHTSensor` | Caching wrapper around Adafruit DHT library | `getTemperature()`, `getHumidity()`, `hasValidReading()` |
| `SerialManager` | UART coordinator, text protocol parser & dispatcher | `begin()`, `update()`, setters for module pointers |

---

## Folder Structure

```
Smart Home Voice Assistant Hardware/
├── platformio.ini              # PlatformIO build configuration
├── README.md
├── include/
│   ├── config.h                # Pin assignments, timing constants, password
│   ├── light_controller.h      # LED control API
│   ├── buzzer.h                # Buzzer API
│   ├── dht_sensor.h            # DHT22 sensor API
│   └── serial_manager.h        # Serial command coordinator API
└── src/
    ├── main.cpp                # Application entry point, static instances
    ├── light_controller.cpp    # LED blink state machine
    ├── buzzer.cpp              # Audio pattern finite-state machine
    ├── dht_sensor.cpp          # DHT22 polling & caching
    └── serial_manager.cpp      # UART protocol parser & dispatcher
```

---

## Communication Protocol

### Transport

| Parameter | Value |
|---|---|
| Interface | UART (Serial) |
| Baud rate | 115 200 |
| Buffer size | 64 bytes (fixed) |
| Termination | `\n` or `\r` |
| Encoding | ASCII |
| Case sensitivity | **Case-insensitive** (input is uppercased before parsing) |

### Protocol Rules

1. Every command triggers exactly one response line (or a multi-line response for `STATUS`).
2. `AUTH` must succeed before any other command is accepted.
3. Unknown commands receive `UNKNOWN_COMMAND`.
4. Unauthenticated commands receive `NOT_AUTHENTICATED`.

---

## Supported Commands

| Command | Arguments | Description | Auth Required |
|---|---|---|---|
| `AUTH` | `<password>` | Authenticate the session | No |
| `LIGHT` | `ON` / `OFF` | Toggle the Light LED | Yes |
| `MUSIC` | `PLAY` / `STOP` | Toggle the Music LED | Yes |
| `TEMP` | — | Read temperature & humidity | Yes |
| `STATUS` | — | Report full system state | Yes |

**Default password:** `esp32` (configurable in `config.h` via `AUTH_PASSWORD`)

---

## Expected Responses

| Command | Response |
|---|---|
| `AUTH esp32` | `AUTH_OK` |
| `AUTH wrong` | `AUTH_FAILED` |
| `LIGHT ON` | `LIGHT_ON` |
| `LIGHT OFF` | `LIGHT_OFF` |
| `MUSIC PLAY` | `MUSIC_PLAYING` |
| `MUSIC STOP` | `MUSIC_STOPPED` |
| `TEMP` | `TEMP 25.6 61.3` _(example)_ |
| `TEMP` (sensor error) | `TEMP_ERROR` |
| `STATUS` | `STATUS`\n`AUTH=1`\n`LIGHT=1`\n`MUSIC=0`\n`TEMP=25.6`\n`HUM=61.3` |
| Any command before auth | `NOT_AUTHENTICATED` |
| Invalid command | `UNKNOWN_COMMAND` |
| Invalid argument | `UNKNOWN_ARGUMENT` |

---

## Build Instructions

### Prerequisites

- [PlatformIO Core](https://platformio.org/install) (`pip install platformio`)
- Python 3.8+

### Build & Upload

```bash
# Navigate to the firmware directory
cd "Smart Home Voice Assistant Hardware"

# Build the firmware
pio run

# Upload to ESP32 (via USB)
pio run --target upload

# Monitor serial output
pio device monitor
```

### PlatformIO Configuration

From `platformio.ini`:

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200
board_build.psram = enable
build_flags = -std=gnu++17
lib_deps =
    adafruit/DHT sensor library
    adafruit/Adafruit Unified Sensor
```

---

## Testing

| Test Case | Input | Expected Result |
|---|---|---|
| Unauthenticated command | `LIGHT ON` | Response: `NOT_AUTHENTICATED` |
| Authentication (correct) | `AUTH esp32` | Response: `AUTH_OK`, Auth LED ON, buzzer success beep |
| Authentication (wrong) | `AUTH wrong` | Response: `AUTH_FAILED`, Auth LED OFF, buzzer error beep |
| Light on | `LIGHT ON` | Response: `LIGHT_ON`, Light LED ON |
| Light off | `LIGHT OFF` | Response: `LIGHT_OFF`, Light LED OFF |
| Music play | `MUSIC PLAY` | Response: `MUSIC_PLAYING`, Music LED ON |
| Music stop | `MUSIC STOP` | Response: `MUSIC_STOPPED`, Music LED OFF |
| Temperature read | `TEMP` | Response: `TEMP 25.6 61.3` (or `TEMP_ERROR` if sensor unavailable) |
| System status | `STATUS` | Multi-line response with all subsystem states |
| Invalid command | `FOO` | Response: `UNKNOWN_COMMAND` |

---

## Future Improvements

- [ ] WiFi connectivity with MQTT bridge for remote control
- [ ] OTA firmware updates
- [ ] Multiple DHT sensor zones
- [ ] PWM-based LED dimming (migrate from on/off to brightness control)
- [ ] Configurable password at runtime
- [ ] Support for additional sensor types (motion, gas, light)
- [ ] Unit test suite using PlatformIO's test framework

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
