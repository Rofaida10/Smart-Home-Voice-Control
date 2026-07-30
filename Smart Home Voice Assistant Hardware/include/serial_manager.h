#ifndef SERIAL_MANAGER_H
#define SERIAL_MANAGER_H

#include <cstddef>
#include <cstdint>

class LightController;
class Buzzer;
class DHTSensor;

class SerialManager {
public:
    /** @brief  Hardware configuration  (baud rate, buffer hint). */
    struct Config {
        unsigned long baud;
        size_t        rx_buffer_size;   // retained for main.cpp compatibility
    };

    /** @brief  Construct the serial coordinator. */
    explicit SerialManager(const Config &cfg);

    /** @brief  Open the UART at the configured baud rate. */
    void begin();

    /**
     * @brief  Poll the UART, parse any incoming command, and dispatch.
     *         Non-blocking — call every iteration of loop().
     */
    void update();

    // -- Subsystem injection (set before loop() begins) -------------------

    void setLightController(LightController *ctrl);
    void setBuzzer(Buzzer *buzzer);
    void setDHTSensor(DHTSensor *sensor);

private:
    // -- Constants --------------------------------------------------------

    static constexpr size_t BUFFER_SIZE = 64;

    // -- Command model ----------------------------------------------------

    enum class CommandType : uint8_t {
        AUTH,
        LIGHT,
        MUSIC,
        TEMP,
        STATUS,
        UNKNOWN
    };

    struct Command {
        CommandType type;
        char        argument1[20];
        char        argument2[20];
    };

    // -- State ------------------------------------------------------------

    unsigned long     m_baud;
    LightController  *m_light;
    Buzzer           *m_buzzer;
    DHTSensor        *m_sensor;

    char    m_buffer[BUFFER_SIZE];
    size_t  m_bufferPos;
    bool    m_commandReady;
    bool    m_authenticated;
    Command m_cmd;

    // -- Serial I/O -------------------------------------------------------

    /** Read bytes from UART into the line buffer until '\n'. */
    void readSerial();

    /** Convert the entire line buffer to uppercase for case-insensitive matching. */
    void toUpper();

    /** Split the buffer into a Command struct (no strtok). */
    void parseCommand();

    /** Dispatch the parsed command to the appropriate handler. */
    void executeCommand();

    // -- Response helpers -------------------------------------------------

    void sendOK(const char *msg);
    void sendError(const char *msg);
    void sendStatus();
    void sendTemperature();

    // -- Command handlers -------------------------------------------------

    void handleAuth();
    void handleLight();
    void handleMusic();
};

#endif  // SERIAL_MANAGER_H
