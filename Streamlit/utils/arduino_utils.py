"""
Communication abstraction layer for the Smart Home ESP32.

The application (app.py) talks to a single facade, ``ArduinoController``,
which routes to a transport selected by the ``COMMUNICATION_MODE`` env var:

    COMMUNICATION_MODE=SERIAL   (default)  USB Serial via pyserial
    COMMUNICATION_MODE=SUPABASE            Supabase REST over WiFi (Phase 2)

Switching modes requires NO application/UI changes: every transport exposes
the same public API (connect, disconnect, send_command, read_temperature,
authenticate, is_connected).
"""

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os
import serial
import time
import threading
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_SERIAL = "SERIAL"
_SUPABASE = "SUPABASE"

COMMUNICATION_MODE = os.getenv("COMMUNICATION_MODE", _SERIAL).upper()
if COMMUNICATION_MODE not in (_SERIAL, _SUPABASE):
    raise ValueError(
        f"Invalid COMMUNICATION_MODE '{COMMUNICATION_MODE}'. "
        f"Expected one of: {_SERIAL}, {_SUPABASE}."
    )


# ===========================================================================
# Transport interface  (the shared contract every transport implements)
# ===========================================================================

class CommunicationTransport:
    """Interface contract for all communication transports."""

    mode = None  # transport identifier, e.g. 'SERIAL' / 'SUPABASE'

    def connect(self):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def send_command(self, command):
        raise NotImplementedError

    def read_temperature(self):
        raise NotImplementedError

    def authenticate(self, password):
        raise NotImplementedError

    @property
    def is_connected(self):
        raise NotImplementedError


# ===========================================================================
# Serial transport  (existing pyserial implementation, preserved)
# ===========================================================================

