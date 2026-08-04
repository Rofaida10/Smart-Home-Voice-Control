#include "serial_manager.h"
#include "light_controller.h"
#include "buzzer.h"
#include "dht_sensor.h"
#include "config.h"

#include <Arduino.h>
#include <cstring>

// ---------------------------------------------------------------------------
// Construction & initialisation
// ---------------------------------------------------------------------------

SerialManager::SerialManager(const Config &cfg)
    : m_baud(cfg.baud)
    , m_light(nullptr)
    , m_buzzer(nullptr)
    , m_sensor(nullptr)
    , m_bufferPos(0)
    , m_commandReady(false)
    , m_authenticated(false) {

    m_cmd.type = CommandType::UNKNOWN;
    m_cmd.argument1[0] = '\0';
    m_cmd.argument2[0] = '\0';
}

void SerialManager::begin() {
    Serial.begin(m_baud);
}

// ---------------------------------------------------------------------------
// update()  —  poll UART → parse → dispatch
// ---------------------------------------------------------------------------

void SerialManager::update() {
    readSerial();

    if (m_commandReady) {
        m_commandReady = false;
        m_buffer[m_bufferPos] = '\0';

        toUpper();
        parseCommand();
        executeCommand();

        m_bufferPos = 0;
        m_buffer[0] = '\0';
    }
}

// ---------------------------------------------------------------------------
// Subsystem injection
// ---------------------------------------------------------------------------

void SerialManager::setLightController(LightController *ctrl) { m_light = ctrl; }
void SerialManager::setBuzzer(Buzzer *buzzer)                 { m_buzzer = buzzer; }
void SerialManager::setDHTSensor(DHTSensor *sensor)           { m_sensor = sensor; }

// ===========================================================================
// Serial I/O
// ===========================================================================

// ---------------------------------------------------------------------------
// Read bytes into the fixed-size line buffer.
// ---------------------------------------------------------------------------

void SerialManager::readSerial() {
    while (Serial.available() > 0) {
        char const c = static_cast<char>(Serial.read());

        if (c == '\n' || c == '\r') {
            if (m_bufferPos > 0) {
                m_commandReady = true;
                break;  // process one command per update() call
            }
        } else if (m_bufferPos < BUFFER_SIZE - 1) {
            m_buffer[m_bufferPos++] = c;
        }
    }
}

// ---------------------------------------------------------------------------
// Convert the buffer to uppercase  (ASCII only).
// ---------------------------------------------------------------------------

void SerialManager::toUpper() {
    for (size_t i = 0; m_buffer[i] != '\0'; ++i) {
        if (m_buffer[i] >= 'a' && m_buffer[i] <= 'z') {
            m_buffer[i] -= 32;
        }
    }
}

// ---------------------------------------------------------------------------
// Lightweight command parser  (no strtok).
// ---------------------------------------------------------------------------

void SerialManager::parseCommand() {
    m_cmd.type = CommandType::UNKNOWN;
    m_cmd.argument1[0] = '\0';
    m_cmd.argument2[0] = '\0';

    // --- skip leading spaces ------------------------------------------------

    char const *p = m_buffer;
    while (*p == ' ') ++p;
    if (*p == '\0') return;

    // --- extract the command word (first token) -----------------------------

    char const *cmdStart = p;
    while (*p != '\0' && *p != ' ') ++p;
    size_t const cmdLen = static_cast<size_t>(p - cmdStart);

    // --- match command (all uppercase after toUpper()) ----------------------

    if      (cmdLen == 4  && strncmp(cmdStart, "AUTH",  4) == 0) m_cmd.type = CommandType::AUTH;
    else if (cmdLen == 5  && strncmp(cmdStart, "LIGHT", 5) == 0) m_cmd.type = CommandType::LIGHT;
    else if (cmdLen == 5  && strncmp(cmdStart, "MUSIC", 5) == 0) m_cmd.type = CommandType::MUSIC;
    else if (cmdLen == 4  && strncmp(cmdStart, "TEMP",  4) == 0) m_cmd.type = CommandType::TEMP;
    else if (cmdLen == 6  && strncmp(cmdStart, "STATUS",6) == 0) m_cmd.type = CommandType::STATUS;

    // --- skip spaces to argument 1 ------------------------------------------

    while (*p == ' ') ++p;
    if (*p == '\0') return;

    size_t i = 0;
    while (*p != '\0' && *p != ' ' && i < sizeof(m_cmd.argument1) - 1) {
        m_cmd.argument1[i++] = *p++;
    }
    m_cmd.argument1[i] = '\0';

    // --- skip spaces to argument 2 ------------------------------------------

    while (*p == ' ') ++p;
    if (*p == '\0') return;

    i = 0;
    while (*p != '\0' && *p != ' ' && i < sizeof(m_cmd.argument2) - 1) {
        m_cmd.argument2[i++] = *p++;
    }
    m_cmd.argument2[i] = '\0';
}

