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

# Load environment variables
load_dotenv(dotenv_path='../.env')

# Configuration variables for TTN and IOTA
ttn_broker = "eu1.cloud.thethings.network"
ttn_port = 8883
ttn_app_id = os.getenv('TTN_APP_ID')
ttn_api_key = os.getenv('TTN_API_KEY')
node_url = os.environ.get('NODE_URL', 'https://api.testnet.shimmer.network')
explorer_url = os.environ.get('EXPLORER_URL', 'https://explorer.shimmer.network/testnet')

# Initialize IOTA client and queues
iota_client = Client(nodes=[node_url])
confirmation_queue = queue.Queue()

# Function to store data in CSV file
def store_data(block_id, sensor_data, ttn_time=None, confirmation_time=None):
    """Store data in CSV file"""
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
                    datetime.fromtimestamp(ttn_time).isoformat(),
                    None, None,
                    f"{explorer_url}/block/{block_id}",
                    False
                ])
        else:
            df = pd.read_csv('iota_data.csv', dtype={
                'Confirmation time': str,
                'Response time': str
            })
            mask = df['Block ID'] == block_id
            
            response_time = confirmation_time - ttn_time
            
            df.loc[mask, 'Confirmation time'] = datetime.fromtimestamp(confirmation_time).isoformat()
            df.loc[mask, 'Response time'] = f"{response_time:.2f}"
            df.loc[mask, 'Confirmed'] = True
            
            df.to_csv('iota_data.csv', index=False)
            print(f"\nResponse time: {response_time:.2f} seconds")
            
    except Exception as e:
        print(f"Error storing data: {str(e)}")

# Function to plot response times
def plot_response_times():
   """Plot response times graph"""
   try:
       if not os.path.exists('iota_data.csv'):
           print("No data file found.")
           return
           
       df = pd.read_csv('iota_data.csv')
       df['TTN time'] = pd.to_datetime(df['TTN time'])
       df['Response time'] = pd.to_numeric(df['Response time'])
       
       mean_response = df['Response time'].mean()

       plt.figure(figsize=(10, 5))  # Increased figure size
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
       plt.xticks(rotation=45)  # Increased rotation
       
       plt.tight_layout()
       plt.savefig('response_times.png', dpi=300)
       print(f"\nMean response time: {mean_response:.2f} seconds")
   except Exception as e:
       print(f"Error creating graph: {str(e)}")

# Function to check block confirmation
def check_block_confirmation(block_id, ttn_time, device_id, sensor_data):
    """Check if block is confirmed in Tangle"""
    try:
        response = requests.get(f"{node_url}/api/core/v2/blocks/{block_id}")
        if response.status_code == 200:
            confirmation_time = time.time()
            store_data(block_id, sensor_data, ttn_time, confirmation_time)
            return True
        return False
    except Exception as e:
        print(f"Error checking block confirmation: {str(e)}")
        return False

# Function to monitor block confirmation
def confirmation_monitor():
   """Monitor block confirmations"""
   while True:
       try:
           block_id, ttn_time, device_id, sensor_data = confirmation_queue.get()
           attempts = 0
           while attempts < 300:  # 30 seconds
               if check_block_confirmation(block_id, ttn_time, device_id, sensor_data):
                   break
               time.sleep(0.1)  # Wait 100ms
               attempts += 1
           if attempts >= 300:
               print(f"Block {block_id} not confirmed after 30 seconds")
       except Exception as e:
           print(f"Error in confirmation monitor: {str(e)}")
       finally:
           confirmation_queue.task_done()

# Function to process sensor data
def process_sensor_data(payload):
    """Process TTN message and create sensor data structure"""
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

# Function to send data to IOTA
def send_to_iota(sensor_data, ttn_time, device_id):
    """Send sensor data to IOTA"""
    try:
        data_string = json.dumps(sensor_data)
        print(f"\nSending to IOTA: {data_string}")
        
        block = iota_client.build_and_post_block(
            tag=utf8_to_hex('SENSOR_DATA'),
            data=utf8_to_hex(data_string)
        )
        
        block_id = block[0]
        print(f'Block sent! ID: {block_id}')
        confirmation_queue.put((block_id, ttn_time, device_id, sensor_data))
        return block_id
    except Exception as e:
        print(f"Error sending to IOTA: {str(e)}")
        return None

# Callbacks for MQTT client
def on_connect(client, userdata, flags, rc):
    """Callback when connected to TTN"""
    if rc == 0:
        print("Connected to TTN successfully!")
        topic = f"v3/{ttn_app_id}@ttn/devices/+/up" # Topic to subscribe
        client.subscribe(topic) # Subscribe to topic
        print(f"Subscribed to topic: {topic}")
    else:
        print(f"Failed to connect to TTN, return code: {rc}")

# Callback for new messages
def on_message(client, userdata, msg):
    """Callback for new messages"""
    try:
        print("\n=== New message received ===")
        ttn_time = time.time()
        
        payload = json.loads(msg.payload.decode())
        device_id = payload['end_device_ids']['device_id']
        
        if 'uplink_message' in payload and 'decoded_payload' in payload['uplink_message']:
            sensor_data = process_sensor_data(payload)
            if sensor_data:
                block_id = send_to_iota(sensor_data, ttn_time, device_id)
                if block_id:
                    store_data(block_id, sensor_data, ttn_time)
                    print(f"Data sent to IOTA. Monitoring confirmation...")
                else:
                    print("Failed to send to IOTA")
    except Exception as e:
        print(f"Error processing message: {str(e)}")

# Main function
def main():
    try:
        print("\nStarting TTN to IOTA bridge with response time monitoring...")
        
        monitor_thread = Thread(target=confirmation_monitor, daemon=True) 
        monitor_thread.start()
        
        client = mqtt.Client(client_id=f"python-bridge-{ttn_app_id}-{int(time.time())}")
        client.username_pw_set(ttn_app_id, ttn_api_key)
        client.tls_set()
        
        client.on_connect = on_connect
        client.on_message = on_message
        
        print("\nConnecting to TTN...")
        client.connect(ttn_broker, ttn_port, 60)
        
        print("Starting loop...")
        client.loop_forever()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
        plot_response_times()
    except Exception as e:
        print(f"\nError in main: {str(e)}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()