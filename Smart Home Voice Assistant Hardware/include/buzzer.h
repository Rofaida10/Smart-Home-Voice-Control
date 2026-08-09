#ifndef BUZZER_H
#define BUZZER_H

#include <cstdint>

class Buzzer {
public:
    /** @brief  Construct with the GPIO pin number from config.h. */
    explicit Buzzer(uint8_t pin);

    /** @brief  Configure the GPIO as output and ensure the buzzer is OFF. */
    void begin();

    /**
     * @brief  Advance the active sound pattern.
     *         Non-blocking — call every iteration of loop().
     */
    void update();

    /** @brief  Single short beep  (100 ms).  Non-blocking. */
    void success();

    /** @brief  Three short beeps  (100 ON / 100 OFF × 3).  Non-blocking. */
    void error();

    /** @brief  Single long beep  (700 ms).  Non-blocking. */
    void warning();

    /** @brief  Stop immediately and turn the buzzer OFF. */
    void stop();

    /** @brief  Turn the buzzer ON continuously.  Non-blocking. */
    void on();

    /** @brief  Turn the buzzer OFF immediately. */
    void off();

    /** @return true while a sound pattern (or steady ON) is active. */
    bool isPlaying() const;

private:
    enum class Pattern : uint8_t {
        IDLE,
        ON,
        OFF,
        STEADY
    };

    // -- state ------------------------------------------------------------

    uint8_t       m_pin;
    Pattern       m_pattern;
    bool          m_output;
    uint8_t       m_beepsRemaining;
    uint16_t      m_onDurationMs;
    uint16_t      m_offDurationMs;
    unsigned long m_lastToggleMs;

    // -- helpers ----------------------------------------------------------

    void setOutput(bool on);
    void toggle(unsigned long now);
    void startPattern(uint16_t onMs, uint16_t offMs, uint8_t beeps);
    void updatePattern(unsigned long now);
};

#endif  // BUZZER_H
