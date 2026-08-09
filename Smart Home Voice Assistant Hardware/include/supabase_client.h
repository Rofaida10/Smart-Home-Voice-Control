#ifndef SUPABASE_CLIENT_H
#define SUPABASE_CLIENT_H

/**
 * @brief  Polls a Supabase REST backend for queued commands and posts
 *         telemetry.
 *
 * Workflow (one pass per poll interval):
 *   1. GET  /rest/v1/commands?device_id=eq.<id>&processed=eq.false&order=created_at.asc&limit=1
 *   2. If a row exists, hand its `command` to SerialManager::executeLine()
 *      so every command path shares one parser/handler (same behaviour as USB).
 *   3. If the command was TEMP, POST the DHT reading to /rest/v1/telemetry.
 *   4. PATCH the command row to processed=true (fire-and-forget, non-fatal on failure).
 *
 * HTTPS is enforced. NTP is expected to be synchronised by WiFiManager before
 * the first poll so row timestamps are correct.
 */

class SerialManager;
class DHTSensor;

class SupabaseClient {
public:
    SupabaseClient(const char *url, const char *key, const char *deviceId);

    /** Allocate the secure client. Returns false on allocation failure. */
    bool begin();

    /** Register the executor that runs received commands. */
    void setSerialManager(SerialManager *mgr);

    /** Register the sensor used for periodic telemetry uploads. */
    void setSensor(DHTSensor *sensor);

    /**
     * @brief  Poll for commands, throttled by SUPABASE_POLL_INTERVAL_MS.
     *         Call every iteration of loop().
     */
    void update();

private:
    bool pollCommand();
    bool markProcessed(const char *rowId);
    bool postTelemetry();
    void uploadTelemetry(unsigned long now);

    bool ensureClient();
    void teardownClient();

    const char   *m_url;
    const char   *m_key;
    const char   *m_deviceId;

    class WiFiClientSecure *m_client;
    SerialManager          *m_serial;
    DHTSensor              *m_sensor;

    unsigned long m_lastPollMs;
    unsigned long m_lastTelemetryMs;
    unsigned long m_retryUntilMs;
};

#endif  // SUPABASE_CLIENT_H
