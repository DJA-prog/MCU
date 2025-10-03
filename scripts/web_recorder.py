#!/usr/bin/env python3
"""
MQTT Data Recorder for Cooler Sensor Readings
Records sensor data from ESP8266 BME280 sensor to CSV file
"""

import paho.mqtt.client as mqtt
import json
import csv
import os
from datetime import datetime
import time
import logging

# Configuration
MQTT_BROKER = "localhost"  # Change to your MQTT broker IP
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/cooler"
MQTT_USERNAME = ""  # Leave empty if no authentication
MQTT_PASSWORD = ""  # Leave empty if no authentication

# Data storage configuration
DATA_FILE = "sensor_readings.csv"
LOG_FILE = "mqtt_recorder.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class SensorDataRecorder:
    def __init__(self):
        self.client = mqtt.Client()
        self.setup_mqtt_client()
        self.setup_csv_file()
        
    def setup_mqtt_client(self):
        """Configure MQTT client callbacks and authentication"""
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_log = self.on_log
        
        # Set authentication if provided
        if MQTT_USERNAME and MQTT_PASSWORD:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            
    def setup_csv_file(self):
        """Create CSV file with headers if it doesn't exist"""
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'w', newline='') as csvfile:
                fieldnames = [
                    'timestamp_received', 'timestamp_device', 'device',
                    'temperature', 'pressure', 'altitude'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
            logging.info(f"Created new CSV file: {DATA_FILE}")
        else:
            logging.info(f"Using existing CSV file: {DATA_FILE}")
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker"""
        if rc == 0:
            logging.info("Connected to MQTT broker successfully")
            client.subscribe(MQTT_TOPIC)
            logging.info(f"Subscribed to topic: {MQTT_TOPIC}")
        else:
            logging.error(f"Failed to connect to MQTT broker. Return code: {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker"""
        if rc != 0:
            logging.warning("Unexpected disconnection from MQTT broker")
        else:
            logging.info("Disconnected from MQTT broker")
    
    def on_log(self, client, userdata, level, buf):
        """Callback for MQTT client logging"""
        logging.debug(f"MQTT Log: {buf}")
    
    def on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        try:
            # Decode the message
            message = msg.payload.decode('utf-8')
            logging.info(f"Received message: {message}")
            
            # Parse JSON data
            data = json.loads(message)
            
            # Add receive timestamp
            receive_time = datetime.now()
            
            # Prepare data for CSV
            csv_data = {
                'timestamp_received': receive_time.isoformat(),
                'timestamp_device': data.get('timestamp', ''),
                'device': data.get('device', 'unknown'),
                'temperature': data.get('temperature', ''),
                'pressure': data.get('pressure', ''),
                'altitude': data.get('altitude', '')
            }
            
            # Write to CSV file
            self.write_to_csv(csv_data)
            
            # Display formatted data
            self.display_data(data, receive_time)
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON: {e}")
            logging.error(f"Raw message: {message}")
        except Exception as e:
            logging.error(f"Error processing message: {e}")
    
    def write_to_csv(self, data):
        """Write data to CSV file"""
        try:
            with open(DATA_FILE, 'a', newline='') as csvfile:
                fieldnames = [
                    'timestamp_received', 'timestamp_device', 'device',
                    'temperature', 'pressure', 'altitude'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerow(data)
            logging.debug("Data written to CSV successfully")
        except Exception as e:
            logging.error(f"Failed to write to CSV: {e}")
    
    def display_data(self, data, receive_time):
        """Display formatted sensor data"""
        print("\n" + "="*50)
        print(f"📊 SENSOR READING - {receive_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)
        print(f"🌡️  Temperature: {data.get('temperature', 'N/A')}°C")
        print(f"🏔️  Pressure:    {data.get('pressure', 'N/A')} hPa")
        print(f"📏 Altitude:    {data.get('altitude', 'N/A')} m")
        print(f"📱 Device:      {data.get('device', 'N/A')}")
        print(f"⏰ Device Time: {data.get('timestamp', 'N/A')} ms")
        print("="*50)
    
    def connect_and_start(self):
        """Connect to MQTT broker and start listening"""
        try:
            logging.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            
            # Start the network loop
            self.client.loop_start()
            
            logging.info("MQTT client started. Waiting for messages...")
            logging.info("Press Ctrl+C to stop recording")
            
            # Keep the script running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logging.info("Recording stopped by user")
        except Exception as e:
            logging.error(f"Error: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            logging.info("MQTT client stopped")
    
    def show_stats(self):
        """Show statistics about recorded data"""
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r') as csvfile:
                    reader = csv.DictReader(csvfile)
                    rows = list(reader)
                    print(f"\n📈 STATISTICS")
                    print(f"Total readings recorded: {len(rows)}")
                    if rows:
                        print(f"First reading: {rows[0]['timestamp_received']}")
                        print(f"Last reading: {rows[-1]['timestamp_received']}")
        except Exception as e:
            logging.error(f"Error showing stats: {e}")

def main():
    """Main function"""
    print("🔌 MQTT Sensor Data Recorder")
    print("=" * 40)
    print(f"📡 Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📋 Topic: {MQTT_TOPIC}")
    print(f"💾 Data file: {DATA_FILE}")
    print(f"📝 Log file: {LOG_FILE}")
    print("=" * 40)
    
    # Create recorder instance
    recorder = SensorDataRecorder()
    
    # Show existing stats
    recorder.show_stats()
    
    # Start recording
    recorder.connect_and_start()

if __name__ == "__main__":
    main()
