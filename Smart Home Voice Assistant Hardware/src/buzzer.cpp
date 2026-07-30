#include "buzzer.h"

#include <Arduino.h>

// Pattern timing constants  (milliseconds)
static constexpr uint16_t SUCCESS_MS    = 100;
static constexpr uint16_t ERROR_MS      = 100;
static constexpr uint16_t ERROR_GAP_MS  = 100;
static constexpr uint8_t  ERROR_COUNT   = 3;
static constexpr uint16_t WARNING_MS    = 700;

// ---------------------------------------------------------------------------
// Construction & initialisation
// ---------------------------------------------------------------------------

Buzzer::Buzzer(uint8_t pin)
    : m_pin(pin)
    , m_pattern(Pattern::IDLE)
    , m_output(false)
    , m_beepsRemaining(0)
    , m_onDurationMs(0)
    , m_offDurationMs(0)
    , m_lastToggleMs(0) {}

void Buzzer::begin() {
    pinMode(m_pin, OUTPUT);
    setOutput(false);
}

// ---------------------------------------------------------------------------
// update()  —  advance the FSM  (call from loop())
// ---------------------------------------------------------------------------

void Buzzer::update() {
    if (m_pattern == Pattern::IDLE) return;
    updatePattern(millis());
}

// ---------------------------------------------------------------------------
// Public sound-pattern API
// ---------------------------------------------------------------------------

void Buzzer::success() {
    startPattern(SUCCESS_MS, 0, 1);
}

void Buzzer::error() {
    startPattern(ERROR_MS, ERROR_GAP_MS, ERROR_COUNT);
}

void Buzzer::warning() {
    startPattern(WARNING_MS, 0, 1);
}

void Buzzer::stop() {
    m_pattern = Pattern::IDLE;
    setOutput(false);
}

bool Buzzer::isPlaying() const {
    return m_pattern != Pattern::IDLE;
}

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

void Buzzer::setOutput(bool on) {
    m_output = on;
    digitalWrite(m_pin, on ? HIGH : LOW);
}

void Buzzer::toggle(unsigned long now) {
    m_output = !m_output;
    digitalWrite(m_pin, m_output ? HIGH : LOW);
    m_lastToggleMs = now;
}

void Buzzer::startPattern(uint16_t onMs, uint16_t offMs, uint8_t beeps) {
    m_pattern        = Pattern::ON;
    m_onDurationMs   = onMs;
    m_offDurationMs  = offMs;
    m_beepsRemaining = beeps;
    m_lastToggleMs   = millis();

    setOutput(true);
}

void Buzzer::updatePattern(unsigned long now) {
    switch (m_pattern) {
        case Pattern::ON:
            if (now - m_lastToggleMs < m_onDurationMs) break;

            toggle(now);
            --m_beepsRemaining;

            if (m_beepsRemaining > 0) {
                m_pattern = Pattern::OFF;
            } else {
                m_pattern = Pattern::IDLE;
                setOutput(false);
            }
            break;

        case Pattern::OFF:
            if (now - m_lastToggleMs < m_offDurationMs) break;

            toggle(now);
            m_pattern = Pattern::ON;
            break;

        case Pattern::IDLE:
            break;
    }
}
