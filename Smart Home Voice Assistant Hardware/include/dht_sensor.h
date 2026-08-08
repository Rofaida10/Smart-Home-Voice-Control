#ifndef DHT_SENSOR_H
#define DHT_SENSOR_H

#include <cstdint>
#include <DHT.h>

class DHTSensor {
public:
    /** @brief  Hardware configuration (pin, sensor type, poll interval). */
    struct Config {
        uint8_t       pin;
        uint8_t       type;
        unsigned long poll_interval_ms;   // retained for main.cpp compatibility
    };

    /** @brief  Construct the sensor wrapper.  Does not touch hardware yet. */
    explicit DHTSensor(const Config &cfg);

    /** @brief  Initialise the DHT hardware driver. */
    void begin();

    /**
     * @brief  Poll the sensor at a fixed interval.
     *         Non-blocking — call every iteration of loop().
     *
     * Reads the DHT when the poll interval has elapsed.
     * On success the temperature, humidity and timestamp caches are updated.
     * On failure the previous valid values are preserved.
     */
    void update();

    /**
     * @brief  Perform an immediate sensor read and return the temperature.
     *
     * Intended for on-demand queries (e.g. the TEMP serial command).  Updates
     * the cache on success; returns the last cached value (or NaN) on failure.
     */
    float readNow();

    /** @return The last successfully-read temperature in °C  (or NaN). */
    float getTemperature() const;

    /** @return The last successfully-read relative humidity in %  (or NaN). */
    float getHumidity() const;

    /** @return true after at least one successful read has been cached. */
    bool  hasValidReading() const;

    /** @return millis() timestamp of the most recent successful read. */
    unsigned long lastUpdateTime() const;

    // -----------------------------------------------------------------------
    // Backward-compatibility aliases  (used by SerialManager)
    // -----------------------------------------------------------------------

    /** @deprecated  Use hasValidReading() instead. */
    bool isDataValid() const;

private:
    DHT           m_dht;
    float         m_lastTemperature;
    float         m_lastHumidity;
    bool          m_validReading;
    unsigned long m_lastPollTime;
    unsigned long m_lastSuccessfulRead;

    /** Read the DHT and populate references.  Returns true on success. */
    bool readSensor(float &temperature, float &humidity);

    /** Store a validated temperature / humidity pair in the cache. */
    void updateCache(float temperature, float humidity);
};

#endif  // DHT_SENSOR_H