// ===========================================================================
// Command dispatch
// ===========================================================================

void SerialManager::executeCommand() {
    // All commands except AUTH require prior authentication.
    if (m_cmd.type != CommandType::AUTH && !m_authenticated) {
        sendError("NOT_AUTHENTICATED");
        return;
    }

    switch (m_cmd.type) {
        case CommandType::AUTH:    handleAuth();          break;
        case CommandType::LIGHT:   handleLight();         break;
        case CommandType::MUSIC:   handleMusic();         break;
        case CommandType::TEMP:    sendTemperature();     break;
        case CommandType::STATUS:  sendStatus();          break;
        default:                   sendError("UNKNOWN_COMMAND"); break;
    }
}

// ===========================================================================
// Response helpers
// ===========================================================================

void SerialManager::sendOK(const char *msg) {
    Serial.println(msg);
}

void SerialManager::sendError(const char *msg) {
    Serial.println(msg);
}

// ---------------------------------------------------------------------------
// TEMP  —  "TEMP <temp> <hum>" or "TEMP_ERROR"
// ---------------------------------------------------------------------------

void SerialManager::sendTemperature() {
    if (m_sensor == nullptr || !m_sensor->hasValidReading()) {
        sendError("TEMP_ERROR");
        return;
    }

    char buf[32];
    snprintf(buf, sizeof(buf), "TEMP %.1f %.1f",
             m_sensor->getTemperature(),
             m_sensor->getHumidity());
    Serial.println(buf);
}

// ---------------------------------------------------------------------------
// STATUS  —  multi-line response
// ---------------------------------------------------------------------------

void SerialManager::sendStatus() {
    char buf[48];

    Serial.println("STATUS");

    snprintf(buf, sizeof(buf), "AUTH=%d",  m_authenticated ? 1 : 0);
    Serial.println(buf);

    snprintf(buf, sizeof(buf), "LIGHT=%d",
             (m_light != nullptr && m_light->isLightOn()) ? 1 : 0);
    Serial.println(buf);

    snprintf(buf, sizeof(buf), "MUSIC=%d",
             (m_light != nullptr && m_light->isMusicOn()) ? 1 : 0);
    Serial.println(buf);

    if (m_sensor != nullptr && m_sensor->hasValidReading()) {
        snprintf(buf, sizeof(buf), "TEMP=%.1f", m_sensor->getTemperature());
        Serial.println(buf);
        snprintf(buf, sizeof(buf), "HUM=%.1f",  m_sensor->getHumidity());
        Serial.println(buf);
    } else {
        Serial.println("TEMP=--");
        Serial.println("HUM=--");
    }
}

// ===========================================================================
// Command handlers
// ===========================================================================

// ---------------------------------------------------------------------------
// AUTH <password>
// ---------------------------------------------------------------------------

void SerialManager::handleAuth() {
    if (m_cmd.argument1[0] == '\0') {
        sendError("AUTH_FAILED");
        return;
    }

    if (strcmp(m_cmd.argument1, AUTH_PASSWORD) == 0) {
        m_authenticated = true;
        if (m_light != nullptr) m_light->authOn();
        if (m_buzzer != nullptr) m_buzzer->success();
        sendOK("AUTH_OK");
    } else {
        m_authenticated = false;
        if (m_light != nullptr) m_light->authOff();
        if (m_buzzer != nullptr) m_buzzer->error();
        sendError("AUTH_FAILED");
    }
}

// ---------------------------------------------------------------------------
// LIGHT ON | OFF
// ---------------------------------------------------------------------------

void SerialManager::handleLight() {
    if (m_light == nullptr) {
        sendError("LIGHT_ERROR");
        return;
    }

    if (strcmp(m_cmd.argument1, "ON") == 0) {
        m_light->lightOn();
        sendOK("LIGHT_ON");
    } else if (strcmp(m_cmd.argument1, "OFF") == 0) {
        m_light->lightOff();
        sendOK("LIGHT_OFF");
    } else {
        sendError("UNKNOWN_ARGUMENT");
    }
}

// ---------------------------------------------------------------------------
// MUSIC PLAY | STOP
// ---------------------------------------------------------------------------

void SerialManager::handleMusic() {
    if (m_light == nullptr) {
        sendError("MUSIC_ERROR");
        return;
    }

    if (strcmp(m_cmd.argument1, "PLAY") == 0) {
        m_light->musicOn();
        sendOK("MUSIC_PLAYING");
    } else if (strcmp(m_cmd.argument1, "STOP") == 0) {
        m_light->musicOff();
        sendOK("MUSIC_STOPPED");
    } else {
        sendError("UNKNOWN_ARGUMENT");
    }
}
