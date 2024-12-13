import os
import json
import time
from datetime import datetime
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from iota_sdk import Client, utf8_to_hex
import ssl
import csv
import requests
from threading import Thread
import queue
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.dates import DateFormatter, SecondLocator
from cryptography.fernet import Fernet
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pathlib import Path

# Load environment variables
load_dotenv(dotenv_path='../.env')

# Configuration settings for the middleware
class Config:
    TTN_BROKER = "eu1.cloud.thethings.network"
    TTN_PORT = 8883
    TTN_APP_ID = os.getenv('TTN_APP_ID')
    TTN_API_KEY = os.getenv('TTN_API_KEY')
    NODE_URL = os.environ.get('NODE_URL', 'https://api.testnet.shimmer.network')
    EXPLORER_URL = os.environ.get('EXPLORER_URL', 'https://explorer.shimmer.network/testnet')
    VERIFICATION_INTERVAL = 0.1  # 100ms
    MAX_RETRY_ATTEMPTS = 300  # 30 seconds total

# Middleware class for handling TTN to IOTA communication
class Middleware:
    # Initialize middleware
    def __init__(self):
        self.iota_client = Client(nodes=[Config.NODE_URL])
        self.confirmation_queue = queue.Queue()
        self.pending_data_file = Path('pending_data.csv')
        self.connection_status = True
        self.cipher_suite = self._setup_encryption()
    
    # Initialize encryption key
    def _setup_encryption(self):
        """Initialize encryption key"""
        password = os.getenv('ENCRYPTION_KEY', 'default_password').encode()
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return Fernet(key)

    # Encrypt data
    def encrypt_data(self, data):
        """Encrypt data and store metrics"""
        try:
            json_str = json.dumps(data) # Convert data to JSON string
            original_size = len(json_str.encode()) # Original data size
            
            start_time = time.time()
            encrypted_data = self.cipher_suite.encrypt(json_str.encode()) # Encrypt data
            encryption_time = time.time() - start_time
            
            encrypted_size = len(encrypted_data) # Encrypted data size
            
            # Store encryption metrics
            self._store_encryption_metrics(
                'encrypt',
                original_size,
                encrypted_size,
                encryption_time,
                0,
                encryption_time
            )
            
            return encrypted_data
        except Exception as e:
            print(f"Error encrypting data: {str(e)}")
            return None

    # Decrypt data
    def decrypt_data(self, encrypted_data):
        """Decrypt data and store metrics"""
        try:
            encrypted_size = len(encrypted_data) # Encrypted data size
            
            start_time = time.time()
            decrypted_data = self.cipher_suite.decrypt(encrypted_data) # Decrypt data
            decryption_time = time.time() - start_time
            
            original_size = len(decrypted_data) # Original data size
            
            # Store decryption metrics
            self._store_encryption_metrics(
                'decrypt',
                original_size,
                encrypted_size,
                decryption_time,
                0,
                decryption_time
            )
            
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"Error decrypting data: {str(e)}")
            return None

    # Store encryption metrics
    def _store_encryption_metrics(self, operation_type, original_size, encrypted_size, 
                                encryption_time, transmission_time, total_time):
        """Store encryption performance metrics"""
        try:
            file_exists = os.path.isfile('encryption_metrics.csv')
            with open('encryption_metrics.csv', mode='a', newline='') as file:
                writer = csv.writer(file)
                if not file_exists:
                    writer.writerow([
                        'Timestamp', 'Operation', 'Original size (bytes)',
                        'Encrypted size (bytes)', 'Encryption time (s)',
                        'Transmission time (s)', 'Total time (s)'
                    ])
                writer.writerow([
                    datetime.now().isoformat(), operation_type, original_size,
                    encrypted_size, f"{encryption_time:.6f}",
                    f"{transmission_time:.6f}", f"{total_time:.6f}"
                ])
        except Exception as e:
            print(f"Error storing encryption metrics: {str(e)}")

    # Store sensor data and confirmation details
    def store_data(self, block_id, sensor_data, ttn_time=None, confirmation_time=None):
        """Store sensor data and confirmation details"""
        try:
            file_exists = os.path.isfile('iota_data.csv')
            
            if not confirmation_time:
                with open('iota_data.csv', mode='a', newline='') as file:
                    writer = csv.writer(file)
                    if not file_exists:
                        writer.writerow([
                            'Block ID', 'Device ID', 'Timestamp', 'AHT10 Temperature', 
                            'AHT10 Humidity', 'DS18B20 Temperature', 'Light level',
                            'Soil moisture', 'TTN time', 'Confirmation time',
                            'Response time', 'Explorer URL', 'Confirmed'
                        ])
                    
                    writer.writerow([
                        block_id, sensor_data["deviceId"], datetime.now().isoformat(),
                        sensor_data["measurements"]["aht10_temperature"],
                        sensor_data["measurements"]["aht10_humidity"],
                        sensor_data["measurements"]["ds18b20_temperature"],
                        sensor_data["measurements"]["light_level"],
                        sensor_data["measurements"]["soil_moisture"],
                        datetime.fromtimestamp(ttn_time).isoformat() if ttn_time else None,
                        None, None,
                        f"{Config.EXPLORER_URL}/block/{block_id}",
                        False
                    ])
            else:
                # Read data from CSV file
                df = pd.read_csv('iota_data.csv', dtype={
                    'Block ID': str,
                    'Device ID': str,
                    'Timestamp': str,
                    'AHT10 Temperature': float,
                    'AHT10 Humidity': float,
                    'DS18B20 Temperature': float,
                    'Light level': float,
                    'Soil moisture': float,
                    'TTN time': str,
                    'Confirmation time': str,
                    'Response time': str,
                    'Explorer URL': str,
                    'Confirmed': bool
                })
                
                mask = df['Block ID'] == block_id
                response_time = confirmation_time - ttn_time
                
                # Update confirmation details
                df.loc[mask, 'Confirmation time'] = datetime.fromtimestamp(confirmation_time).isoformat()
                df.loc[mask, 'Response time'] = str(round(response_time, 2))
                df.loc[mask, 'Confirmed'] = True
                
                df.to_csv('iota_data.csv', index=False)
                print(f"\nResponse time: {response_time:.2f} seconds")
                
        except Exception as e:
            print(f"Error storing data: {str(e)}")

    # Save pending message when offline
    def save_pending_message(self, device_id, sensor_data):
        """Save message to pending queue when offline"""
        try:
            file_exists = self.pending_data_file.exists() # Check if file exists
            
            with self.pending_data_file.open('a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['device_id', 'timestamp', 'sensor_data'])
                
                writer.writerow([
                    device_id,
                    datetime.now().isoformat(),
                    json.dumps(sensor_data)
                ])
            print(f"Message saved for device {device_id}")
        except Exception as e:
            print(f"Error saving pending message: {str(e)}")

    # Load pending messages when back online
    def load_pending_messages(self):
        """Load pending messages when back online"""
        try:
            messages = []
            if self.pending_data_file.exists():
                with self.pending_data_file.open('r', newline='') as f:
                    reader = csv.DictReader(f)
                    messages = list(reader)
                print(f"Loaded {len(messages)} pending messages")
            return messages
        except Exception as e:
            print(f"Error loading pending messages: {str(e)}")
            return []

    # Check network connection
    def check_connection(self):
        """Check if IOTA node is reachable"""
        try:
            response = requests.get(f"{Config.NODE_URL}/health", timeout=1) # Check node health
            return response.status_code == 200
        except Exception:
            return False

    # Send encrypted data to IOTA
    def send_to_iota(self, sensor_data, ttn_time, device_id):
        """Send encrypted data to IOTA"""
        try:
            if not self.check_connection():
                print("\nNetwork unavailable - storing data...")
                self.save_pending_message(device_id, sensor_data) # Save message when offline
                return None

            total_start_time = time.time()
            
            # Encrypt data
            encrypted_data = self.encrypt_data(sensor_data) 
            if not encrypted_data:
                return None
                
            original_size = len(json.dumps(sensor_data).encode()) # Original data size
            encrypted_size = len(encrypted_data) # Encrypted data size
            
            print(f"\nSending encrypted data to IOTA")
            print(f"Original size: {original_size} bytes")
            print(f"Encrypted size: {encrypted_size} bytes")
            
            # Send to IOTA
            transmission_start = time.time()
            block = self.iota_client.build_and_post_block( # Send encrypted data to IOTA
                tag=utf8_to_hex('ENCRYPTED_SENSOR_DATA'),
                data=utf8_to_hex(base64.b64encode(encrypted_data).decode())
            )
            transmission_time = time.time() - transmission_start
            
            total_time = time.time() - total_start_time
            
            block_id = block[0] # Get block ID
            print(f'Block sent! ID: {block_id}')
            
            # Store encryption metrics
            self._store_encryption_metrics(
                'send_encrypted',
                original_size,
                encrypted_size,
                total_time - transmission_time,
                transmission_time,
                total_time
            )
            
            # Add to confirmation queue
            self.confirmation_queue.put((block_id, ttn_time, device_id, sensor_data))
            return block_id
            
        except Exception as e:
            print(f"Error sending to IOTA: {str(e)}")
            self.save_pending_message(device_id, sensor_data)
            return None

    # Process sensor data
    def process_sensor_data(self, payload):
        """Process TTN message into sensor data structure"""
        try:
            return {
                "deviceId": payload["end_device_ids"]["device_id"],
                "timestamp": datetime.now().isoformat(),
                "measurements": {
                    "aht10_temperature": payload["uplink_message"]["decoded_payload"]["v0"],
                    "aht10_humidity": payload["uplink_message"]["decoded_payload"]["v1"],
                    "ds18b20_temperature": payload["uplink_message"]["decoded_payload"]["v2"],
                    "light_level": payload["uplink_message"]["decoded_payload"]["v3"],
                    "soil_moisture": payload["uplink_message"]["decoded_payload"]["v4"]
                },
                "metadata": {
                    "rssi": payload["uplink_message"]["rx_metadata"][0]["rssi"],
                    "snr": payload["uplink_message"]["rx_metadata"][0]["snr"],
                    "frequency": payload["uplink_message"]["settings"]["frequency"],
                    "gateway_id": payload["uplink_message"]["rx_metadata"][0]["gateway_ids"]["gateway_id"]
                }
            }
        except Exception as e:
            print(f"Error processing sensor data: {str(e)}")
            return None

    # Check block confirmation
    def check_block_confirmation(self, block_id, ttn_time, device_id, sensor_data):
        """Check if block is confirmed in Tangle"""
        try:
            response = requests.get(f"{Config.NODE_URL}/api/core/v2/blocks/{block_id}") # Check block confirmation
            if response.status_code == 200: 
                confirmation_time = time.time()
                self.store_data(block_id, sensor_data, ttn_time, confirmation_time) # Store confirmation details
                return True
            return False
        except Exception as e:
            print(f"Error checking block confirmation: {str(e)}")
            return False

    # Plot response times
    def plot_response_times(self):
        """Plot response time metrics"""
        try:
            if not os.path.exists('iota_data.csv'):
                print("No data file found.")
                return
                
            df = pd.read_csv('iota_data.csv')
            df['TTN time'] = pd.to_datetime(df['TTN time'])
            df['Response time'] = pd.to_numeric(df['Response time'])
            
            mean_response = df['Response time'].mean()

            plt.figure(figsize=(10, 5))
            plt.plot(df['TTN time'], df['Response time'], marker='o', label='Response time')
            plt.axhline(y=mean_response, color='r', linestyle='--', 
                       label=f'Mean: {mean_response:.2f}s')
            
            plt.title('Response time: TTN to Tangle')
            plt.xlabel('Time')
            plt.ylabel('Response time (s)')
            plt.grid(True)
            plt.legend()
            
            ax = plt.gca()
            ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
            ax.xaxis.set_major_locator(SecondLocator(interval=3600))
            plt.xticks(rotation=45)
            
            plt.tight_layout()
            plt.savefig('response_times.png', dpi=300)
            print(f"\nMean response time: {mean_response:.2f} seconds")
        except Exception as e:
            print(f"Error creating graph: {str(e)}")

    # Monitor block confirmations
    def confirmation_monitor(self):
        """Monitor block confirmations"""
        while True:
            try:
                block_id, ttn_time, device_id, sensor_data = self.confirmation_queue.get() # Get confirmation details
                attempts = 0
                while attempts < Config.MAX_RETRY_ATTEMPTS: 
                    if self.check_block_confirmation(block_id, ttn_time, device_id, sensor_data): # Check block confirmation
                        break
                    time.sleep(Config.VERIFICATION_INTERVAL)
                    attempts += 1
                if attempts >= Config.MAX_RETRY_ATTEMPTS:
                    print(f"Block {block_id} not confirmed after 30 seconds")
            except Exception as e:
                print(f"Error in confirmation monitor: {str(e)}")
            finally:
                self.confirmation_queue.task_done()

    # Retry sending pending messages
    def retry_monitor(self):
        """Monitor and retry sending pending messages"""
        while True:
            try:
                if self.check_connection(): # Check network connection
                    pending_messages = self.load_pending_messages() # Load pending messages
                    
                    if pending_messages:
                        print("\nConnection available - sending pending messages...")
                        
                        for message in pending_messages: # Retry sending pending messages
                            sensor_data = json.loads(message['sensor_data']) # Load sensor data
                            if self.send_to_iota(sensor_data, time.time(), message['device_id']):
                                continue
                        
                        if self.pending_data_file.exists(): 
                            self.pending_data_file.unlink() # Remove pending messages file
                            print("Pending messages processed")
                
                time.sleep(Config.VERIFICATION_INTERVAL)
                
            except Exception as e:
                print(f"Error in retry monitor: {str(e)}")

    # Monitor connection status
    def connection_monitor(self):
        """Monitor connection status"""
        last_status = True
        
        while True:
            try:
                current_status = self.check_connection() # Check network connection
                self.connection_status = current_status # Update connection status
                
                if current_status != last_status: 
                    if not current_status:
                        print("\n--> Connection lost <--")
                    else:
                        print("\n--> Connection restored <--")
                    
                    last_status = current_status
                
                time.sleep(Config.VERIFICATION_INTERVAL)
                
            except Exception as e:
                print(f"Error in connection monitor: {str(e)}")
                self.connection_status = False

    # Callback for MQTT client connection
    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to TTN"""
        if rc == 0:
            print("Connected to TTN successfully!")
            topic = f"v3/{Config.TTN_APP_ID}@ttn/devices/+/up" # TTN topic
            client.subscribe(topic) # Subscribe to TTN topic
            print(f"Subscribed to topic: {topic}")
        else:
            print(f"Failed to connect to TTN, return code: {rc}")

    # Callback for incoming MQTT messages
    def on_message(self, client, userdata, msg):
        """Process incoming TTN messages"""
        try:
            print("\n=== New message received ===")
            ttn_time = time.time()
            
            payload = json.loads(msg.payload.decode()) # Load message payload
            device_id = payload['end_device_ids']['device_id']
            
            if 'uplink_message' in payload and 'decoded_payload' in payload['uplink_message']:
                sensor_data = self.process_sensor_data(payload) # Process sensor data
                if sensor_data:
                    block_id = self.send_to_iota(sensor_data, ttn_time, device_id) # Send to IOTA
                    if block_id:
                        self.store_data(block_id, sensor_data, ttn_time)
                        print(f"Data sent to IOTA. Monitoring confirmation...")
                    else:
                        print("Failed to send to IOTA")
        except Exception as e:
            print(f"Error processing message: {str(e)}")

    # Start the middleware
    def start(self):
        """Start the middleware"""
        try:
            print("\nStarting TTN to IOTA middleware with encryption and connection handling...")
            
            # Start monitor threads
            Thread(target=self.confirmation_monitor, daemon=True).start()
            Thread(target=self.retry_monitor, daemon=True).start()
            Thread(target=self.connection_monitor, daemon=True).start()
            
            # Setup MQTT client
            client = mqtt.Client(client_id=f"python-bridge-{Config.TTN_APP_ID}-{int(time.time())}")
            client.username_pw_set(Config.TTN_APP_ID, Config.TTN_API_KEY)
            client.tls_set()
            
            client.on_connect = self.on_connect
            client.on_message = self.on_message
            
            print("\nConnecting to TTN...")
            client.connect(Config.TTN_BROKER, Config.TTN_PORT, 60)
            
            print("Starting MQTT loop...")
            client.loop_forever()
            
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.plot_response_times()
        except Exception as e:
            print(f"\nError in middleware: {str(e)}")
        finally:
            client.disconnect()

# Main entry point
def main():
    """Main entry point"""
    middleware = Middleware()
    middleware.start()

if __name__ == "__main__":
    main()