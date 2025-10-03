#!/bin/bash

# Setup script for MQTT sensor data recorder and plotting GUI

echo "🔧 Setting up MQTT Sensor Data Recorder & Plotting GUI"
echo "======================================================"

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

# Make scripts executable
chmod +x scripts/web_recorder.py
chmod +x scripts/PLOT_GUI.py
chmod +x scripts/api_test.py

echo ""
echo "🚀 Setup complete!"
echo ""
echo "📋 Available tools:"
echo "  1. API Server:     python3 scripts/web_recorder.py"
echo "  2. Plotting GUI:   python3 scripts/PLOT_GUI.py"
echo "  3. Web Dashboard:  Open scripts/dashboard.html in browser"
echo "  4. API Test:       python3 scripts/api_test.py"
echo ""
echo "📝 Quick Start:"
echo "  1. Start the API server: python3 scripts/web_recorder.py"
echo "  2. In another terminal, run: python3 scripts/PLOT_GUI.py"
echo "  3. Click 'Start Recording' in the GUI"
echo ""
echo "🔧 Configuration:"
echo "  - Edit MQTT_BROKER in scripts/web_recorder.py"
echo "  - Update WiFi credentials in src/secrets.cpp"
echo "  - Upload code to ESP8266 using PlatformIO"
