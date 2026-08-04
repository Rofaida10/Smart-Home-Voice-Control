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
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            time.sleep(2) 
            self.connected = True
            print(f"Connected to ESP32 on {self.port} at {self.baudrate} baud")
            return True
        except Exception as e:
            print(f"ESP32 connection error: {str(e)}")
            self.connected = False
            return False

    def disconnect(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.connected = False
            self.authenticated = False
            print("Disconnected from ESP32")

    def authenticate(self, passphrase="esp32"):
 
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
  
        if not self.connected or not self.serial:
            print("ESP32 not connected")
            return None

        # تحويل "light_on" أو "LIGHT_ON" إلى "LIGHT ON"
        formatted_cmd = str(command).strip().upper().replace("_", " ")

        try:
            with self.lock:
                self.serial.reset_input_buffer()
                self.serial.write(f"{formatted_cmd}\n".encode('utf-8'))
                time.sleep(0.15)
                
                response = ""
                if self.serial.in_waiting > 0:
                    response = self.serial.readline().decode('utf-8', errors='ignore').strip()
                
                print(f"Sent: '{formatted_cmd}' | Received: '{response}'")
                return response if response else "OK"
        except Exception as e:
            print(f"Send command error: {str(e)}")
            return None

    def read_temperature(self):
        response = self.send_command("TEMP")
        if response:
            try:
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
