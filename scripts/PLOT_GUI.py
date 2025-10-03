#!/usr/bin/env python3
"""
Real-time Sensor Data Plotting GUI using PyQt5
Connects to the MQTT Sensor Data Recorder API and displays live plots
"""

import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QPushButton, QLabel, 
                            QLineEdit, QCheckBox, QGroupBox, QMessageBox,
                            QSplitter, QFrame)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QPalette, QColor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import requests
import json
from datetime import datetime, timedelta
import threading
import queue
import numpy as np

class DataWorker(QThread):
    """Worker thread for fetching data from API"""
    data_received = pyqtSignal(list)
    status_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, api_base):
        super().__init__()
        self.api_base = api_base
        self.running = True
        
    def api_call(self, endpoint, method='GET'):
        """Make API call with error handling"""
        try:
            url = f"{self.api_base}{endpoint}"
            if method == 'GET':
                response = requests.get(url, timeout=5)
            elif method == 'POST':
                response = requests.post(url, timeout=5)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}
        except json.JSONDecodeError as e:
            return {"status": "error", "message": "Invalid JSON response"}
    
    def fetch_status(self):
        """Fetch status from API"""
        result = self.api_call('/status')
        if result.get('status') == 'success':
            self.status_received.emit(result['data'])
        else:
            self.error_occurred.emit(result.get('message', 'Unknown error'))
    
    def fetch_data(self):
        """Fetch data from API"""
        result = self.api_call('/data?limit=100')
        if result.get('status') == 'success':
            self.data_received.emit(result['data'])
        else:
            self.error_occurred.emit(result.get('message', 'Unknown error'))
    
    def start_recording(self):
        """Start recording"""
        result = self.api_call('/start', 'POST')
        return result
    
    def stop_recording(self):
        """Stop recording"""
        result = self.api_call('/stop', 'POST')
        return result

class SensorPlotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌡️ Sensor Data Plotter - Qt5")
        self.setGeometry(100, 100, 1400, 900)
        
        # API configuration
        self.api_base = "http://localhost:5000/api"
        
        # Data storage
        self.time_data = []
        self.temperature_data = []
        self.pressure_data = []
        self.start_time = None
        
        # Status variables
        self.is_connected = False
        self.is_recording = False
        self.auto_refresh = True
        
        # Setup worker thread
        self.worker = DataWorker(self.api_base)
        self.worker.data_received.connect(self.process_new_data)
        self.worker.status_received.connect(self.update_status_display)
        self.worker.error_occurred.connect(self.show_error)
        
        # Setup UI
        self.init_ui()
        self.setup_plots()
        self.apply_styles()
        
        # Setup timers
        self.setup_timers()
        
    def init_ui(self):
        """Initialize the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create control panel
        self.create_control_panel(main_layout)
        
        # Create status panel
        self.create_status_panel(main_layout)
        
        # Create plot area
        self.create_plot_area(main_layout)
        
    def create_control_panel(self, parent_layout):
        """Create control buttons and settings"""
        control_group = QGroupBox("📡 Controls")
        control_layout = QHBoxLayout(control_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶️ Start Recording")
        self.start_btn.clicked.connect(self.start_recording)
        self.start_btn.setMinimumHeight(35)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹️ Stop Recording")
        self.stop_btn.clicked.connect(self.stop_recording)
        self.stop_btn.setMinimumHeight(35)
        button_layout.addWidget(self.stop_btn)
        
        self.refresh_btn = QPushButton("🔄 Refresh Data")
        self.refresh_btn.clicked.connect(self.manual_refresh)
        self.refresh_btn.setMinimumHeight(35)
        button_layout.addWidget(self.refresh_btn)
        
        self.clear_btn = QPushButton("🗑️ Clear Plot")
        self.clear_btn.clicked.connect(self.clear_data)
        self.clear_btn.setMinimumHeight(35)
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        
        # Settings
        settings_layout = QHBoxLayout()
        
        self.auto_refresh_cb = QCheckBox("Auto Refresh")
        self.auto_refresh_cb.setChecked(True)
        self.auto_refresh_cb.stateChanged.connect(self.toggle_auto_refresh)
        settings_layout.addWidget(self.auto_refresh_cb)
        
        settings_layout.addWidget(QLabel("API:"))
        self.api_entry = QLineEdit(self.api_base)
        self.api_entry.setMinimumWidth(250)
        settings_layout.addWidget(self.api_entry)
        
        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.update_api_base)
        connect_btn.setMinimumHeight(30)
        settings_layout.addWidget(connect_btn)
        
        # Combine layouts
        control_layout.addLayout(button_layout)
        control_layout.addStretch()
        control_layout.addLayout(settings_layout)
        
        parent_layout.addWidget(control_group)
        
    def create_status_panel(self, parent_layout):
        """Create status information panel"""
        status_group = QGroupBox("📊 Status")
        status_layout = QHBoxLayout(status_group)
        
        # Status indicators
        status_left = QHBoxLayout()
        
        self.connection_label = QLabel("🔴 Disconnected")
        self.connection_label.setStyleSheet("color: red; font-weight: bold;")
        status_left.addWidget(self.connection_label)
        
        self.recording_label = QLabel("⏸️ Not Recording")
        self.recording_label.setStyleSheet("color: orange; font-weight: bold;")
        status_left.addWidget(self.recording_label)
        
        self.data_count_label = QLabel("📈 Data Points: 0")
        status_left.addWidget(self.data_count_label)
        
        status_left.addStretch()
        
        # Current readings
        status_right = QHBoxLayout()
        
        self.temp_label = QLabel("🌡️ Temp: -- °C")
        self.temp_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        status_right.addWidget(self.temp_label)
        
        self.pressure_label = QLabel("🏔️ Pressure: -- hPa")
        self.pressure_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        status_right.addWidget(self.pressure_label)
        
        # Combine layouts
        status_layout.addLayout(status_left)
        status_layout.addStretch()
        status_layout.addLayout(status_right)
        
        parent_layout.addWidget(status_group)
        
    def create_plot_area(self, parent_layout):
        """Create matplotlib plotting area"""
        plot_group = QGroupBox("📈 Real-time Sensor Data")
        plot_layout = QVBoxLayout(plot_group)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(14, 8), facecolor='white')
        self.canvas = FigureCanvas(self.figure)
        
        # Create subplots
        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)
        
        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas)
        
        parent_layout.addWidget(plot_group)
        
    def setup_plots(self):
        """Initialize plot configuration"""
        self.setup_plot_styling()
        
    def setup_plot_styling(self):
        """Configure plot appearance"""
        # Temperature plot
        self.ax1.set_title('🌡️ Temperature vs Time', fontsize=14, fontweight='bold', pad=20)
        self.ax1.set_ylabel('Temperature (°C)', fontsize=12)
        self.ax1.grid(True, alpha=0.3)
        self.ax1.set_facecolor('#f8f9fa')
        
        # Pressure plot
        self.ax2.set_title('🏔️ Pressure vs Time', fontsize=14, fontweight='bold', pad=20)
        self.ax2.set_xlabel('Time (seconds since start)', fontsize=12)
        self.ax2.set_ylabel('Pressure (hPa)', fontsize=12)
        self.ax2.grid(True, alpha=0.3)
        self.ax2.set_facecolor('#f8f9fa')
        
        # Adjust layout
        self.figure.tight_layout(pad=3.0)
        self.canvas.draw()
        
    def apply_styles(self):
        """Apply modern Qt5 styling"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #333333;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QLineEdit {
                border: 2px solid #ddd;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
            QCheckBox {
                font-weight: bold;
            }
            QLabel {
                color: #333333;
            }
        """)
        
    def setup_timers(self):
        """Setup Qt timers for periodic updates"""
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(3000)  # Every 3 seconds
        
        # Data update timer
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.fetch_data)
        self.data_timer.start(2000)  # Every 2 seconds
        
        # Initial update
        self.update_status()
        self.fetch_data()
        # Initial update
        self.update_status()
        self.fetch_data()
        
    def toggle_auto_refresh(self, state):
        """Toggle auto refresh functionality"""
        self.auto_refresh = state == Qt.Checked
        if self.auto_refresh:
            self.data_timer.start(2000)
        else:
            self.data_timer.stop()
        
    def start_recording(self):
        """Start MQTT recording via API"""
        def start_async():
            result = self.worker.start_recording()
            if result.get('status') == 'success':
                QMessageBox.information(self, "Success", "Recording started!")
                QTimer.singleShot(2000, self.update_status)  # Update status after 2 seconds
            else:
                message = result.get('message', 'Unknown error')
                QMessageBox.critical(self, "Error", f"Failed to start: {message}")
        
        # Run in separate thread to avoid blocking UI
        threading.Thread(target=start_async, daemon=True).start()
        
    def stop_recording(self):
        """Stop MQTT recording via API"""
        def stop_async():
            result = self.worker.stop_recording()
            if result.get('status') == 'success':
                QMessageBox.information(self, "Success", "Recording stopped!")
                self.update_status()
            else:
                message = result.get('message', 'Unknown error')
                QMessageBox.critical(self, "Error", f"Failed to stop: {message}")
        
        threading.Thread(target=stop_async, daemon=True).start()
        
    def update_api_base(self):
        """Update API base URL"""
        new_api = self.api_entry.text().strip()
        if new_api:
            self.api_base = new_api
            self.worker.api_base = new_api
            self.update_status()
            
    def manual_refresh(self):
        """Manually refresh data"""
        self.fetch_data()
        
    def clear_data(self):
        """Clear all plotted data"""
        self.time_data.clear()
        self.temperature_data.clear()
        self.pressure_data.clear()
        self.start_time = None
        self.update_plots()
        
    def update_status(self):
        """Update connection and recording status"""
        self.worker.fetch_status()
        
    def fetch_data(self):
        """Fetch data from API"""
        if self.auto_refresh:
            self.worker.fetch_data()
        
    def update_status_display(self, status_data):
        """Update status labels with current data"""
        # Connection status
        self.is_connected = True
        self.connection_label.setText("🟢 Connected")
        self.connection_label.setStyleSheet("color: green; font-weight: bold;")
        
        # Recording status
        self.is_recording = status_data.get('is_recording', False)
        if self.is_recording:
            self.recording_label.setText("� Recording")
            self.recording_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.recording_label.setText("⏸️ Not Recording")
            self.recording_label.setStyleSheet("color: orange; font-weight: bold;")
        
        # Data count
        total_readings = status_data.get('total_readings', 0)
        self.data_count_label.setText(f"📈 Total Readings: {total_readings}")
        
        # Latest reading
        latest = status_data.get('last_reading')
        if latest:
            temp = latest.get('temperature', '--')
            pressure = latest.get('pressure', '--')
            self.temp_label.setText(f"🌡️ Temp: {temp} °C")
            self.pressure_label.setText(f"🏔️ Pressure: {pressure} hPa")
        
    def show_error(self, message):
        """Show error message and update disconnected status"""
        print(f"Error: {message}")
        
        # Update status to disconnected
        self.is_connected = False
        self.is_recording = False
        self.connection_label.setText("🔴 Disconnected")
        self.connection_label.setStyleSheet("color: red; font-weight: bold;")
        self.recording_label.setText("⏸️ Not Recording")
        self.recording_label.setStyleSheet("color: orange; font-weight: bold;")
        self.temp_label.setText("🌡️ Temp: -- °C")
        self.pressure_label.setText("🏔️ Pressure: -- hPa")
        
    def process_new_data(self, readings):
        """Process new data and update plots"""
        if not readings:
            return
            
        # Clear existing data
        self.time_data.clear()
        self.temperature_data.clear()
        self.pressure_data.clear()
        
        # Set start time from first reading
        if readings:
            try:
                self.start_time = datetime.fromisoformat(readings[0]['timestamp_received'].replace('Z', '+00:00'))
            except:
                self.start_time = datetime.now()
        
        # Process all readings
        for reading in readings:
            try:
                timestamp = datetime.fromisoformat(reading['timestamp_received'].replace('Z', '+00:00'))
                seconds_since_start = (timestamp - self.start_time).total_seconds()
                
                temperature = float(reading.get('temperature', 0))
                pressure = float(reading.get('pressure', 0))
                
                self.time_data.append(seconds_since_start)
                self.temperature_data.append(temperature)
                self.pressure_data.append(pressure)
                
            except (ValueError, TypeError, KeyError) as e:
                print(f"Error processing reading: {e}")
                continue
        
        # Update plots
        self.update_plots()
        
    def update_plots(self):
        """Update matplotlib plots with current data"""
        try:
            # Clear previous plots
            self.ax1.clear()
            self.ax2.clear()
            
            # Reapply styling
            self.setup_plot_styling()
            
            if self.time_data and self.temperature_data and self.pressure_data:
                # Plot temperature
                self.ax1.plot(self.time_data, self.temperature_data, 
                             'o-', linewidth=2, markersize=4, 
                             label='Temperature', color='#e74c3c')
                self.ax1.legend()
                
                # Plot pressure
                self.ax2.plot(self.time_data, self.pressure_data, 
                             's-', linewidth=2, markersize=4, 
                             label='Pressure', color='#3498db')
                self.ax2.legend()
                
                # Set axis limits with some padding
                if len(self.time_data) > 1:
                    time_range = max(self.time_data) - min(self.time_data)
                    padding = max(time_range * 0.05, 1)  # Minimum 1 second padding
                    self.ax1.set_xlim(min(self.time_data) - padding, 
                                     max(self.time_data) + padding)
                    self.ax2.set_xlim(min(self.time_data) - padding, 
                                     max(self.time_data) + padding)
            
            # Update data count
            data_count = len(self.time_data)
            self.data_count_label.setText(f"📈 Data Points: {data_count}")
            
            # Refresh canvas
            self.canvas.draw()
            
        except Exception as e:
            print(f"Error updating plots: {e}")
    
    def closeEvent(self, event):
        """Handle application close event"""
        # Stop timers
        self.status_timer.stop()
        self.data_timer.stop()
        
        # Close worker thread
        self.worker.running = False
        self.worker.quit()
        self.worker.wait()
        
        event.accept()

def main():
    """Main function to run the Qt5 GUI"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Sensor Data Plotter")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("IoT Sensor Systems")
    
    # Apply dark theme (optional)
    # app.setStyle('Fusion')
    
    # Create and show main window
    window = SensorPlotGUI()
    window.show()
    
    # Start event loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
