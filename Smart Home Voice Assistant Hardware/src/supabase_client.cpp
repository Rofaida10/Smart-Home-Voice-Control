#include "communication_config.h"

// This translation unit compiles to an empty unit unless SUPABASE mode is on,
// so SERIAL-only builds pull in no WiFi/TLS/JSON code at all.
#if COMMUNICATION_MODE == COMMUNICATION_MODE_SUPABASE

#include "supabase_client.h"
#include "serial_manager.h"
#include "dht_sensor.h"

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#include <cmath>
#include <cstring>
#include <time.h>

SupabaseClient::SupabaseClient(const char *url, const char *key, const char *deviceId)
    : m_url(url)
    , m_key(key)
    , m_deviceId(deviceId)
    , m_client(nullptr)
    , m_serial(nullptr)
    , m_sensor(nullptr)
    , m_lastPollMs(0)
    , m_lastTelemetryMs(0)
    , m_retryUntilMs(0) {}

bool SupabaseClient::begin() {
    return ensureClient();
}

bool SupabaseClient::ensureClient() {
    if (m_client != nullptr) return true;

    m_client = new WiFiClientSecure();
    if (m_client == nullptr) {
        Serial.println("[Supabase] ensureClient: out of memory");
        return false;
    }

    // Trust any HTTPS peer. Supabase serves a valid cert from a public CA;
    // pinning the root CA is a future hardening step (see report).
    m_client->setInsecure();
    return true;
}

void SupabaseClient::teardownClient() {
    if (m_client != nullptr) {
        m_client->stop();
        delete m_client;
        m_client = nullptr;
    }
}

void SupabaseClient::setSerialManager(SerialManager *mgr) {
    m_serial = mgr;
}

void SupabaseClient::setSensor(DHTSensor *sensor) {
    m_sensor = sensor;
}

void SupabaseClient::update() {
    if (m_serial == nullptr) return;

    unsigned long const now = millis();
    if (now < m_retryUntilMs) return;                 // backoff after connection failure
    if (now - m_lastPollMs < SUPABASE_POLL_INTERVAL_MS) return;
    m_lastPollMs = now;

    if (WiFi.status() != WL_CONNECTED) return;        // WiFiManager owns reconnection

    pollCommand();
    uploadTelemetry(now);
}

void SupabaseClient::uploadTelemetry(unsigned long now) {
    if (now - m_lastTelemetryMs < SUPABASE_TELEMETRY_INTERVAL_MS) return;
    m_lastTelemetryMs = now;

    if (m_sensor == nullptr || !m_sensor->hasValidReading()) return;

    float const temperature = m_sensor->getTemperature();
    if (std::isfinite(temperature)) {
        postTemperature(temperature);
    }
}

bool SupabaseClient::pollCommand() {
    if (!ensureClient()) return false;

    String url = String(m_url) + "/rest/v1/" + SUPABASE_COMMANDS_TABLE;
    url += "?device_id=eq." + String(m_deviceId);
    url += "&or=(processed.is.null,processed.eq.false)";
    url += "&order=created_at.asc,id.asc";
    url += "&limit=1";

    HTTPClient http;
    if (!http.begin(*m_client, url)) {
        Serial.println("[Supabase] poll: begin() failed");
        return false;
    }
    http.addHeader("apikey", m_key);
    http.addHeader("Authorization", String("Bearer ") + m_key);
    http.setTimeout(SUPABASE_HTTP_TIMEOUT_MS);

    int const code = http.GET();
    String response = (code == HTTP_CODE_OK) ? http.getString() : String();
    http.end();

    if (code < 0) {
        // Connection-level failure (TLS handshake abort, socket reset, ...).
        // A failed handshake can leave the mbedTLS context in a bad state, so
        // drop the client and let the next poll allocate a fresh one. Back off
        // so a dead network doesn't hammer the TLS stack every poll interval.
        Serial.printf("[Supabase] poll: connection failed (code %d) — recreating TLS client\n", code);
        teardownClient();
        m_retryUntilMs = millis() + SUPABASE_TLS_BACKOFF_MS;
        return false;
    }

    if (code != HTTP_CODE_OK) {
        Serial.printf("[Supabase] poll: HTTP %d\n", code);
        return false;
    }

    JsonDocument doc;
    DeserializationError const err = deserializeJson(doc, response);
    if (err) {
        Serial.printf("[Supabase] poll: JSON parse error: %s\n", err.c_str());
        return false;
    }

    if (!doc.is<JsonArray>() || doc.size() == 0) return true;

    JsonObject const row = doc[0];
    char const *const command = row["command"] | "";
    char const *const rowId   = row["id"] | "";
    bool const        done    = row["processed"] | false;

    if (command[0] == '\0' || done) return true;

    Serial.printf("[Supabase] received command: '%s'\n", command);
    m_serial->executeLine(command);

    if (strcmp(command, "TEMP") == 0) {
        float const temp = m_serial->getLastTemperature();
        if (std::isfinite(temp)) {
            postTemperature(temp);
        } else {
            Serial.println("[Supabase] TEMP: no valid reading — telemetry not posted");
        }
    }

    if (rowId[0] == '\0') {
        Serial.println("[Supabase] poll: command row has no 'id' — cannot mark processed");
        return true;
    }
    markProcessed(rowId);
    return true;
}

bool SupabaseClient::markProcessed(const char *rowId) {
    String url = String(m_url) + "/rest/v1/" + SUPABASE_COMMANDS_TABLE
               + "?id=eq." + String(rowId);

    HTTPClient http;
    if (!http.begin(*m_client, url)) return false;
    http.addHeader("apikey", m_key);
    http.addHeader("Authorization", String("Bearer ") + m_key);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Prefer", "return=minimal");
    http.setTimeout(SUPABASE_HTTP_TIMEOUT_MS);

    int const code = http.PATCH("{\"processed\":true}");
    bool const ok = (code == HTTP_CODE_OK || code == HTTP_CODE_NO_CONTENT);
    if (!ok) Serial.printf("[Supabase] markProcessed: HTTP %d\n", code);
    http.end();
    return ok;
}

bool SupabaseClient::postTemperature(float temperature) {
    time_t const now = time(nullptr);
    if (now < 100000) {
        Serial.println("[Supabase] telemetry: clock not synchronized — skipping post");
        return false;
    }

    char ts[32];
    {
        struct tm tmv;
        gmtime_r(&now, &tmv);
        strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &tmv);
    }

    JsonDocument doc;
    JsonObject obj = doc.to<JsonArray>().add<JsonObject>();
    obj["device_id"]  = m_deviceId;
    obj["temperature"] = temperature;
    obj["created_at"]  = ts;

    String payload;
    serializeJson(doc, payload);

    String url = String(m_url) + "/rest/v1/" + SUPABASE_TELEMETRY_TABLE;

    HTTPClient http;
    if (!http.begin(*m_client, url)) return false;
    http.addHeader("apikey", m_key);
    http.addHeader("Authorization", String("Bearer ") + m_key);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Prefer", "return=minimal");
    http.setTimeout(SUPABASE_HTTP_TIMEOUT_MS);

    int const code = http.POST(payload);
    bool const ok = (code == HTTP_CODE_OK || code == HTTP_CODE_CREATED || code == HTTP_CODE_NO_CONTENT);
    if (ok) {
        Serial.printf("[Supabase] telemetry posted: %.1f C\n", temperature);
    } else {
        Serial.printf("[Supabase] postTelemetry: HTTP %d\n", code);
    }
    http.end();
    return ok;
}

#endif  // COMMUNICATION_MODE == COMMUNICATION_MODE_SUPABASE
