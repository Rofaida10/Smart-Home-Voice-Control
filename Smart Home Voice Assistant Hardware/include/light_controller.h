#ifndef LIGHT_CONTROLLER_H
#define LIGHT_CONTROLLER_H

#include <cstdint>

class LightController {
public:
    /** @brief  Pin configuration matching main.cpp initialisation order. */
    struct Config {
        uint8_t pinBuiltin;
        uint8_t pinWifi;
        uint8_t pinVoice;
        uint8_t pinError;
    };

    /** @brief  Construct with pin config.  Does not touch hardware yet. */
    explicit LightController(const Config &cfg);

    /** @brief  Initialise every GPIO as output and set all LEDs OFF. */
    void begin();

    /**
     * @brief  Call from loop() — advances every active blink state machine.
     *         Non-blocking, returns immediately when no LED is blinking.
     */
    void update();

    // -- Static control  (cancels any active blink on that LED) -----------

    /** @brief  Turn the Auth LED ON. */
    void authOn();
    /** @brief  Turn the Auth LED OFF. */
    void authOff();

    /** @brief  Turn the Light LED ON. */
    void lightOn();
    /** @brief  Turn the Light LED OFF. */
    void lightOff();

    /** @brief  Turn the Music LED ON. */
    void musicOn();
    /** @brief  Turn the Music LED OFF. */
    void musicOff();

    /** @brief  Turn every LED ON. */
    void allOn();
    /** @brief  Turn every LED OFF. */
    void allOff();

    // -- Blink sequences  (non-blocking) ----------------------------------

    /**
     * @brief  Blink the Auth LED  (non-blocking).
     * @param  times  Number of full ON–OFF cycles.  Ignored when 0.
     */
    void blinkAuth(uint8_t times);

    /** @copydoc blinkAuth */
    void blinkLight(uint8_t times);

    /** @copydoc blinkAuth */
    void blinkMusic(uint8_t times);

    // -- State queries ----------------------------------------------------

    /** @return true if the Auth LED is physically lit right now. */
    bool isAuthOn() const;

    /** @return true if the Light LED is physically lit right now. */
    bool isLightOn() const;

    /** @return true if the Music LED is physically lit right now. */
    bool isMusicOn() const;

private:
    /// Per-LED operating mode.
    enum class LedMode : uint8_t {
        OFF,    ///< Output forced LOW.
        ON,     ///< Output forced HIGH.
        BLINK   ///< Output toggles at a fixed interval.
    };

    static constexpr uint8_t LED_COUNT = 3;

    enum Id : uint8_t { ID_AUTH = 0, ID_LIGHT, ID_MUSIC };

    struct LedState {
        uint8_t       pin;
        LedMode       mode;
        bool          output;               // Current GPIO line state
        uint8_t       remainingTransitions; // Toggles left in a blink sequence
        unsigned long lastToggleMs;
        unsigned long intervalMs;
    };

    LedState m_leds[LED_COUNT];

    // -- Helpers ----------------------------------------------------------

    /** Set a single LED to a static mode (OFF or ON) and update the pin. */
    void setLedState(uint8_t id, LedMode mode);

    /** Toggle the GPIO and record the timestamp. */
    void toggleLed(uint8_t id, unsigned long now);

    /** Advance one step of the blink state machine for one LED. */
    void updateLed(uint8_t id, unsigned long now);

    /** Start a non-blocking blink sequence.  No-op when times == 0. */
    void startBlink(uint8_t id, uint8_t times);
};

#endif  // LIGHT_CONTROLLER_H