class SerialTransport(CommunicationTransport):
    """USB Serial transport — identical behaviour to the legacy controller."""

    mode = _SERIAL

    def __init__(self, port='COM5', baudrate=9600, timeout=2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        self.connected = False
        self.lock = threading.Lock()

    def connect(self):
        """Establish connection to Arduino"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            time.sleep(2)  # Wait for Arduino to reset
            self.connected = True
            print(f"Connected to Arduino on {self.port}")
            return True
        except Exception as e:
            print(f"Arduino connection error: {str(e)}")
            self.connected = False
            return False

    def disconnect(self):
        """Close serial connection"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.connected = False
            print("Disconnected from Arduino")

    def send_command(self, command):
        """Send command to Arduino"""
        if not self.connected or not self.serial:
            print("Arduino not connected")
            return False

        try:
            with self.lock:
                # Add newline for Arduino's Serial.readString()
                self.serial.write(f"{command}\n".encode())
                time.sleep(0.1)
                print(f"Sent command: {command}")
                return True
        except Exception as e:
            print(f"Send command error: {str(e)}")
            return False

    def read_temperature(self):
        """Read temperature from Arduino"""
        if not self.connected or not self.serial:
            return None

        try:
            with self.lock:
                # Send request for temperature
                self.serial.write(b"TEMP\n")
                time.sleep(0.3)

                # Read response
                if self.serial.in_waiting > 0:
                    response = self.serial.readline().decode('utf-8').strip()
                    try:
                        temp = float(response)
                        return temp
                    except:
                        return None
                return None
        except Exception as e:
            print(f"Temperature read error: {str(e)}")
            return None

    def authenticate(self, password):
        """Send the AUTH command with the given password to the device."""
        if not password:
            print("Authentication skipped: empty password")
            return False
        return self.send_command(f"AUTH {password}")

    @property
    def is_connected(self):
        return self.connected and self.serial and self.serial.is_open


# ===========================================================================
# Supabase transport  (Phase 2 — REST over WiFi)
# ===========================================================================

class SupabaseTransport(CommunicationTransport):
    """Supabase REST transport.

    Credentials are read exclusively from environment variables:
        SUPABASE_URL   e.g. https://xxxx.supabase.co
        SUPABASE_KEY   the anon/service key
        DEVICE_ID      id of the ESP32 device this app talks to

    Commands are queued as rows in the ``commands`` table
    (device_id, command, value, status, created_at). Temperature is read
    from the latest row of the ``telemetry`` table for this device.
    """

    mode = _SUPABASE

    def __init__(self):
        # Lazy import so the SERIAL transport never depends on requests.
        import requests as _requests
        self._requests = _requests

        self.url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        self.key = os.getenv("SUPABASE_KEY", "").strip()
        self.device_id = os.getenv("DEVICE_ID", "").strip()

        missing = []
        if not self.url:
            missing.append("SUPABASE_URL")
        if not self.key:
            missing.append("SUPABASE_KEY")
        if not self.device_id:
            missing.append("DEVICE_ID")
        if missing:
            raise ValueError(
                "SupabaseTransport: missing required environment variable(s): "
                + ", ".join(missing)
            )

        self._session = self._requests.Session()
        self._session.headers.update({
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        })
        self.connected = False

    def connect(self):
        """Verify Supabase connectivity with a lightweight request."""
        try:
            response = self._session.get(f"{self.url}/rest/v1/", timeout=10)
            self.connected = (response.status_code == 200)
            if self.connected:
                print("Connected to Supabase")
            else:
                print(f"Supabase connection error: HTTP {response.status_code}")
            return self.connected
        except Exception as e:
            print(f"Supabase connection error: {str(e)}")
            self.connected = False
            return False

    def disconnect(self):
        """Release network resources."""
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None
        self.connected = False
        print("Disconnected from Supabase")

    def authenticate(self, password):
        """Authentication logic not implemented yet — placeholder."""
        return True

    def send_command(self, command):
        """Insert a pending command row into the Supabase commands table."""
        if not self.connected or self._session is None:
            print("Supabase not connected")
            return False
        if not command:
            return False

        try:
            payload = [{
                "device_id": self.device_id,
                "command": command,
                "value": "",
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }]
            response = self._session.post(
                f"{self.url}/rest/v1/commands",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                timeout=10,
            )
            if response.status_code in (200, 201, 204):
                print(f"Command queued: {command}")
                return True
            print(f"Send command error: HTTP {response.status_code} {response.text[:200]}")
            return False
        except Exception as e:
            print(f"Send command error: {str(e)}")
            return False

    def read_temperature(self):
        """Read the latest telemetry temperature for this device."""
        if not self.connected or self._session is None:
            return None

        try:
            params = {
                "device_id": f"eq.{self.device_id}",
                "select": "temperature",
                "order": "created_at.desc",
                "limit": "1",
            }
            response = self._session.get(
                f"{self.url}/rest/v1/telemetry",
                params=params,
                timeout=10,
            )
            if response.status_code != 200:
                print(f"Temperature read error: HTTP {response.status_code}")
                return None

            rows = response.json()
            if not rows:
                return None
            try:
                return float(rows[0]["temperature"])
            except (KeyError, TypeError, ValueError):
                return None
        except Exception as e:
            print(f"Temperature read error: {str(e)}")
            return None

    @property
    def is_connected(self):
        return bool(self.connected)


# ===========================================================================
# Public facade  (drop-in replacement for the legacy ArduinoController)
# ===========================================================================

class ArduinoController:
    """Facade that routes to the transport selected by COMMUNICATION_MODE.

    The public API is identical to the legacy controller, so app.py and any
    other callers work unchanged in every mode.
    """

    def __init__(self, port='COM5', baudrate=9600, timeout=2):
        self.mode = COMMUNICATION_MODE
        if self.mode == _SUPABASE:
            self._transport = SupabaseTransport()
        else:
            self._transport = SerialTransport(
                port=port,
                baudrate=baudrate,
                timeout=timeout,
            )

    def connect(self):
        """Establish the connection. Returns True on success."""
        return self._transport.connect()

    def disconnect(self):
        """Close the connection."""
        return self._transport.disconnect()

    def send_command(self, command):
        """Send a command string to the device. Returns True on success."""
        return self._transport.send_command(command)

    def read_temperature(self):
        """Request the temperature. Returns a float, or None on failure."""
        return self._transport.read_temperature()

    def authenticate(self, password):
        """Authenticate with the given password."""
        return self._transport.authenticate(password)

    @property
    def is_connected(self):
        """True when the underlying transport is connected."""
        return self._transport.is_connected
