import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from iota_sdk import Client, utf8_to_hex
import csv
import requests
from threading import Thread
import queue
from pathlib import Path

# Load environment variables
load_dotenv(dotenv_path='../.env')

# Configuration variables from environment
node_url = os.environ.get('NODE_URL', 'https://api.testnet.shimmer.network')
explorer_url = os.environ.get('EXPLORER_URL', 'https://explorer.shimmer.network/testnet')
connection_status = True
VERIFICATION_INTERVAL = 0.1  # 100ms
SIMULATION_INTERVAL = 10  # Seconds between simulated data

# Initialize IOTA client and queues
iota_client = Client(nodes=[node_url])
confirmation_queue = queue.Queue()
pending_data_file = Path('pending_data.csv')

# Data simulator class
class DataSimulator(Thread):
   # Class to simulate
   def __init__(self, message_handler):
       super().__init__(daemon=True)
       self.message_handler = message_handler
       self.running = True
    
   # Create message with fixed test values
   def create_message(self):
       """Creates message with fixed test values"""
       message = {
           'device_id': 'test-device-001',
           'timestamp': datetime.now().isoformat(),
           'data': {
               'v0': 25,  # AHT10 temperature
               'v1': 65,  # AHT10 humidity
               'v2': 22,  # DS18B20 temperature
               'v3': 60,  # Light level
               'v4': 15   # Soil moisture
           },
           'metadata': {
               'rssi': -63,
               'snr': 9.8
           }
       }
       return message

   # Run method
   def run(self):
       while self.running:
           message = self.create_message()
           self.message_handler(message)
           time.sleep(SIMULATION_INTERVAL)

   # Stop method
   def stop(self):
       self.running = False

# Save pending message to CSV
def save_pending_message(device_id, sensor_data):
   """Save pending message to CSV"""
   try:
       file_exists = pending_data_file.exists()
       
       with pending_data_file.open('a', newline='') as f:
           writer = csv.writer(f)
           
           if not file_exists:
               writer.writerow([
                   'device_id', 
                   'timestamp',
                   'sensor_data'
               ])
           
           writer.writerow([
               device_id,
               datetime.now().isoformat(),
               json.dumps(sensor_data)
           ])
           
       print(f"Message saved for device {device_id}")
       
   except Exception as e:
       print(f"Error saving message: {str(e)}")

# Load pending messages from CSV
def load_pending_messages():
   """Load pending messages from CSV"""
   messages = []
   try:
       if pending_data_file.exists():
           with pending_data_file.open('r', newline='') as f:
               reader = csv.DictReader(f)
               messages = list(reader)
           print(f"Loaded {len(messages)} pending messages")
       return messages
   except Exception as e:
       print(f"Error loading messages: {str(e)}")
       return []

# Send data to IOTA network
def send_to_iota(sensor_data, device_id):
   """Send data to IOTA network"""
   try:
       if not check_connection(): # Check connection before sending
           print("\nNetwork unavailable - storing data...")
           save_pending_message(device_id, sensor_data)
           return False

       data_string = json.dumps(sensor_data) # Convert to JSON string
       print(f"\nSending to IOTA: {data_string}")
       
       # Build and post block
       block = iota_client.build_and_post_block( 
           tag=utf8_to_hex('SENSOR_DATA'),
           data=utf8_to_hex(data_string)
       )
       
       block_id = block[0]
       print(f'Block sent! ID: {block_id}')
       confirmation_queue.put((block_id, device_id))
       return True
           
   except Exception as e:
       print(f"Error sending to IOTA: {str(e)}")
       save_pending_message(device_id, sensor_data)
       return False

# Check block confirmation
def check_block_confirmation(block_id):
   """Check if block is confirmed in Tangle"""
   try:
       response = requests.get(f"{node_url}/api/core/v2/blocks/{block_id}") # Get block info
       if response.status_code == 200:
           print(f"Block {block_id} confirmed!")
           print(f"Explorer URL: {explorer_url}/block/{block_id}")
           
           try:
               # Store timing information
               file_exists = os.path.isfile('confirmation_times.csv')
               with open('confirmation_times.csv', mode='a', newline='') as file:
                   writer = csv.writer(file)
                   if not file_exists:
                       writer.writerow(['Block ID', 'Timestamp', 'Explorer URL'])
                   
                   writer.writerow([
                       block_id,
                       datetime.now().isoformat(),
                       f"{explorer_url}/block/{block_id}"
                   ])
           except Exception as e:
               print(f"Error storing confirmation data: {str(e)}")
               
           return True
       return False
   except Exception:
       return False

# Check connection to IOTA node
def check_connection():
   """Check if IOTA node is reachable"""
   try:
       response = requests.get(f"{node_url}/health", timeout=1) # Check health endpoint
       return response.status_code == 200
   except Exception:
       return False

# Monitor methods
def retry_monitor():
   """Monitor and retry sending pending messages"""
   while True:
       try:
           if check_connection(): # Check connection before sending
               pending_messages = load_pending_messages() # Load pending messages
               
               if pending_messages:
                   print("\nConnection available - attempting to send pending messages...")
                   
                   for message in pending_messages:
                       sensor_data = json.loads(message['sensor_data'])

                       if send_to_iota(sensor_data, message['device_id']):
                            continue  
                       
                   if pending_data_file.exists():
                        pending_data_file.unlink()
                        print("Pending messages processed")
           
           time.sleep(VERIFICATION_INTERVAL)
           
       except Exception as e:
           print(f"Error in retry monitor: {str(e)}")

# Monitor block confirmations
def confirmation_monitor():
   """Monitor block confirmations"""
   while True:
       try: 
           block_id, device_id = confirmation_queue.get() # Get block ID from queue
           while not check_block_confirmation(block_id):
               time.sleep(VERIFICATION_INTERVAL)
           
       except Exception as e:
           print(f"Error in confirmation monitor: {str(e)}")
       finally:
           confirmation_queue.task_done()

# Monitor connection status
def connection_monitor():
   """Monitor connection status"""
   global connection_status
   last_status = True
   
   while True:
       try:
           current_status = check_connection()
           connection_status = current_status
           
           if current_status != last_status: # Check if status changed
               if not current_status:
                   print("\n--> Connection lost <--")
               else:
                   print("\n--> Connection restored <--")
               
               last_status = current_status
           
           time.sleep(VERIFICATION_INTERVAL)
           
       except Exception as e:
           print(f"Error in connection monitor: {str(e)}")
           connection_status = False

# Process message
def process_message(message):
   """Process and send simulated data"""
   try:
       print("\n=== Processing simulated data ===")
       device_id = message['device_id']
       
       if not connection_status:
           print("\nOffline - storing data...")
           save_pending_message(device_id, message)
           return
       
       send_to_iota(message, device_id)
               
   except Exception as e:
       print(f"Error processing message: {str(e)}")

# Main method
def main():
   simulator = None
   try:
       
       monitor_thread = Thread(target=confirmation_monitor, daemon=True)
       monitor_thread.start()
       
       retry_thread = Thread(target=retry_monitor, daemon=True)
       retry_thread.start()
       
       connection_thread = Thread(target=connection_monitor, daemon=True)
       connection_thread.start()
       
       simulator = DataSimulator(process_message)
       simulator.start()
       
       while True:
           time.sleep(1)
           
   except KeyboardInterrupt:
       print("\nShutting down...")
   except Exception as e:
       print(f"\nError in main: {str(e)}")
   finally:
       if simulator:
           simulator.stop()
           print("Simulator stopped")

if __name__ == "__main__":
   main()