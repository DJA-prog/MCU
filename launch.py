#!/usr/bin/env python3
"""
Launcher script for the complete sensor monitoring system
Starts both the API server and plotting GUI
"""

import subprocess
import sys
import time
import threading
import signal
import os

def start_api_server():
    """Start the API server in a subprocess"""
    try:
        print("🚀 Starting API server...")
        api_process = subprocess.Popen([
            sys.executable, "scripts/web_recorder.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Give the API server time to start
        time.sleep(3)
        
        return api_process
    except Exception as e:
        print(f"❌ Failed to start API server: {e}")
        return None

def start_plotting_gui():
    """Start the plotting GUI"""
    try:
        print("📊 Starting plotting GUI...")
        time.sleep(2)  # Wait a bit more for API to be ready
        gui_process = subprocess.Popen([
            sys.executable, "scripts/PLOT_GUI.py"
        ])
        return gui_process
    except Exception as e:
        print(f"❌ Failed to start plotting GUI: {e}")
        return None

def main():
    """Main launcher function"""
    print("🌡️ Sensor Monitoring System Launcher")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not os.path.exists("scripts/web_recorder.py"):
        print("❌ Please run this script from the project root directory")
        return
    
    processes = []
    
    try:
        # Start API server
        api_process = start_api_server()
        if api_process:
            processes.append(api_process)
            print("✅ API server started (PID: {})".format(api_process.pid))
        
        # Start plotting GUI
        gui_process = start_plotting_gui()
        if gui_process:
            processes.append(gui_process)
            print("✅ Plotting GUI started (PID: {})".format(gui_process.pid))
        
        print("\n🎉 System is running!")
        print("📡 API server: http://localhost:5000")
        print("📊 Plotting GUI: Should be visible on screen")
        print("🌐 Web dashboard: Open scripts/dashboard.html in browser")
        print("\nPress Ctrl+C to stop all processes\n")
        
        # Wait for GUI process to finish (when user closes it)
        if gui_process:
            gui_process.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    
    finally:
        # Cleanup processes
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ Process {process.pid} terminated")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"🔪 Process {process.pid} killed")
            except Exception as e:
                print(f"❌ Error stopping process {process.pid}: {e}")
        
        print("🏁 All processes stopped")

if __name__ == "__main__":
    main()
