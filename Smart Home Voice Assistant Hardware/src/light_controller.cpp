#include "light_controller.h"
#include "config.h"

#include <Arduino.h>

// ---------------------------------------------------------------------------
// Construction  —  store the pin layout from Config
// ---------------------------------------------------------------------------

LightController::LightController(const Config &cfg) {
    uint8_t const pins[LED_COUNT] = {
        static_cast<uint8_t>(cfg.pinBuiltin),  // ID_AUTH
        static_cast<uint8_t>(cfg.pinWifi),     // ID_LIGHT
        static_cast<uint8_t>(cfg.pinVoice)     // ID_MUSIC
    };
    // cfg.pinError is accepted for main.cpp compatibility but unused.

    for (uint8_t i = 0; i < LED_COUNT; ++i) {
        m_leds[i].pin                  = pins[i];
        m_leds[i].mode                 = LedMode::OFF;
        m_leds[i].output               = false;
        m_leds[i].remainingTransitions = 0;
        m_leds[i].lastToggleMs         = 0UL;
        m_leds[i].intervalMs           = 0UL;
    }
}

// ---------------------------------------------------------------------------
// begin()  —  initialise GPIOs and place every LED in a known OFF state
// ---------------------------------------------------------------------------

void LightController::begin() {
    for (uint8_t i = 0; i < LED_COUNT; ++i) {
        pinMode(m_leds[i].pin, OUTPUT);
        digitalWrite(m_leds[i].pin, LOW);
    }
}

// ---------------------------------------------------------------------------
// update()  —  non-blocking blink advancement  (call from loop())
// ---------------------------------------------------------------------------

void LightController::update() {
    unsigned long const now = millis();
    for (uint8_t i = 0; i < LED_COUNT; ++i) {
        updateLed(i, now);
    }
}

// ---------------------------------------------------------------------------
// Static control  (each call cancels any active blink on that LED)
// ---------------------------------------------------------------------------

void LightController::authOn()   { setLedState(ID_AUTH,  LedMode::ON);  }
void LightController::authOff()  { setLedState(ID_AUTH,  LedMode::OFF); }

void LightController::lightOn()  { musicOff();  setLedState(ID_LIGHT, LedMode::ON);  }
void LightController::lightOff() { setLedState(ID_LIGHT, LedMode::OFF); }

void LightController::musicOn()  { lightOff();  setLedState(ID_MUSIC, LedMode::ON);  }
void LightController::musicOff() { setLedState(ID_MUSIC, LedMode::OFF); }

void LightController::allOn() {
    for (uint8_t i = 0; i < LED_COUNT; ++i) {
        setLedState(i, LedMode::ON);
    }
}

void LightController::allOff() {
    for (uint8_t i = 0; i < LED_COUNT; ++i) {
        setLedState(i, LedMode::OFF);
    }
}

// ---------------------------------------------------------------------------
// Blink sequences  (non-blocking)
// ---------------------------------------------------------------------------

void LightController::blinkAuth(uint8_t times)   { startBlink(ID_AUTH,  times); }
void LightController::blinkLight(uint8_t times)  { startBlink(ID_LIGHT, times); }
void LightController::blinkMusic(uint8_t times)  { startBlink(ID_MUSIC, times); }

// ---------------------------------------------------------------------------
// State queries
// ---------------------------------------------------------------------------

bool LightController::isAuthOn()  const { return m_leds[ID_AUTH].output;  }
bool LightController::isLightOn() const { return m_leds[ID_LIGHT].output; }
bool LightController::isMusicOn() const { return m_leds[ID_MUSIC].output; }

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

void LightController::setLedState(uint8_t id, LedMode mode) {
    LedState &led = m_leds[id];
    led.mode   = mode;
    led.output = (mode == LedMode::ON);
    digitalWrite(led.pin, led.output ? HIGH : LOW);
}

void LightController::toggleLed(uint8_t id, unsigned long now) {
    LedState &led = m_leds[id];
    led.output = !led.output;
    digitalWrite(led.pin, led.output ? HIGH : LOW);
    led.lastToggleMs = now;
}

void LightController::updateLed(uint8_t id, unsigned long now) {
    LedState &led = m_leds[id];
    if (led.mode != LedMode::BLINK) return;
    if (now - led.lastToggleMs < led.intervalMs) return;

    toggleLed(id, now);

    if (led.remainingTransitions > 0) {
        --led.remainingTransitions;
        if (led.remainingTransitions == 0) {
            setLedState(id, LedMode::OFF);
        }
    }
}

void LightController::startBlink(uint8_t id, uint8_t times) {
    if (times == 0) return;

    LedState &led = m_leds[id];
    led.mode                = LedMode::BLINK;
    led.output              = true;
    led.remainingTransitions = (times * 2) - 1;   // first ON happens here
    led.intervalMs          = DEFAULT_BLINK_INTERVAL_MS;
    led.lastToggleMs        = millis();
    digitalWrite(led.pin, HIGH);
}
