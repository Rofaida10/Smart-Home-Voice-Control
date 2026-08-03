import serial
import time
import threading


class ArduinoController:
    def __init__(self, port='COM3', baudrate=9600, timeout=2):
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

    @property
    def is_connected(self):
        return self.connected and self.serial and self.serial.is_open