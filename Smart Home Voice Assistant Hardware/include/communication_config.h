#ifndef COMMUNICATION_CONFIG_H
#define COMMUNICATION_CONFIG_H

// ===================== Communication Mode =====================
#define COMMUNICATION_MODE_SERIAL      0
#define COMMUNICATION_MODE_SUPABASE    1

// Select the active communication mode (SERIAL or SUPABASE).
#define COMMUNICATION_MODE COMMUNICATION_MODE_SUPABASE

// ===================== WiFi =====================
// Credentials are supplied at build time via platformio.ini build flags
// (read from the environment). Real values must never be committed.
#ifndef WIFI_SSID
#define WIFI_SSID ""
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD ""
#endif

// ===================== Supabase =====================
// Endpoint + API key supplied at build time via platformio.ini build flags.
#ifndef SUPABASE_URL
#define SUPABASE_URL ""
#endif
#ifndef SUPABASE_KEY
#define SUPABASE_KEY ""
#endif
#ifndef DEVICE_ID
#define DEVICE_ID "esp32-001"
#endif

#define SUPABASE_COMMANDS_TABLE  "commands"
#define SUPABASE_TELEMETRY_TABLE "telemetry"

// ===================== Timing =====================
#define SUPABASE_POLL_INTERVAL_MS 2000
#define SUPABASE_TELEMETRY_INTERVAL_MS 5000
#define SUPABASE_HTTP_TIMEOUT_MS 10000
#define SUPABASE_TLS_BACKOFF_MS 10000
#define WIFI_CONNECT_TIMEOUT_MS 15000
#define WIFI_RETRY_INTERVAL_MS 10000
#define NTP_SYNC_TIMEOUT_MS 8000

#endif
