#ifndef CONFIG_H
#define CONFIG_H

#include <cstdint>

// ============================================================================
// Pin Mappings — ESP32 DevKit V1
// ============================================================================

#define PIN_LIGHT_BUILTIN    2
#define PIN_LIGHT_WIFI       4
#define PIN_LIGHT_VOICE      5
#define PIN_LIGHT_ERROR      15

#define PIN_BUZZER           16

#define PIN_DHT_DATA         23

// ============================================================================
// Sensor
// ============================================================================

#define DHT_TYPE             DHT22
#define DHT_POLL_INTERVAL_MS  2000

// ============================================================================
// Light Controller
// ============================================================================

constexpr uint16_t DEFAULT_BLINK_INTERVAL_MS = 250;

// ============================================================================
// Serial
// ============================================================================

#define SERIAL_BAUD_RATE      115200
#define SERIAL_RX_BUFFER_SIZE 128
#define AUTH_PASSWORD        "esp32"

#endif  // CONFIG_H
