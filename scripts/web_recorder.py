#!/usr/bin/env python3
"""
MQTT Data Recorder API for Cooler Sensor Readings
Records sensor data from ESP8266 BME280 sensor to CSV file
Provides REST API interface for data access and control
"""

import paho.mqtt.client as mqtt
import json
import csv
import os
from datetime import datetime
import time
import logging
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd

# Configuration
MQTT_BROKER = "localhost"  # Change to your MQTT broker IP
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/cooler"
MQTT_USERNAME = ""  # Leave empty if no authentication
MQTT_PASSWORD = ""  # Leave empty if no authentication

# Data storage configuration
DATA_FILE = "sensor_readings.csv"
LOG_FILE = "mqtt_recorder.log"

# API configuration
API_HOST = "0.0.0.0"
API_PORT = 5002

# Global variables
app = Flask(__name__)
CORS(app)
recorder_instance = None
recording_status = {"is_recording": False, "start_time": None}

# Setup logging (console only, no file)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class SensorDataRecorder:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.setup_mqtt_client()
        self.setup_csv_file()
        self.is_connected = False
        self.last_reading = None
        self.total_readings = 0
        
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
            print(f"📁 Creating new CSV file: {DATA_FILE}")
            with open(DATA_FILE, 'w', newline='') as csvfile:
                fieldnames = [
                    'timestamp_received', 'timestamp_device', 'device',
                    'temperature', 'humidity', 'pressure',
                    'cooler_running', 'cooler_runtime', 'total_elapsed_time', 'cooler_ever_started', 'manual_override'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
            print(f"✅ Created new CSV file with headers: {DATA_FILE}")
        else:
            print(f"📂 Using existing CSV file: {DATA_FILE}")
            
        # Check if file is readable
        try:
            with open(DATA_FILE, 'r') as f:
                lines = f.readlines()
                print(f"📊 CSV file has {len(lines)} lines")
        except Exception as e:
            print(f"⚠️  Warning reading CSV file: {e}")
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for when the client connects to the broker"""
        if rc == 0:
            self.is_connected = True
            print("🟢 Connected to MQTT broker successfully")
            client.subscribe(MQTT_TOPIC)
            print(f"📡 Subscribed to topic: {MQTT_TOPIC}")
        else:
            self.is_connected = False
            print(f"🔴 Failed to connect to MQTT broker. Return code: {rc}")
    
    def on_disconnect(self, client, userdata, flags, rc, properties=None):
        """Callback for when the client disconnects from the broker"""
        self.is_connected = False
        if rc != 0:
            print("⚠️  Unexpected disconnection from MQTT broker")
        else:
            print("👋 Disconnected from MQTT broker")
    
    def on_log(self, client, userdata, level, buf):
        """Callback for MQTT client logging"""
        logging.debug(f"MQTT Log: {buf}")
    
    def on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        try:
            # Decode the message
            message = msg.payload.decode('utf-8')
            print(f"📡 Raw MQTT message: {message}")
            
            # Parse JSON data
            data = json.loads(message)
            print(f"📊 Parsed data: {data}")
            
            # Add receive timestamp
            receive_time = datetime.now()
            
            # Store last reading for API
            self.last_reading = {
                **data,
                'timestamp_received': receive_time.isoformat()
            }
            self.total_readings += 1
            
            # Prepare data for CSV
            csv_data = {
                'timestamp_received': receive_time.isoformat(),
                'timestamp_device': data.get('timestamp', ''),
                'device': data.get('device', 'unknown'),
                'temperature': data.get('temperature', ''),
                'humidity': data.get('humidity', ''),
                'pressure': data.get('pressure', ''),
                'cooler_running': data.get('cooler_running', ''),
                'cooler_runtime': data.get('cooler_runtime', ''),
                'total_elapsed_time': data.get('total_elapsed_time', ''),
                'cooler_ever_started': data.get('cooler_ever_started', ''),
                'manual_override': data.get('manual_override', '')
            }
            
            print(f"💾 CSV data to write: {csv_data}")
            
            # Write to CSV file
            self.write_to_csv(csv_data)
            
            # Display formatted data
            self.display_data(data, receive_time)
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON: {e}")
            print(f"Raw message: {message}")
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    def write_to_csv(self, data):
        """Write data to CSV file"""
        try:
            print(f"📝 Writing to CSV file: {DATA_FILE}")
            with open(DATA_FILE, 'a', newline='') as csvfile:
                fieldnames = [
                    'timestamp_received', 'timestamp_device', 'device',
                    'temperature', 'humidity', 'pressure',
                    'cooler_running', 'cooler_runtime', 'total_elapsed_time', 'cooler_ever_started', 'manual_override'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerow(data)
            print("✅ Data written to CSV successfully")
        except Exception as e:
            print(f"❌ Failed to write to CSV: {e}")
    
    def display_data(self, data, receive_time):
        """Display formatted sensor data"""
        print("\n" + "="*60)
        print(f"📊 SENSOR READING - {receive_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        print(f"🌡️  Temperature: {data.get('temperature', 'N/A')}°C")
        print(f"💧 Humidity:    {data.get('humidity', 'N/A')}%")
        print(f"🏔️  Pressure:    {data.get('pressure', 'N/A')} hPa")
        print(f"📱 Device:      {data.get('device', 'N/A')}")
        print(f"⏰ Device Time: {data.get('timestamp', 'N/A')} s")
        
        # Display cooler information if available
        cooler_running = data.get('cooler_running')
        manual_override = data.get('manual_override', False)
        
        if cooler_running is not None:
            print("-" * 30 + " COOLER STATUS " + "-" * 30)
            mode = "MANUAL" if manual_override else "AUTO"
            status_icon = "🧊 RUNNING" if cooler_running else "⏸️  STOPPED"
            print(f"❄️  Cooler:     {status_icon} ({mode})")
            
            cooler_runtime = data.get('cooler_runtime', 0)
            total_elapsed = data.get('total_elapsed_time', 0)
            ever_started = data.get('cooler_ever_started', False)
            
            if ever_started:
                print(f"⏱️  Runtime:    {cooler_runtime:.1f} seconds")
                print(f"📈 Elapsed:    {total_elapsed:.1f} seconds")
        
        print("="*60)
    
    def connect_and_start(self):
        """Connect to MQTT broker and start listening"""
        try:
            logging.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            
            # Start the network loop
            self.client.loop_start()
            
            recording_status["is_recording"] = True
            recording_status["start_time"] = datetime.now().isoformat()
            
            logging.info("MQTT client started. Recording in background...")
            
        except Exception as e:
            logging.error(f"Error connecting to MQTT: {e}")
            recording_status["is_recording"] = False
            raise e
    
    def stop_recording(self):
        """Stop MQTT recording"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            recording_status["is_recording"] = False
            logging.info("MQTT client stopped")
        except Exception as e:
            logging.error(f"Error stopping MQTT client: {e}")
    
    def get_status(self):
        """Get current status of the recorder"""
        return {
            "is_recording": recording_status["is_recording"],
            "is_connected": self.is_connected,
            "start_time": recording_status["start_time"],
            "total_readings": self.total_readings,
            "last_reading": self.last_reading
        }
    
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

# API Routes
@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current status of the recorder"""
    global recorder_instance
    if recorder_instance:
        status = recorder_instance.get_status()
    else:
        status = {
            "is_recording": False,
            "is_connected": False,
            "start_time": None,
            "total_readings": 0,
            "last_reading": None
        }
    
    return jsonify({
        "status": "success",
        "data": status
    })

@app.route('/api/start', methods=['POST'])
def start_recording():
    """Start MQTT recording"""
    global recorder_instance, recording_status
    
    try:
        if recording_status["is_recording"]:
            return jsonify({
                "status": "error",
                "message": "Recording is already active"
            }), 400
        
        if not recorder_instance:
            recorder_instance = SensorDataRecorder()
        
        # Start recording in background thread
        def start_bg():
            recorder_instance.connect_and_start()
        
        thread = threading.Thread(target=start_bg, daemon=True)
        thread.start()
        
        time.sleep(2)  # Give it time to connect
        
        return jsonify({
            "status": "success",
            "message": "Recording started successfully"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to start recording: {str(e)}"
        }), 500

@app.route('/api/stop', methods=['POST'])
def stop_recording():
    """Stop MQTT recording"""
    global recorder_instance
    
    try:
        if not recording_status["is_recording"]:
            return jsonify({
                "status": "error",
                "message": "Recording is not active"
            }), 400
        
        if recorder_instance:
            recorder_instance.stop_recording()
        
        return jsonify({
            "status": "success",
            "message": "Recording stopped successfully"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to stop recording: {str(e)}"
        }), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    """Get sensor data with optional filtering"""
    try:
        # Get query parameters
        limit = request.args.get('limit', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not os.path.exists(DATA_FILE):
            return jsonify({
                "status": "success",
                "data": [],
                "total": 0
            })
        
        # Read CSV data
        try:
            df = pd.read_csv(DATA_FILE)
        except:
            # Fallback to manual CSV reading if pandas fails
            with open(DATA_FILE, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                data = list(reader)
                
                if limit:
                    data = data[-limit:]
                
                return jsonify({
                    "status": "success",
                    "data": data,
                    "total": len(data)
                })
        
        # Filter by date range if provided
        if start_date or end_date:
            df['timestamp_received'] = pd.to_datetime(df['timestamp_received'])
            
            if start_date:
                df = df[df['timestamp_received'] >= start_date]
            if end_date:
                df = df[df['timestamp_received'] <= end_date]
        
        # Apply limit
        if limit:
            df = df.tail(limit)
        
        # Convert to list of dictionaries
        data = df.to_dict('records')
        
        # Convert datetime objects back to strings
        for record in data:
            if 'timestamp_received' in record and hasattr(record['timestamp_received'], 'isoformat'):
                record['timestamp_received'] = record['timestamp_received'].isoformat()
        
        return jsonify({
            "status": "success",
            "data": data,
            "total": len(data)
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to retrieve data: {str(e)}"
        }), 500

@app.route('/api/data/latest', methods=['GET'])
def get_latest_reading():
    """Get the latest sensor reading"""
    global recorder_instance
    
    if recorder_instance and recorder_instance.last_reading:
        return jsonify({
            "status": "success",
            "data": recorder_instance.last_reading
        })
    else:
        return jsonify({
            "status": "success",
            "data": None,
            "message": "No readings available"
        })

@app.route('/api/data/stats', methods=['GET'])
def get_statistics():
    """Get data statistics"""
    try:
        if not os.path.exists(DATA_FILE):
            return jsonify({
                "status": "success",
                "data": {
                    "total_readings": 0,
                    "first_reading": None,
                    "last_reading": None,
                    "temperature": {"min": None, "max": None, "avg": None},
                    "pressure": {"min": None, "max": None, "avg": None},
                    "altitude": {"min": None, "max": None, "avg": None}
                }
            })
        
        try:
            df = pd.read_csv(DATA_FILE)
            
            stats = {
                "total_readings": len(df),
                "first_reading": df.iloc[0]['timestamp_received'] if len(df) > 0 else None,
                "last_reading": df.iloc[-1]['timestamp_received'] if len(df) > 0 else None,
                "temperature": {
                    "min": float(df['temperature'].min()) if 'temperature' in df else None,
                    "max": float(df['temperature'].max()) if 'temperature' in df else None,
                    "avg": float(df['temperature'].mean()) if 'temperature' in df else None
                },
                "pressure": {
                    "min": float(df['pressure'].min()) if 'pressure' in df else None,
                    "max": float(df['pressure'].max()) if 'pressure' in df else None,
                    "avg": float(df['pressure'].mean()) if 'pressure' in df else None
                },
                "altitude": {
                    "min": float(df['altitude'].min()) if 'altitude' in df else None,
                    "max": float(df['altitude'].max()) if 'altitude' in df else None,
                    "avg": float(df['altitude'].mean()) if 'altitude' in df else None
                }
            }
            
        except:
            # Fallback to manual calculation
            with open(DATA_FILE, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                
                temps = [float(row['temperature']) for row in rows if row['temperature']]
                pressures = [float(row['pressure']) for row in rows if row['pressure']]
                altitudes = [float(row['altitude']) for row in rows if row['altitude']]
                
                stats = {
                    "total_readings": len(rows),
                    "first_reading": rows[0]['timestamp_received'] if rows else None,
                    "last_reading": rows[-1]['timestamp_received'] if rows else None,
                    "temperature": {
                        "min": min(temps) if temps else None,
                        "max": max(temps) if temps else None,
                        "avg": sum(temps) / len(temps) if temps else None
                    },
                    "pressure": {
                        "min": min(pressures) if pressures else None,
                        "max": max(pressures) if pressures else None,
                        "avg": sum(pressures) / len(pressures) if pressures else None
                    },
                    "altitude": {
                        "min": min(altitudes) if altitudes else None,
                        "max": max(altitudes) if altitudes else None,
                        "avg": sum(altitudes) / len(altitudes) if altitudes else None
                    }
                }
        
        return jsonify({
            "status": "success",
            "data": stats
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to calculate statistics: {str(e)}"
        }), 500

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    config = {
        "mqtt_broker": MQTT_BROKER,
        "mqtt_port": MQTT_PORT,
        "mqtt_topic": MQTT_TOPIC,
        "data_file": DATA_FILE,
        "log_file": LOG_FILE
    }
    
    return jsonify({
        "status": "success",
        "data": config
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "success",
        "message": "API is running",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/cooler/on', methods=['POST'])
def turn_cooler_on():
    """Turn cooler ON manually via MQTT"""
    global recorder_instance
    
    try:
        if not recorder_instance or not recorder_instance.is_connected:
            return jsonify({
                "status": "error",
                "message": "MQTT not connected"
            }), 503
        
        # Publish MQTT command to turn cooler ON
        recorder_instance.client.publish("sensors/cooler/control", "ON")
        
        return jsonify({
            "status": "success",
            "message": "Cooler turned ON"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to control cooler: {str(e)}"
        }), 500

@app.route('/api/cooler/off', methods=['POST'])
def turn_cooler_off():
    """Turn cooler OFF manually via MQTT"""
    global recorder_instance
    
    try:
        if not recorder_instance or not recorder_instance.is_connected:
            return jsonify({
                "status": "error",
                "message": "MQTT not connected"
            }), 503
        
        # Publish MQTT command to turn cooler OFF
        recorder_instance.client.publish("sensors/cooler/control", "OFF")
        
        return jsonify({
            "status": "success",
            "message": "Cooler turned OFF"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to control cooler: {str(e)}"
        }), 500

@app.route('/api/cooler/auto', methods=['POST'])
def set_cooler_auto():
    """Set cooler to automatic temperature control via MQTT"""
    global recorder_instance
    
    try:
        if not recorder_instance or not recorder_instance.is_connected:
            return jsonify({
                "status": "error",
                "message": "MQTT not connected"
            }), 503
        
        # Publish MQTT command to set cooler to auto mode
        recorder_instance.client.publish("sensors/cooler/control", "AUTO")
        
        return jsonify({
            "status": "success",
            "message": "Cooler set to automatic mode"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to control cooler: {str(e)}"
        }), 500

@app.route('/', methods=['GET'])
def index():
    """API documentation"""
    return jsonify({
        "message": "MQTT Sensor Data Recorder API",
        "version": "1.0.0",
        "endpoints": {
            "GET /api/health": "Health check",
            "GET /api/status": "Get recorder status",
            "POST /api/start": "Start recording",
            "POST /api/stop": "Stop recording",
            "GET /api/data": "Get sensor data (params: limit, start_date, end_date)",
            "GET /api/data/latest": "Get latest reading",
            "GET /api/data/stats": "Get data statistics",
            "GET /api/config": "Get configuration",
            "POST /api/cooler/on": "Turn cooler ON manually",
            "POST /api/cooler/off": "Turn cooler OFF manually",
            "POST /api/cooler/auto": "Set cooler to automatic mode"
        }
    })

def main():
    """Main function"""
    print("🔌 MQTT Sensor Data Recorder API")
    print("=" * 40)
    print(f"📡 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📋 MQTT Topic: {MQTT_TOPIC}")
    print(f"💾 Data file: {DATA_FILE}")
    print(f"📝 Log file: {LOG_FILE}")
    print(f"🌐 API Server: http://{API_HOST}:{API_PORT}")
    print("=" * 40)
    
    # Initialize recorder but don't start automatically
    global recorder_instance
    recorder_instance = SensorDataRecorder()
    
    # Show existing stats
    recorder_instance.show_stats()
    
    print("\n🚀 Starting API server...")
    print("📖 API Documentation available at: http://localhost:5000/")
    print("🔧 Control endpoints:")
    print("   POST /api/start  - Start recording")
    print("   POST /api/stop   - Stop recording")
    print("   GET  /api/status - Get status")
    print("   GET  /api/data   - Get data")
    
    try:
        app.run(host=API_HOST, port=API_PORT, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        if recorder_instance and recording_status["is_recording"]:
            recorder_instance.stop_recording()
        print("✅ API server stopped")

if __name__ == "__main__":
    main()
