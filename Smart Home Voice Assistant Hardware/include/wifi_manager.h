#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

/**
 * @brief  WiFi connectivity helper for the ESP32.
 *
 * Responsibilities: station-mode connect, automatic reconnect, and NTP time
 * synchronisation (required so TLS certificate validity checks behave and so
 * telemetry rows carry trustworthy UTC timestamps).
 *
 * Contains no application logic — purely connectivity.
 */

class WiFiManager {
public:
    /** @param ssid  WiFi network name  @param password  WiFi passphrase */
    WiFiManager(const char *ssid, const char *password);

    /** Connect to the configured network (blocking, bounded by timeout). */
    void begin();

    /** @return true while the station is connected to the AP. */
    bool isConnected() const;

    /**
     * @brief  Reconnect in the background if the link dropped.
     *         Call every iteration of loop().
     */
    void update();

    /** Synchronise the system clock via NTP (blocking, bounded). */
    void syncNTP();

private:
    bool connect();

    const char   *m_ssid;
    const char   *m_password;
    bool          m_ntpSynced;
    unsigned long m_lastAttemptMs;
};

#endif  // WIFI_MANAGER_H
