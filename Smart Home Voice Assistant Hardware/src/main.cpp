#include "config.h"
#include "communication_config.h"
#include "light_controller.h"
#include "buzzer.h"
#include "dht_sensor.h"
#include "serial_manager.h"

#if COMMUNICATION_MODE == COMMUNICATION_MODE_SUPABASE
#include "wifi_manager.h"
#include "supabase_client.h"
#endif

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

#if COMMUNICATION_MODE == COMMUNICATION_MODE_SUPABASE
static WiFiManager     g_wifi(WIFI_SSID, WIFI_PASSWORD);
static SupabaseClient  g_supabase(SUPABASE_URL, SUPABASE_KEY, DEVICE_ID);
#endif

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

#if COMMUNICATION_MODE == COMMUNICATION_MODE_SUPABASE
    g_wifi.begin();
    g_supabase.setSerialManager(&g_serial);
    g_supabase.setSensor(&g_dht);
    g_supabase.begin();
#endif
}

// ============================================================================
// loop()  —  runs continuously
// ============================================================================

void loop() {
    g_serial.update();
    g_light.update();
    g_buzzer.update();
    g_dht.update();

#if COMMUNICATION_MODE == COMMUNICATION_MODE_SUPABASE
    g_wifi.update();
    g_supabase.update();
#endif
}
