#include "communication_config.h"

// This translation unit compiles to an empty unit unless SUPABASE mode is on,
// so SERIAL-only builds pull in no WiFi/TLS code at all.
#if COMMUNICATION_MODE == COMMUNICATION_MODE_SUPABASE

#include "wifi_manager.h"

#include <Arduino.h>
#include <WiFi.h>
#include <time.h>

WiFiManager::WiFiManager(const char *ssid, const char *password)
    : m_ssid(ssid)
    , m_password(password)
    , m_ntpSynced(false)
    , m_lastAttemptMs(0) {}

void WiFiManager::begin() {
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);          // keep the radio responsive for polling
    connect();
}

bool WiFiManager::isConnected() const {
    return WiFi.status() == WL_CONNECTED;
}

void WiFiManager::update() {
    if (isConnected()) return;

    unsigned long const now = millis();
    if (now - m_lastAttemptMs < WIFI_RETRY_INTERVAL_MS) return;
    m_lastAttemptMs = now;

    Serial.println("[WiFi] link lost — reconnecting...");
    WiFi.disconnect();
    connect();
}

void WiFiManager::syncNTP() {
    configTime(0, 0, "time.google.com", "pool.ntp.org", "time.nist.gov");

    unsigned long const start = millis();
    time_t now = time(nullptr);
    while (now < 100000 && millis() - start < NTP_SYNC_TIMEOUT_MS) {
        delay(500);
        now = time(nullptr);
    }

    if (now >= 100000) {
        m_ntpSynced = true;
        Serial.println("[WiFi] NTP time synchronized");
    } else {
        Serial.println("[WiFi] NTP sync timed out — telemetry timestamps may be stale");
    }
}

bool WiFiManager::connect() {
    if (isConnected()) return true;

    Serial.printf("[WiFi] connecting to '%s'...\n", m_ssid);
    WiFi.begin(m_ssid, m_password);

    unsigned long const start = millis();
    while (!isConnected() && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
        delay(500);
    }

    if (isConnected()) {
        Serial.printf("[WiFi] connected — IP: %s\n", WiFi.localIP().toString().c_str());
        if (!m_ntpSynced) syncNTP();
        return true;
    }

    Serial.println("[WiFi] connection FAILED (will retry)");
    return false;
}

#endif  // COMMUNICATION_MODE == COMMUNICATION_MODE_SUPABASE
