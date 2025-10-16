#!/usr/bin/env python3
"""
Real-time Sensor Data Plotting GUI using PyQt5
Connects to ESP8266 via Serial and displays live plots
"""

import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QPushButton, QLabel, 
                            QLineEdit, QCheckBox, QGroupBox, QMessageBox,
                            QSplitter, QFrame, QTabWidget, QComboBox)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QPalette, QColor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import serial
import serial.tools.list_ports
import json
from datetime import datetime, timedelta
import threading
import queue
import numpy as np
import time

class SerialWorker(QThread):
    """Worker thread for serial communication with ESP8266"""
    data_received = pyqtSignal(dict)
    status_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, port, baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.serial_connection = None
        self.data_buffer = []
        
    def connect_serial(self):
        """Connect to serial port"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                write_timeout=1
            )
            time.sleep(2)  # Give time for connection to establish
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to connect to {self.port}: {str(e)}")
            return False
    
    def send_at_command(self, command):
        """Send AT command to ESP8266"""
        try:
            if not self.serial_connection or not self.serial_connection.is_open:
                if not self.connect_serial():
                    return False
                    
            command_line = f"{command}\n"
            self.serial_connection.write(command_line.encode())
            self.serial_connection.flush()
            return True
        except Exception as e:
            self.error_occurred.emit(f"Failed to send command: {str(e)}")
            return False
    
    def cooler_on(self):
        """Turn cooler ON"""
        return self.send_at_command("AT+COOLER=ON")
    
    def cooler_off(self):
        """Turn cooler OFF"""
        return self.send_at_command("AT+COOLER=OFF")
    
    def cooler_auto(self):
        """Set cooler to automatic mode"""
        return self.send_at_command("AT+COOLER=AUTO")
    
    def get_status(self):
        """Get device status"""
        return self.send_at_command("AT+STATUS")
    
    def get_data(self):
        """Get current sensor data"""
        return self.send_at_command("AT+DATA")
    
    def set_start_temp(self, temp):
        """Set start temperature threshold"""
        return self.send_at_command(f"AT+SETSTART={temp}")
    
    def set_stop_temp(self, temp):
        """Set stop temperature threshold"""
        return self.send_at_command(f"AT+SETSTOP={temp}")
    
    def get_thresholds(self):
        """Get current temperature thresholds"""
        return self.send_at_command("AT+GETTHRESH")
    
    def run(self):
        """Main thread loop for reading serial data"""
        while self.running:
            try:
                if not self.serial_connection or not self.serial_connection.is_open:
                    if not self.connect_serial():
                        time.sleep(5)  # Wait before retrying
                        continue
                
                if self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line:
                        self.process_serial_line(line)
                        
                time.sleep(0.1)  # Small delay to prevent high CPU usage
                
            except Exception as e:
                self.error_occurred.emit(f"Serial communication error: {str(e)}")
                time.sleep(1)
    
    def process_serial_line(self, line):
        """Process a line received from serial"""
        try:
            # Try to parse as JSON (sensor data)
            if line.startswith('{') and line.endswith('}'):
                data = json.loads(line)
                if 'temperature' in data:
                    # Add to data buffer for plotting
                    data['timestamp_received'] = datetime.now().isoformat()
                    self.data_buffer.append(data)
                    
                    # Keep only last 500 readings
                    if len(self.data_buffer) > 500:
                        self.data_buffer = self.data_buffer[-500:]
                    
                    # Emit the latest data
                    self.data_received.emit(data)
                    
            # Handle status messages
            elif line.startswith('STATUS:'):
                # Parse status information
                status_info = line[7:].strip()  # Remove "STATUS: " prefix
                
                # Create a status dictionary from the message
                status = {
                    'message': status_info,
                    'timestamp': datetime.now().isoformat()
                }
                self.status_received.emit(status)
                
            # Handle OK/ERROR responses
            elif line in ['OK', 'ERROR']:
                print(f"Command response: {line}")
                
        except json.JSONDecodeError:
            # Not JSON, might be status message or other output
            if line.startswith('ERROR:'):
                self.error_occurred.emit(line[6:].strip())
            else:
                print(f"Serial: {line}")
        except Exception as e:
            print(f"Error processing serial line: {e}")
    
    def get_buffered_data(self):
        """Get all buffered data for plotting"""
        return self.data_buffer.copy()
    
    def stop(self):
        """Stop the serial worker"""
        self.running = False
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()

class SensorPlotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sensor Data Plotter - Serial Interface")
        # Optimized for 1366x768 screen - leave some margin for taskbar/panels
        self.setGeometry(50, 50, 1280, 680)
        self.setMinimumSize(1000, 600)
        
        # Serial configuration
        self.serial_port = "/dev/ttyUSB0"  # Default port
        self.baudrate = 115200
        
        # Data storage
        self.time_data = []
        self.temperature_data = []
        self.humidity_data = []
        self.pressure_data = []
        self.start_time = None
        
        # Status variables
        self.is_connected = False
        self.is_recording = False
        self.auto_refresh = True
        
        # Setup worker thread
        self.worker = SerialWorker(self.serial_port, self.baudrate)
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
        
        # Main layout - compact for 1366x768 screen
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(5)  # Reduced spacing
        main_layout.setContentsMargins(5, 5, 5, 5)  # Reduced margins
        
        # Create control panel
        self.create_control_panel(main_layout)
        
        # Create status panel
        self.create_status_panel(main_layout)
        
        # Create plot area
        self.create_plot_area(main_layout)
        
    def create_control_panel(self, parent_layout):
        """Create control buttons and settings"""
        control_group = QGroupBox("Controls")
        control_layout = QHBoxLayout(control_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Recording")
        self.start_btn.clicked.connect(self.start_recording)
        self.start_btn.setMinimumHeight(28)  # Reduced height
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop Recording")
        self.stop_btn.clicked.connect(self.stop_recording)
        self.stop_btn.setMinimumHeight(28)  # Reduced height
        button_layout.addWidget(self.stop_btn)
        
        self.refresh_btn = QPushButton("Refresh Data")
        self.refresh_btn.clicked.connect(self.manual_refresh)
        self.refresh_btn.setMinimumHeight(28)  # Reduced height
        button_layout.addWidget(self.refresh_btn)
        
        self.clear_btn = QPushButton("Clear Plot")
        self.clear_btn.clicked.connect(self.clear_data)
        self.clear_btn.setMinimumHeight(28)  # Reduced height
        button_layout.addWidget(self.clear_btn)
        
        # Add separator
        button_layout.addStretch()
        
        # Cooler control buttons
        self.cooler_on_btn = QPushButton("Cooler ON")
        self.cooler_on_btn.clicked.connect(self.turn_cooler_on)
        self.cooler_on_btn.setMinimumHeight(28)  # Reduced height
        self.cooler_on_btn.setStyleSheet("background-color: #28a745;")
        button_layout.addWidget(self.cooler_on_btn)
        
        self.cooler_off_btn = QPushButton("Cooler OFF")
        self.cooler_off_btn.clicked.connect(self.turn_cooler_off)
        self.cooler_off_btn.setMinimumHeight(28)  # Reduced height
        self.cooler_off_btn.setStyleSheet("background-color: #dc3545;")
        button_layout.addWidget(self.cooler_off_btn)
        
        self.cooler_auto_btn = QPushButton("Auto Mode")
        self.cooler_auto_btn.clicked.connect(self.set_cooler_auto)
        self.cooler_auto_btn.setMinimumHeight(28)  # Reduced height
        self.cooler_auto_btn.setStyleSheet("background-color: #ffc107; color: black;")
        button_layout.addWidget(self.cooler_auto_btn)
        
        button_layout.addStretch()
        
        # Settings
        settings_layout = QHBoxLayout()
        
        self.auto_refresh_cb = QCheckBox("Auto Refresh")
        self.auto_refresh_cb.setChecked(True)
        self.auto_refresh_cb.stateChanged.connect(self.toggle_auto_refresh)
        settings_layout.addWidget(self.auto_refresh_cb)
        
        settings_layout.addWidget(QLabel("Serial Port:"))
        self.port_entry = QLineEdit(self.serial_port)
        self.port_entry.setMinimumWidth(150)
        settings_layout.addWidget(self.port_entry)
        
        settings_layout.addWidget(QLabel("Baudrate:"))
        self.baudrate_entry = QLineEdit(str(self.baudrate))
        self.baudrate_entry.setMinimumWidth(100)
        settings_layout.addWidget(self.baudrate_entry)
        
        connect_btn = QPushButton("Reconnect")
        connect_btn.clicked.connect(self.reconnect_serial)
        connect_btn.clicked.connect(self.reconnect_serial)
        connect_btn.setMinimumHeight(30)
        settings_layout.addWidget(connect_btn)
        
        # Combine layouts
        control_layout.addLayout(button_layout)
        control_layout.addStretch()
        control_layout.addLayout(settings_layout)
        
        parent_layout.addWidget(control_group)
        
    def create_status_panel(self, parent_layout):
        """Create status information panel"""
        status_group = QGroupBox("Status")
        status_layout = QHBoxLayout(status_group)
        
        # Status indicators
        status_left = QHBoxLayout()
        
        self.connection_label = QLabel("Disconnected")
        self.connection_label.setStyleSheet("color: red; font-weight: bold;")
        status_left.addWidget(self.connection_label)
        
        self.recording_label = QLabel("Not Recording")
        self.recording_label.setStyleSheet("color: orange; font-weight: bold;")
        status_left.addWidget(self.recording_label)
        
        self.data_count_label = QLabel("Data Points: 0")
        status_left.addWidget(self.data_count_label)
        
        status_left.addStretch()
        
        # Current readings
        status_right = QHBoxLayout()
        
        self.temp_label = QLabel("Temp: -- °C")
        self.temp_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        status_right.addWidget(self.temp_label)
        
        self.pressure_label = QLabel("Pressure: -- hPa")
        self.pressure_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        status_right.addWidget(self.pressure_label)
        
        self.humidity_label = QLabel("Humidity: -- %")
        self.humidity_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        status_right.addWidget(self.humidity_label)
        
        self.cooler_status_label = QLabel("Cooler: --")
        self.cooler_status_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        status_right.addWidget(self.cooler_status_label)
        
        # Combine layouts
        status_layout.addLayout(status_left)
        status_layout.addStretch()
        status_layout.addLayout(status_right)
        
        parent_layout.addWidget(status_group)
        
    def create_plot_area(self, parent_layout):
        """Create matplotlib plotting area with tabs"""
        plot_group = QGroupBox("Real-time Sensor Data")
        plot_layout = QVBoxLayout(plot_group)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create individual tabs
        self.create_temperature_tab()
        self.create_humidity_tab()
        self.create_pressure_tab()
        self.create_overview_tab()
        
        plot_layout.addWidget(self.tab_widget)
        parent_layout.addWidget(plot_group)
    
    def create_temperature_tab(self):
        """Create temperature plot tab"""
        temp_widget = QWidget()
        temp_layout = QVBoxLayout(temp_widget)
        
        # Create matplotlib figure for temperature - optimized for 1366x768
        self.temp_figure = Figure(figsize=(10, 4.5), facecolor='white')
        self.temp_canvas = FigureCanvas(self.temp_figure)
        self.temp_ax = self.temp_figure.add_subplot(111)
        
        # Add navigation toolbar
        temp_toolbar = NavigationToolbar(self.temp_canvas, temp_widget)
        
        temp_layout.addWidget(temp_toolbar)
        temp_layout.addWidget(self.temp_canvas)
        
        self.tab_widget.addTab(temp_widget, "Temperature")
    
    def create_humidity_tab(self):
        """Create humidity plot tab"""
        humidity_widget = QWidget()
        humidity_layout = QVBoxLayout(humidity_widget)
        
        # Create matplotlib figure for humidity - optimized for 1366x768
        self.humidity_figure = Figure(figsize=(10, 4.5), facecolor='white')
        self.humidity_canvas = FigureCanvas(self.humidity_figure)
        self.humidity_ax = self.humidity_figure.add_subplot(111)
        
        # Add navigation toolbar
        humidity_toolbar = NavigationToolbar(self.humidity_canvas, humidity_widget)
        
        humidity_layout.addWidget(humidity_toolbar)
        humidity_layout.addWidget(self.humidity_canvas)
        
        self.tab_widget.addTab(humidity_widget, "Humidity")
    
    def create_pressure_tab(self):
        """Create pressure plot tab"""
        pressure_widget = QWidget()
        pressure_layout = QVBoxLayout(pressure_widget)
        
        # Create matplotlib figure for pressure - optimized for 1366x768
        self.pressure_figure = Figure(figsize=(10, 4.5), facecolor='white')
        self.pressure_canvas = FigureCanvas(self.pressure_figure)
        self.pressure_ax = self.pressure_figure.add_subplot(111)
        
        # Add navigation toolbar
        pressure_toolbar = NavigationToolbar(self.pressure_canvas, pressure_widget)
        
        pressure_layout.addWidget(pressure_toolbar)
        pressure_layout.addWidget(self.pressure_canvas)
        
        self.tab_widget.addTab(pressure_widget, "Pressure")
    
    def create_overview_tab(self):
        """Create overview tab with all plots"""
        overview_widget = QWidget()
        overview_layout = QVBoxLayout(overview_widget)
        
        # Create matplotlib figure for overview - optimized for 1366x768
        self.overview_figure = Figure(figsize=(10, 5.5), facecolor='white')
        self.overview_canvas = FigureCanvas(self.overview_figure)
        
        # Create subplots for overview - more compact spacing
        self.overview_ax1 = self.overview_figure.add_subplot(311)
        self.overview_ax2 = self.overview_figure.add_subplot(312)
        self.overview_ax3 = self.overview_figure.add_subplot(313)
        
        # Adjust subplot spacing for compact layout
        self.overview_figure.subplots_adjust(hspace=0.4)
        
        # Add navigation toolbar
        overview_toolbar = NavigationToolbar(self.overview_canvas, overview_widget)
        
        overview_layout.addWidget(overview_toolbar)
        overview_layout.addWidget(self.overview_canvas)
        
        self.tab_widget.addTab(overview_widget, "Overview")
        
    def setup_plots(self):
        """Initialize plot configuration"""
        self.setup_individual_plot_styling()
        self.setup_overview_plot_styling()
        
    def setup_individual_plot_styling(self):
        """Configure individual plot appearance"""
        # Temperature plot
        self.temp_ax.set_title('Temperature vs Time', fontsize=14, fontweight='bold', pad=20)
        self.temp_ax.set_xlabel('Time (seconds since start)', fontsize=12)
        self.temp_ax.set_ylabel('Temperature (°C)', fontsize=12)
        self.temp_ax.grid(True, alpha=0.3)
        self.temp_ax.set_facecolor('#f8f9fa')
        
        # Humidity plot
        self.humidity_ax.set_title('Humidity vs Time', fontsize=14, fontweight='bold', pad=20)
        self.humidity_ax.set_xlabel('Time (seconds since start)', fontsize=12)
        self.humidity_ax.set_ylabel('Humidity (%)', fontsize=12)
        self.humidity_ax.grid(True, alpha=0.3)
        self.humidity_ax.set_facecolor('#f8f9fa')
        
        # Pressure plot
        self.pressure_ax.set_title('Pressure vs Time', fontsize=14, fontweight='bold', pad=20)
        self.pressure_ax.set_xlabel('Time (seconds since start)', fontsize=12)
        self.pressure_ax.set_ylabel('Pressure (hPa)', fontsize=12)
        self.pressure_ax.grid(True, alpha=0.3)
        self.pressure_ax.set_facecolor('#f8f9fa')
        
        # Draw individual canvases
        self.temp_figure.tight_layout(pad=3.0)
        self.humidity_figure.tight_layout(pad=3.0)
        self.pressure_figure.tight_layout(pad=3.0)
        self.temp_canvas.draw()
        self.humidity_canvas.draw()
        self.pressure_canvas.draw()
    
    def setup_overview_plot_styling(self):
        """Configure overview plot appearance"""
        # Temperature plot
        self.overview_ax1.set_title('Temperature vs Time', fontsize=12, fontweight='bold')
        self.overview_ax1.set_ylabel('Temperature (°C)', fontsize=10)
        self.overview_ax1.grid(True, alpha=0.3)
        self.overview_ax1.set_facecolor('#f8f9fa')
        
        # Humidity plot
        self.overview_ax2.set_title('Humidity vs Time', fontsize=12, fontweight='bold')
        self.overview_ax2.set_ylabel('Humidity (%)', fontsize=10)
        self.overview_ax2.grid(True, alpha=0.3)
        self.overview_ax2.set_facecolor('#f8f9fa')
        
        # Pressure plot
        self.overview_ax3.set_title('Pressure vs Time', fontsize=12, fontweight='bold')
        self.overview_ax3.set_xlabel('Time (seconds since start)', fontsize=10)
        self.overview_ax3.set_ylabel('Pressure (hPa)', fontsize=10)
        self.overview_ax3.grid(True, alpha=0.3)
        self.overview_ax3.set_facecolor('#f8f9fa')
        
        # Adjust layout
        self.overview_figure.tight_layout(pad=2.0)
        self.overview_canvas.draw()
        
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
        """Setup Qt timers for periodic updates and start serial worker"""
        # Start the serial worker thread
        self.worker.start()
        
        # Status update timer (less frequent since data comes automatically)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # Every 5 seconds
        
        # Initial status update
        self.update_status()
        
    def toggle_auto_refresh(self, state):
        """Toggle auto refresh functionality"""
        self.auto_refresh = state == Qt.Checked
        
    def start_recording(self):
        """Start data recording (always recording with serial)"""
        self.is_recording = True
        self.start_time = datetime.now()
        self.clear_data()
        self.show_success_message("Started data recording!")
        
    def stop_recording(self):
        """Stop data recording"""
        self.is_recording = False
        self.show_success_message("Stopped data recording!")
        
        # Run in separate thread to avoid blocking UI
        threading.Thread(target=stop_async, daemon=True).start()
    
    def show_success_message(self, message):
        """Show success message in main thread"""
        print(f"Success: {message}")
    
    def show_error_message(self, message):
        """Show error message in main thread"""
        print(f"Error: {message}")
    
    def turn_cooler_on(self):
        """Turn cooler ON via serial command"""
        if self.worker.cooler_on():
            self.show_success_message("Cooler ON command sent!")
        else:
            self.show_error_message("Failed to send cooler ON command")
    
    def turn_cooler_off(self):
        """Turn cooler OFF via serial command"""
        if self.worker.cooler_off():
            self.show_success_message("Cooler OFF command sent!")
        else:
            self.show_error_message("Failed to send cooler OFF command")
    
    def set_cooler_auto(self):
        """Set cooler to automatic mode via serial command"""
        if self.worker.cooler_auto():
            self.show_success_message("Cooler set to automatic mode!")
        else:
            self.show_error_message("Failed to set cooler to auto mode")
        
    def reconnect_serial(self):
        """Reconnect with new serial settings"""
        new_port = self.port_entry.text().strip()
        new_baudrate = int(self.baudrate_entry.text().strip())
        
        # Stop current worker
        self.worker.stop()
        self.worker.wait()
        
        # Update settings
        self.serial_port = new_port
        self.baudrate = new_baudrate
        
        # Create new worker
        self.worker = SerialWorker(self.serial_port, self.baudrate)
        self.worker.data_received.connect(self.process_new_data)
        self.worker.status_received.connect(self.update_status_display)
        self.worker.error_occurred.connect(self.show_error)
        self.worker.start()
        
        self.show_success_message(f"Reconnected to {new_port} at {new_baudrate} baud")
            
    def manual_refresh(self):
        """Manually refresh data"""
        self.refresh_plots()
        
    def clear_data(self):
        """Clear all plotted data"""
        self.time_data.clear()
        self.temperature_data.clear()
        self.humidity_data.clear()
        self.pressure_data.clear()
        self.start_time = None
        self.update_plots()
        
    def update_status(self):
        """Update connection and recording status"""
        self.worker.get_status()
        
    def fetch_data(self):
        """Fetch data from serial"""
        if self.auto_refresh:
            self.worker.get_data()
        
    def update_status_display(self, status_data):
        """Update status labels with current data"""
        # Connection status
        self.is_connected = True
        self.connection_label.setText("Connected")
        self.connection_label.setStyleSheet("color: green; font-weight: bold;")
        
        # Recording status
        self.is_recording = status_data.get('is_recording', False)
        if self.is_recording:
            self.recording_label.setText("Recording")
            self.recording_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.recording_label.setText("Not Recording")
            self.recording_label.setStyleSheet("color: orange; font-weight: bold;")
        
        # Data count
        total_readings = status_data.get('total_readings', 0)
        self.data_count_label.setText(f"Total Readings: {total_readings}")
        
        # Latest reading
        latest = status_data.get('last_reading')
        if latest:
            temp = latest.get('temperature', '--')
            pressure = latest.get('pressure', '--')
            humidity = latest.get('humidity', '--')
            cooler_running = latest.get('cooler_running', False)
            manual_override = latest.get('manual_override', False)
            
            self.temp_label.setText(f"Temp: {temp} °C")
            self.pressure_label.setText(f"Pressure: {pressure} hPa")
            self.humidity_label.setText(f"Humidity: {humidity} %")
            
            # Cooler status
            if cooler_running is not None:
                mode = "MANUAL" if manual_override else "AUTO"
                status = "ON" if cooler_running else "OFF"
                self.cooler_status_label.setText(f"Cooler: {status} ({mode})")
                
                if cooler_running:
                    self.cooler_status_label.setStyleSheet("color: green; font-weight: bold; font-size: 12px;")
                else:
                    self.cooler_status_label.setStyleSheet("color: red; font-weight: bold; font-size: 12px;")
            else:
                self.cooler_status_label.setText("Cooler: --")
                self.cooler_status_label.setStyleSheet("color: gray; font-weight: bold; font-size: 12px;")
        
    def show_error(self, message):
        """Show error message and update disconnected status"""
        print(f"Error: {message}")
        
        # Update status to disconnected
        self.is_connected = False
        self.is_recording = False
        self.connection_label.setText("Disconnected")
        self.connection_label.setStyleSheet("color: red; font-weight: bold;")
        self.recording_label.setText("Not Recording")
        self.recording_label.setStyleSheet("color: orange; font-weight: bold;")
        self.temp_label.setText("Temp: -- °C")
        self.pressure_label.setText("Pressure: -- hPa")
        self.humidity_label.setText("Humidity: -- %")
        self.cooler_status_label.setText("Cooler: --")
        
    def process_new_data(self, reading):
        """Process new data from serial communication"""
        if not reading:
            return
            
        try:
            # Set start time from first reading if not set
            if self.start_time is None:
                self.start_time = datetime.now()
            
            # Get timestamp - use current time since serial data is real-time
            timestamp = datetime.now()
            seconds_since_start = (timestamp - self.start_time).total_seconds()
            
            temperature = float(reading.get('temperature', 0))
            humidity = float(reading.get('humidity', 0))
            pressure = float(reading.get('pressure', 0))
            
            # Add to data lists
            self.time_data.append(seconds_since_start)
            self.temperature_data.append(temperature)
            self.humidity_data.append(humidity)
            self.pressure_data.append(pressure)
            
            # Keep only recent data (last 500 points)
            max_points = 500
            if len(self.time_data) > max_points:
                self.time_data = self.time_data[-max_points:]
                self.temperature_data = self.temperature_data[-max_points:]
                self.humidity_data = self.humidity_data[-max_points:]
                self.pressure_data = self.pressure_data[-max_points:]
            
            # Update plots
            self.update_plots()
            
        except (ValueError, KeyError, TypeError) as e:
            print(f"Error processing data: {e}")
        
    def update_plots(self):
        """Update matplotlib plots with current data"""
        try:
            # Update data count
            data_count = len(self.time_data)
            self.data_count_label.setText(f"Data Points: {data_count}")
            
            if self.time_data and self.temperature_data and self.humidity_data and self.pressure_data:
                # Update individual plot tabs
                self.update_temperature_plot()
                self.update_humidity_plot()
                self.update_pressure_plot()
                self.update_overview_plot()
            else:
                # Clear all plots if no data
                self.clear_all_plots()
                
        except Exception as e:
            print(f"Error updating plots: {e}")
    
    def refresh_plots(self):
        """Refresh plots with current buffered data"""
        try:
            buffered_data = self.worker.get_buffered_data()
            if buffered_data:
                # Process the buffered data to rebuild plot data
                self.time_data.clear()
                self.temperature_data.clear()
                self.humidity_data.clear()
                self.pressure_data.clear()
                
                if self.start_time is None:
                    self.start_time = datetime.now()
                
                for data_point in buffered_data:
                    timestamp = datetime.now()  # Use current time for simplicity
                    seconds_since_start = (timestamp - self.start_time).total_seconds()
                    
                    self.time_data.append(seconds_since_start)
                    self.temperature_data.append(float(data_point.get('temperature', 0)))
                    self.humidity_data.append(float(data_point.get('humidity', 0)))
                    self.pressure_data.append(float(data_point.get('pressure', 0)))
                
                self.update_plots()
        except Exception as e:
            print(f"Error refreshing plots: {e}")
    
    def update_temperature_plot(self):
        """Update temperature plot"""
        self.temp_ax.clear()
        self.temp_ax.set_title('Temperature vs Time', fontsize=14, fontweight='bold', pad=20)
        self.temp_ax.set_xlabel('Time (seconds since start)', fontsize=12)
        self.temp_ax.set_ylabel('Temperature (°C)', fontsize=12)
        self.temp_ax.grid(True, alpha=0.3)
        self.temp_ax.set_facecolor('#f8f9fa')
        
        self.temp_ax.plot(self.time_data, self.temperature_data, 
                         'o-', linewidth=2, markersize=3, 
                         label='Temperature', color='#e74c3c')
        self.temp_ax.legend()
        
        if len(self.time_data) > 1:
            time_range = max(self.time_data) - min(self.time_data)
            padding = max(time_range * 0.05, 1)
            self.temp_ax.set_xlim(min(self.time_data) - padding, 
                                 max(self.time_data) + padding)
        
        self.temp_figure.tight_layout(pad=1.5)  # Reduced padding for 1366x768
        self.temp_canvas.draw()
    
    def update_humidity_plot(self):
        """Update humidity plot"""
        self.humidity_ax.clear()
        self.humidity_ax.set_title('Humidity vs Time', fontsize=14, fontweight='bold', pad=20)
        self.humidity_ax.set_xlabel('Time (seconds since start)', fontsize=12)
        self.humidity_ax.set_ylabel('Humidity (%)', fontsize=12)
        self.humidity_ax.grid(True, alpha=0.3)
        self.humidity_ax.set_facecolor('#f8f9fa')
        
        self.humidity_ax.plot(self.time_data, self.humidity_data, 
                             '^-', linewidth=2, markersize=3, 
                             label='Humidity', color='#3498db')
        self.humidity_ax.legend()
        
        if len(self.time_data) > 1:
            time_range = max(self.time_data) - min(self.time_data)
            padding = max(time_range * 0.05, 1)
            self.humidity_ax.set_xlim(min(self.time_data) - padding, 
                                     max(self.time_data) + padding)
        
        self.humidity_figure.tight_layout(pad=1.5)  # Reduced padding for 1366x768
        self.humidity_canvas.draw()
    
    def update_pressure_plot(self):
        """Update pressure plot"""
        self.pressure_ax.clear()
        self.pressure_ax.set_title('Pressure vs Time', fontsize=14, fontweight='bold', pad=20)
        self.pressure_ax.set_xlabel('Time (seconds since start)', fontsize=12)
        self.pressure_ax.set_ylabel('Pressure (hPa)', fontsize=12)
        self.pressure_ax.grid(True, alpha=0.3)
        self.pressure_ax.set_facecolor('#f8f9fa')
        
        self.pressure_ax.plot(self.time_data, self.pressure_data, 
                             's-', linewidth=2, markersize=3, 
                             label='Pressure', color='#f39c12')
        self.pressure_ax.legend()
        
        if len(self.time_data) > 1:
            time_range = max(self.time_data) - min(self.time_data)
            padding = max(time_range * 0.05, 1)
            self.pressure_ax.set_xlim(min(self.time_data) - padding, 
                                     max(self.time_data) + padding)
        
        self.pressure_figure.tight_layout(pad=1.5)  # Reduced padding for 1366x768
        self.pressure_canvas.draw()
    
    def update_overview_plot(self):
        """Update overview plot with all sensors"""
        # Clear all overview plots
        self.overview_ax1.clear()
        self.overview_ax2.clear()
        self.overview_ax3.clear()
        
        # Reapply styling
        self.overview_ax1.set_title('Temperature', fontsize=12, fontweight='bold')
        self.overview_ax1.set_ylabel('Temperature (°C)', fontsize=10)
        self.overview_ax1.grid(True, alpha=0.3)
        self.overview_ax1.set_facecolor('#f8f9fa')
        
        self.overview_ax2.set_title('Humidity', fontsize=12, fontweight='bold')
        self.overview_ax2.set_ylabel('Humidity (%)', fontsize=10)
        self.overview_ax2.grid(True, alpha=0.3)
        self.overview_ax2.set_facecolor('#f8f9fa')
        
        self.overview_ax3.set_title('Pressure', fontsize=12, fontweight='bold')
        self.overview_ax3.set_xlabel('Time (seconds since start)', fontsize=10)
        self.overview_ax3.set_ylabel('Pressure (hPa)', fontsize=10)
        self.overview_ax3.grid(True, alpha=0.3)
        self.overview_ax3.set_facecolor('#f8f9fa')
        
        # Plot data
        self.overview_ax1.plot(self.time_data, self.temperature_data, 
                              'o-', linewidth=1, markersize=2, 
                              label='Temperature', color='#e74c3c')
        self.overview_ax1.legend(fontsize=8)
        
        self.overview_ax2.plot(self.time_data, self.humidity_data, 
                              '^-', linewidth=1, markersize=2, 
                              label='Humidity', color='#3498db')
        self.overview_ax2.legend(fontsize=8)
        
        self.overview_ax3.plot(self.time_data, self.pressure_data, 
                              's-', linewidth=1, markersize=2, 
                              label='Pressure', color='#f39c12')
        self.overview_ax3.legend(fontsize=8)
        
        # Set axis limits
        if len(self.time_data) > 1:
            time_range = max(self.time_data) - min(self.time_data)
            padding = max(time_range * 0.05, 1)
            xlim = (min(self.time_data) - padding, max(self.time_data) + padding)
            self.overview_ax1.set_xlim(xlim)
            self.overview_ax2.set_xlim(xlim)
            self.overview_ax3.set_xlim(xlim)
        
        self.overview_figure.tight_layout(pad=1.0)  # Reduced padding for 1366x768
        self.overview_canvas.draw()
    
    def clear_all_plots(self):
        """Clear all plots when no data is available"""
        # Clear individual plots
        self.temp_ax.clear()
        self.humidity_ax.clear()
        self.pressure_ax.clear()
        
        # Clear overview plots
        self.overview_ax1.clear()
        self.overview_ax2.clear()
        self.overview_ax3.clear()
        
        # Reapply styling
        self.setup_individual_plot_styling()
        self.setup_overview_plot_styling()
    
    def closeEvent(self, a0):
        """Handle application close event"""
        # Stop timers if they exist
        if hasattr(self, 'status_timer'):
            self.status_timer.stop()
        
        # Close worker thread
        if hasattr(self, 'worker'):
            self.worker.stop()
            self.worker.wait()
        
        a0.accept()

def main():
    """Main function to run the Qt5 GUI with error handling"""
    try:
        app = QApplication(sys.argv)
        
        # Set application properties
        app.setApplicationName("Sensor Data Plotter")
        app.setApplicationVersion("2.0")
        app.setOrganizationName("IoT Sensor Systems")
        
        # Use Fusion style for better compatibility on 1366x768 screens
        app.setStyle('Fusion')
        
        # Create and show main window
        window = SensorPlotGUI()
        window.show()
        
        # Start event loop
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
