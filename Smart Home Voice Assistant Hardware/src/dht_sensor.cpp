#include "dht_sensor.h"
#include "config.h"

#include <Arduino.h>

// ---------------------------------------------------------------------------
// Construction  —  DHT object is constructed from the Config in the
//                  initialiser list; no dynamic allocation is used.
// ---------------------------------------------------------------------------

DHTSensor::DHTSensor(const Config &cfg)
    : m_dht(cfg.pin, cfg.type)
    , m_lastTemperature(NAN)
    , m_lastHumidity(NAN)
    , m_validReading(false)
    , m_lastPollTime(0)
    , m_lastSuccessfulRead(0) {}

// ---------------------------------------------------------------------------
// begin()  —  hands control to the Adafruit library
// ---------------------------------------------------------------------------

void DHTSensor::begin() {
    m_dht.begin();
}

// ---------------------------------------------------------------------------
// update()  —  non-blocking poll at DHT_POLL_INTERVAL_MS
// ---------------------------------------------------------------------------

void DHTSensor::update() {
    unsigned long const now = millis();
    if (now - m_lastPollTime < DHT_POLL_INTERVAL_MS) return;
    m_lastPollTime = now;

    float temperature = NAN;
    float humidity    = NAN;

    if (readSensor(temperature, humidity)) {
        updateCache(temperature, humidity);
        m_lastSuccessfulRead = now;
    }
    // On failure: cache is untouched, previous valid values are preserved.
}

// ---------------------------------------------------------------------------
// readNow()  —  on-demand read, returns the temperature directly
// ---------------------------------------------------------------------------

float DHTSensor::readNow() {
    float temperature = NAN;
    float humidity    = NAN;

    if (readSensor(temperature, humidity)) {
        updateCache(temperature, humidity);
        m_lastSuccessfulRead = millis();
        return temperature;
    }
    return m_lastTemperature;   // last valid value, or NaN if never read
}

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------

float DHTSensor::getTemperature() const {
    return m_lastTemperature;
}

float DHTSensor::getHumidity() const {
    return m_lastHumidity;
}

bool DHTSensor::hasValidReading() const {
    return m_validReading;
}

unsigned long DHTSensor::lastUpdateTime() const {
    return m_lastSuccessfulRead;
}

bool DHTSensor::isDataValid() const {
    return m_validReading;
}

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

bool DHTSensor::readSensor(float &temperature, float &humidity) {
    temperature = m_dht.readTemperature();
    humidity    = m_dht.readHumidity();
    return !isnan(temperature) && !isnan(humidity);
}

void DHTSensor::updateCache(float temperature, float humidity) {
    m_lastTemperature = temperature;
    m_lastHumidity    = humidity;
    m_validReading    = true;
}
