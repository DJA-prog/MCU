#!/bin/bash

# Setup script for MQTT sensor data recorder

echo "🔧 Setting up MQTT Sensor Data Recorder"
echo "======================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

echo "✅ Python 3 found"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip3 first."
    exit 1
fi

echo "✅ pip3 found"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo ""
echo "🚀 Setup complete!"
echo ""
echo "To run the MQTT recorder:"
echo "  python3 scripts/web_recorder.py"
echo ""
echo "📝 Configuration notes:"
echo "  - Edit MQTT_BROKER in web_recorder.py to match your broker IP"
echo "  - Update MQTT_USERNAME and MQTT_PASSWORD if authentication is required"
echo "  - Data will be saved to sensor_readings.csv"
echo "  - Logs will be saved to mqtt_recorder.log"
