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

# A telemetry row older than this means the device is offline (REST mode).
_STALE_AFTER_SECONDS = 60


def _detect_mode() -> str:
    """Choose the transport automatically.

    - COMMUNICATION_MODE env var wins (explicit override).
    - Otherwise: running on Streamlit Cloud (IS_RUNNING_ON_STREAMLIT_CLOUD)
      with Supabase credentials configured  -> SUPABASE
    - Otherwise (local dev)                  -> SERIAL
    """
    env_mode = os.getenv("COMMUNICATION_MODE")
    if env_mode:
        return env_mode.strip().upper()

    on_cloud = os.getenv("IS_RUNNING_ON_STREAMLIT_CLOUD", "").strip().lower() in ("1", "true", "yes")
    if on_cloud and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"):
        return _SUPABASE
    return _SERIAL


COMMUNICATION_MODE = _detect_mode()
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

    def get_status(self):
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

    def get_status(self):
        """Request the device STATUS and parse the KEY=VALUE response lines.

        Firmware replies (one per line, first line is the literal "STATUS"):
            AUTH=0|1  LIGHT=0|1  MUSIC=0|1  TEMP=..  HUM=..
        Returns a dict like {"auth":"1","light":"0","music":"1","temp":"25.3","hum":"42.1"},
        or None when the device is unreachable / the reply cannot be parsed.
        """
        if not self.connected or not self.serial:
            return None

        try:
            with self.lock:
                self.serial.reset_input_buffer()
                self.serial.write(b"STATUS\n")
                time.sleep(0.3)

                pairs = {}
                deadline = time.time() + self.timeout
                while time.time() < deadline:
                    if self.serial.in_waiting > 0:
                        line = self.serial.readline().decode('utf-8', errors='replace').strip()
                        if "=" in line:
                            key, _, value = line.partition("=")
                            pairs[key] = value
                            if len(pairs) >= 5:
                                break
                    else:
                        time.sleep(0.05)

                if not pairs:
                    return None
                print(f"Device status: {pairs}")
                return pairs
        except Exception as e:
            print(f"Status read error: {str(e)}")
            return None

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
        self.last_seen = None  # epoch of the freshest telemetry row from the device

    @staticmethod
    def _row_age(created_at):
        """Seconds since a telemetry row was created, or None if unparseable."""
        try:
            parsed = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            return time.time() - parsed.timestamp()
        except (TypeError, ValueError):
            return None

    def connect(self):
        """Verify Supabase connectivity with a lightweight request."""
        try:
            response = self._session.get(f"{self.url}/rest/v1/", timeout=10)
            self.connected = (response.status_code == 200)
            if self.connected:
                print("Connected to Supabase")
                self.get_status()  # warm device freshness from the latest telemetry row
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
        """Queue an AUTH command so the device LED/buzzer reacts, like USB mode."""
        if not password:
            print("Authentication skipped: empty password")
            return False
        return self.send_command(f"AUTH {password}")

    def get_status(self):
        """Return the device state from the latest telemetry row.

        The firmware posts light/music/auth/temperature/humidity every
        SUPABASE_TELEMETRY_INTERVAL_MS (5 s). Keys are lowercase to match
        the SerialTransport convention consumed by sync_device_state().
        Also updates `last_seen` so is_connected reflects device freshness.
        Returns None when unreachable or no telemetry has arrived yet.
        """
        if not self.connected or self._session is None:
            return None

        try:
            params = {
                "device_id": f"eq.{self.device_id}",
                "select": "auth,light,music,temperature,humidity,created_at",
                "order": "created_at.desc",
                "limit": "1",
            }
            response = self._session.get(
                f"{self.url}/rest/v1/telemetry",
                params=params,
                timeout=10,
            )
            if response.status_code != 200:
                print(f"Status read error: HTTP {response.status_code}")
                return None

            rows = response.json()
            if not rows:
                return None

            row = rows[0]
            age = self._row_age(row.get("created_at"))
            if age is not None:
                self.last_seen = time.time() - age  # device time, not poll time
            return {
                "auth": row.get("auth"),
                "light": row.get("light"),
                "music": row.get("music"),
                "temperature": row.get("temperature"),
                "humidity": row.get("humidity"),
            }
        except Exception as e:
            print(f"Status read error: {str(e)}")
            return None

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
                "select": "temperature,created_at",
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
                age = self._row_age(rows[0].get("created_at"))
                if age is not None:
                    self.last_seen = time.time() - age
                return float(rows[0]["temperature"])
            except (KeyError, TypeError, ValueError):
                return None
        except Exception as e:
            print(f"Temperature read error: {str(e)}")
            return None

    @property
    def is_connected(self):
        """True only when Supabase is reachable AND the device recently
        posted telemetry — otherwise the UI cannot claim real hardware status."""
        if not self.connected or self._session is None:
            return False
        if self.last_seen is None:
            return False
        return (time.time() - self.last_seen) < _STALE_AFTER_SECONDS


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

    def get_status(self):
        """Request the device state. Returns a dict of KEY=VALUE pairs, or None."""
        return self._transport.get_status()

    def authenticate(self, password):
        """Authenticate with the given password."""
        return self._transport.authenticate(password)

    @property
    def is_connected(self):
        """True when the underlying transport is connected."""
        return self._transport.is_connected
