#!/usr/bin/env python3
"""
API Test Script for MQTT Sensor Data Recorder
Demonstrates how to interact with the API
"""

import requests
import json
import time

# API base URL
API_BASE = "http://localhost:5000/api"

def test_api():
    """Test all API endpoints"""
    print("🧪 Testing MQTT Sensor Data Recorder API")
    print("=" * 50)
    
    # Test health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{API_BASE}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "-" * 30)
    
    # Test configuration
    print("2. Getting configuration...")
    try:
        response = requests.get(f"{API_BASE}/config")
        config = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   MQTT Broker: {config['data']['mqtt_broker']}")
        print(f"   MQTT Topic: {config['data']['mqtt_topic']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "-" * 30)
    
    # Test status
    print("3. Getting status...")
    try:
        response = requests.get(f"{API_BASE}/status")
        status = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Recording: {status['data']['is_recording']}")
        print(f"   Connected: {status['data']['is_connected']}")
        print(f"   Total readings: {status['data']['total_readings']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "-" * 30)
    
    # Test starting recording
    print("4. Starting recording...")
    try:
        response = requests.post(f"{API_BASE}/start")
        result = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Message: {result.get('message', 'No message')}")
        
        if response.status_code == 200:
            print("   Waiting 5 seconds for data...")
            time.sleep(5)
            
            # Check status again
            response = requests.get(f"{API_BASE}/status")
            status = response.json()
            print(f"   Recording: {status['data']['is_recording']}")
            print(f"   Connected: {status['data']['is_connected']}")
            
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "-" * 30)
    
    # Test getting latest data
    print("5. Getting latest reading...")
    try:
        response = requests.get(f"{API_BASE}/data/latest")
        data = response.json()
        print(f"   Status: {response.status_code}")
        if data['data']:
            reading = data['data']
            print(f"   Temperature: {reading.get('temperature', 'N/A')}°C")
            print(f"   Pressure: {reading.get('pressure', 'N/A')} hPa")
            print(f"   Altitude: {reading.get('altitude', 'N/A')} m")
        else:
            print("   No readings available yet")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "-" * 30)
    
    # Test getting data with limit
    print("6. Getting last 5 readings...")
    try:
        response = requests.get(f"{API_BASE}/data?limit=5")
        data = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Total readings: {data.get('total', 0)}")
        if data['data']:
            for i, reading in enumerate(data['data'][-3:], 1):  # Show last 3
                print(f"   Reading {i}: {reading.get('temperature', 'N/A')}°C, "
                      f"{reading.get('pressure', 'N/A')} hPa")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "-" * 30)
    
    # Test statistics
    print("7. Getting statistics...")
    try:
        response = requests.get(f"{API_BASE}/data/stats")
        stats = response.json()
        print(f"   Status: {response.status_code}")
        if stats['data']['total_readings'] > 0:
            temp_stats = stats['data']['temperature']
            print(f"   Total readings: {stats['data']['total_readings']}")
            print(f"   Temperature: {temp_stats['min']:.1f}°C - {temp_stats['max']:.1f}°C "
                  f"(avg: {temp_stats['avg']:.1f}°C)")
        else:
            print("   No data available for statistics")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "-" * 30)
    
    # Test stopping recording
    print("8. Stopping recording...")
    try:
        response = requests.post(f"{API_BASE}/stop")
        result = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Message: {result.get('message', 'No message')}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n🎉 API test completed!")

if __name__ == "__main__":
    test_api()
