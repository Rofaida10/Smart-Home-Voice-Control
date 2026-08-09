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
| Temperature & humidity monitoring | DHT11 cached via Adafruit library, polled at a configurable interval |
| Serial command interface | Case-insensitive text protocol, fixed 64-byte line buffer, manual parser |
| Streamlit-compatible protocol | `LIGHT_ON`, `LIGHT_OFF`, `MUSIC_ON`, `MUSIC_OFF`, `TEMP` — `TEMP` replies with only the temperature float |
| Authentication | Optional `AUTH <password>` command; does not gate the Streamlit commands |
| Status reporting | Multi-line status output with current system state |

---

## Hardware Components

| Component | Quantity | Purpose |
|---|---|---|
| ESP32 DevKit V1 | 1 | Main microcontroller |
| LED (any colour) | 4 | Auth, Light, Music, Error indication |
| Resistor 220 Ω | 4 | Current limiting for LEDs |
| Active buzzer | 1 | Audio feedback (3.3 V) |
| DHT11 | 1 | Temperature and humidity sensor |
| Pull-up resistor 10 kΩ | 1 | DHT11 data line |

---

## Pin Mapping

| Pin | Signal | Notes |
|---|---|---|
| GPIO 2 | Auth LED | Built-in LED (active HIGH) |
| GPIO 4 | Light LED | WiFi / Light status (active HIGH) |
| GPIO 5 | Music LED | Voice / Music status (active HIGH) |
| GPIO 15 | Error LED | Error indicator (active HIGH) |
| GPIO 16 | Buzzer | Active buzzer (HIGH = on) |
| GPIO 23 | DHT11 Data | Digital pin with 10 kΩ pull-up |

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
│   ├── dht_sensor.h            # DHT11 sensor API
│   └── serial_manager.h        # Serial command coordinator API
└── src/
    ├── main.cpp                # Application entry point, static instances
    ├── light_controller.cpp    # LED blink state machine
    ├── buzzer.cpp              # Audio pattern finite-state machine
    ├── dht_sensor.cpp          # DHT11 polling & caching
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
2. `TEMP` replies with **only** the temperature value as a float (e.g. `28.60`) — no units, no extra text.
3. Unknown commands are safely ignored (no response, no action).
4. Lines are trimmed of surrounding spaces / tabs / carriage returns before processing.

---

## Supported Commands

| Command | Arguments | Description |
|---|---|---|
| `LIGHT_ON` | — | Turn the Light LED ON |
| `LIGHT_OFF` | — | Turn the Light LED OFF |
| `MUSIC_ON` | — | Turn the buzzer ON (Music LED follows) |
| `MUSIC_OFF` | — | Turn the buzzer OFF (Music LED follows) |
| `TEMP` | — | Read temperature, reply with only the float value |
| `STATUS` | — | Report full system state |
| `AUTH` *(optional)* | `<password>` | Authenticate the session (feedback only) |

**Legacy aliases** (still accepted): `LIGHT ON` / `LIGHT OFF`, `MUSIC PLAY` / `MUSIC STOP`.

**Default password:** `esp32` (configurable in `config.h` via `AUTH_PASSWORD`)

---

## Expected Responses

| Command | Response |
|---|---|
| `LIGHT_ON` | `LIGHT_ON` |
| `LIGHT_OFF` | `LIGHT_OFF` |
| `MUSIC_ON` | `MUSIC_ON` |
| `MUSIC_OFF` | `MUSIC_OFF` |
| `TEMP` | `28.60` _(only the float — example)_ |
| `STATUS` | `STATUS`\n`AUTH=1`\n`LIGHT=1`\n`MUSIC=0`\n`TEMP=28.6`\n`HUM=61.3` |
| `AUTH esp32` | `AUTH_OK` |
| `AUTH wrong` | `AUTH_FAILED` |
| Invalid argument | `UNKNOWN_ARGUMENT` |
| Anything else | *(silently ignored)* |

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
| Light on | `LIGHT_ON` | Response: `LIGHT_ON`, Light LED ON |
| Light off | `LIGHT_OFF` | Response: `LIGHT_OFF`, Light LED OFF |
| Music on | `MUSIC_ON` | Response: `MUSIC_ON`, buzzer ON, Music LED ON |
| Music off | `MUSIC_OFF` | Response: `MUSIC_OFF`, buzzer OFF, Music LED OFF |
| Temperature read | `TEMP` | Response: only the temperature float, e.g. `28.60` |
| Authentication (correct) | `AUTH esp32` | Response: `AUTH_OK`, Auth LED ON, buzzer success beep |
| Authentication (wrong) | `AUTH wrong` | Response: `AUTH_FAILED`, Auth LED OFF, buzzer error beep |
| System status | `STATUS` | Multi-line response with all subsystem states |
| Invalid command | `FOO` | Silently ignored (no response) |

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
