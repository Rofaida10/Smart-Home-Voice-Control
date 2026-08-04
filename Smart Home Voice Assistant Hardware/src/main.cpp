#include "config.h"
#include "light_controller.h"
#include "buzzer.h"
#include "dht_sensor.h"
#include "serial_manager.h"

// ============================================================================
// Application objects  (one instance per subsystem)
// ============================================================================

static LightController::Config light_cfg = {
    PIN_LIGHT_BUILTIN,
    PIN_LIGHT_WIFI,
    PIN_LIGHT_VOICE,
    PIN_LIGHT_ERROR
};

static SerialManager::Config serial_cfg = {
    SERIAL_BAUD_RATE,
    SERIAL_RX_BUFFER_SIZE
};

static DHTSensor::Config dht_cfg = {
    PIN_DHT_DATA,
    DHT_TYPE,
    DHT_POLL_INTERVAL_MS
};

static LightController g_light(light_cfg);
static Buzzer          g_buzzer(PIN_BUZZER);
static DHTSensor       g_dht(dht_cfg);
static SerialManager   g_serial(serial_cfg);

// ============================================================================
// setup()  —  one-time initialisation
// ============================================================================

void setup() {
    g_serial.begin();
    g_light.begin();
    g_buzzer.begin();
    g_dht.begin();

    g_serial.setLightController(&g_light);
    g_serial.setBuzzer(&g_buzzer);
    g_serial.setDHTSensor(&g_dht);
}

// ============================================================================
// loop()  —  runs continuously
// ============================================================================

void loop() {
    g_serial.update();
    g_light.update();
    g_buzzer.update();
    g_dht.update();
}
