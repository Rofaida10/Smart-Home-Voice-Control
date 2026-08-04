import serial
import time
import threading


class ArduinoController:
    def __init__(self, port='COM3', baudrate=115200, timeout=2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        self.connected = False
        self.authenticated = False
        self.lock = threading.Lock()

    def connect(self):
        """Establish connection to ESP32 / Arduino"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            time.sleep(2)  # Wait for ESP32/Arduino to reset
            self.connected = True
            print(f"Connected to Arduino on {self.port} at {self.baudrate} baud")
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
            self.authenticated = False
            print("Disconnected from Arduino")

    def authenticate(self, passphrase="esp32"):
        """Send AUTH command to ESP32 to unlock command processing"""
        if not self.connected or not self.serial:
            return False
            
        auth_cmd = f"AUTH {passphrase}"
        response = self.send_command(auth_cmd)
        if response:
            self.authenticated = True
            print("ESP32 Authentication Successful!")
            return True
        return False

    def send_command(self, command):
        """
        Send command to Arduino/ESP32.
        Converts spaces to commands expected by SerialManager (e.g. LIGHT ON).
        """
        if not self.connected or not self.serial:
            print("Arduino not connected")
            return None

        # Format input string properly (e.g., LIGHT_ON -> LIGHT ON)
        formatted_cmd = command.strip().upper().replace("_", " ")

        try:
            with self.lock:
                # Flush existing buffer
                self.serial.reset_input_buffer()
                
                # Write command with newline
                self.serial.write(f"{formatted_cmd}\n".encode('utf-8'))
                time.sleep(0.15)
                
                # Read response
                response = ""
                if self.serial.in_waiting > 0:
                    response = self.serial.readline().decode('utf-8', errors='ignore').strip()
                
                print(f"Sent: '{formatted_cmd}' | Received: '{response}'")
                return response if response else "OK"
        except Exception as e:
            print(f"Send command error: {str(e)}")
            return None

    def read_temperature(self):
        """Read temperature from ESP32 using 'TEMP' command"""
        response = self.send_command("TEMP")
        if response:
            try:
                # Extracts numeric value if response format includes text or direct float
                for token in response.split():
                    try:
                        return float(token)
                    except ValueError:
                        continue
            except Exception as e:
                print(f"Temperature parsing error: {e}")
        return None

    @property
    def is_connected(self):
        return self.connected and self.serial and self.serial.is_open
