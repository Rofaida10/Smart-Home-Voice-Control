import serial
import time
import threading
import re


class ArduinoController:
    def __init__(self, port='COM3', baudrate=115200, timeout=2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        self.connected = False
        self.lock = threading.Lock()
        self.authenticated = False

    def connect(self):
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            time.sleep(2)
            self.connected = True
            print(f"Connected to ESP32 on {self.port}")
            self.authenticate()
            return True
        except Exception as e:
            print(f"ESP32 connection error: {str(e)}")
            self.connected = False
            return False

    def authenticate(self, password="esp32"):
        if not self.connected:
            return False

        try:
            with self.lock:
                self.serial.write(f"AUTH {password}\n".encode())
                time.sleep(0.5)
                response = self._read_response()
                if response and "AUTH_OK" in response:
                    self.authenticated = True
                    print("Authentication successful!")
                    return True
                else:
                    print(f"Authentication failed: {response}")
                    return False
        except Exception as e:
            print(f"Auth error: {str(e)}")
            return False

    def _read_response(self, timeout=1.0):
        start_time = time.time()
        response = ""
        while time.time() - start_time < timeout:
            if self.serial.in_waiting > 0:
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    response = line
                    break
            time.sleep(0.05)
        return response

    def send_command(self, command):
        if not self.connected or not self.authenticated:
            print("Not connected or authenticated")
            return None

        try:
            with self.lock:
                esp32_command = self._convert_command(command)
                if not esp32_command:
                    return None

                self.serial.write(f"{esp32_command}\n".encode())
                time.sleep(0.3)
                response = self._read_response()
                print(f"Command: {esp32_command} → Response: {response}")
                return response
        except Exception as e:
            print(f"Send command error: {str(e)}")
            return None

    def _convert_command(self, command):
        command_map = {
            "LIGHT_ON": "LIGHT ON",
            "LIGHT_OFF": "LIGHT OFF",
            "MUSIC_ON": "MUSIC PLAY",
            "MUSIC_OFF": "MUSIC STOP",
        }
        return command_map.get(command, None)

    def read_temperature(self):
        if not self.connected or not self.authenticated:
            return None

        try:
            with self.lock:
                self.serial.write(b"TEMP\n")
                time.sleep(0.5)
                response = self._read_response()
                if response and response.startswith("TEMP"):
                    parts = response.split()
                    if len(parts) >= 3:
                        try:
                            temp = float(parts[1])
                            humidity = float(parts[2])
                            return {"temperature": temp, "humidity": humidity}
                        except:
                            pass
                return None
        except Exception as e:
            print(f"Temperature read error: {str(e)}")
            return None

    def get_status(self):
        if not self.connected or not self.authenticated:
            return None

        try:
            with self.lock:
                self.serial.write(b"STATUS\n")
                time.sleep(0.5)
                status = {}
                lines = []
                start_time = time.time()
                while time.time() - start_time < 1.0:
                    if self.serial.in_waiting > 0:
                        line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            lines.append(line)
                    time.sleep(0.05)

                for line in lines:
                    if '=' in line:
                        key, value = line.split('=', 1)
                        status[key.strip()] = value.strip()

                return status
        except Exception as e:
            print(f"Status error: {str(e)}")
            return None

    def disconnect(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.connected = False
            self.authenticated = False
            print("Disconnected from ESP32")

    @property
    def is_connected(self):
        return self.connected and self.serial and self.serial.is_open