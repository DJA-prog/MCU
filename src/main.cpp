#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>

// Create BME280 instance
Adafruit_BME280 bme;

// Create LCD instance (address 0x26, 20 columns, 4 rows)
LiquidCrystal_I2C lcd(0x26, 20, 4);

// Timing variables
unsigned long lastDataSend = 0;
const unsigned long DATA_SEND_INTERVAL = 5000; // 5 seconds

// Cooler control variables
const int RELAY_PIN = 14; // GPIO14 for relay control
bool coolerRunning = false;
bool manualOverride = false; // Manual control override
unsigned long coolerStartTime = 0;
unsigned long coolerRunTime = 0;
unsigned long totalElapsedTime = 0; // Total time since first cooler start
bool coolerEverStarted = false; // Track if cooler has ever been started
float COOLER_START_TEMP = 4.5; // Start cooler at 25°C (adjustable via AT commands)
float COOLER_STOP_TEMP = 3.5;   // Stop cooler at 3.5°C (adjustable via AT commands)

// PID Controller variables
float PID_Kp = 8.66;     // Proportional gain
float PID_Ki = 0.0121;   // Integral gain
float PID_Kd = 774.21;   // Derivative gain
float PID_setpoint = 4.0; // Target temperature (adjustable via AT commands)
bool PID_enabled = false; // PID control mode (false = simple on/off, true = PID)

// PID calculation variables
float PID_error = 0;
float PID_last_error = 0;
float PID_integral = 0;
float PID_derivative = 0;
float PID_output = 0;
unsigned long PID_last_time = 0;
const unsigned long PID_SAMPLE_TIME = 1000; // PID calculation interval (1 second)

// Serial command processing
String inputString = "";
bool stringComplete = false;

void sendSensorData(float temperature, float humidity, float pressure) {
  // Create JSON payload
  StaticJsonDocument<500> doc; // Increased size for PID data
  doc["temperature"] = round(temperature * 10) / 10.0; // Round to 1 decimal
  doc["humidity"] = round(humidity * 10) / 10.0; // Round to 1 decimal
  doc["pressure"] = round(pressure * 10) / 10.0;
  doc["timestamp"] = millis() / 1000; // Send time in seconds
  doc["device"] = "ESP8266_BME280";
  doc["cooler_running"] = coolerRunning;
  doc["cooler_runtime"] = coolerRunTime / 1000; // Send in seconds
  doc["total_elapsed_time"] = totalElapsedTime / 1000; // Send in seconds
  doc["cooler_ever_started"] = coolerEverStarted;
  doc["manual_override"] = manualOverride; // Add manual override status
  
  // Add PID information
  doc["pid_enabled"] = PID_enabled;
  doc["pid_setpoint"] = PID_setpoint;
  doc["pid_output"] = PID_output;
  doc["pid_error"] = PID_error;
  doc["pid_kp"] = PID_Kp;
  doc["pid_ki"] = PID_Ki;
  doc["pid_kd"] = PID_Kd;
  
  char buffer[600]; // Increased buffer size
  serializeJson(doc, buffer);
  
  Serial.println(buffer);
}

float calculatePID(float currentTemp) {
  unsigned long now = millis();
  
  // Check if enough time has passed for PID calculation
  if (now - PID_last_time >= PID_SAMPLE_TIME) {
    // Calculate error
    PID_error = PID_setpoint - currentTemp;
    
    // Calculate integral (with windup protection)
    PID_integral += PID_error * (PID_SAMPLE_TIME / 1000.0);
    if (PID_integral > 100) PID_integral = 100;  // Clamp integral
    if (PID_integral < -100) PID_integral = -100;
    
    // Calculate derivative
    PID_derivative = (PID_error - PID_last_error) / (PID_SAMPLE_TIME / 1000.0);
    
    // Calculate PID output
    PID_output = (PID_Kp * PID_error) + (PID_Ki * PID_integral) + (PID_Kd * PID_derivative);
    
    // Store values for next iteration
    PID_last_error = PID_error;
    PID_last_time = now;
    
    // Clamp output to 0-100 range (percentage)
    if (PID_output > 100) PID_output = 100;
    if (PID_output < 0) PID_output = 0;
  }
  
  return PID_output;
}

void controlCooler(float temperature) {
  // Skip automatic control if manual override is active
  if (manualOverride) {
    // Update timing information even in manual mode
    if (coolerEverStarted) {
      totalElapsedTime = millis() - coolerStartTime;
      if (coolerRunning) {
        coolerRunTime = totalElapsedTime;
      }
    }
    return;
  }

  if (PID_enabled) {
    // PID Control Mode
    float pidOutput = calculatePID(temperature);
    
    // Convert PID output to on/off control (simple implementation)
    // You could implement PWM here for true proportional control
    if (pidOutput > 50.0) { // Threshold for turning cooler on
      if (!coolerRunning) {
        digitalWrite(RELAY_PIN, HIGH);
        coolerRunning = true;
        
        if (!coolerEverStarted) {
          coolerStartTime = millis();
          coolerEverStarted = true;
        }
        
        Serial.println("STATUS: PID Cooler STARTED!");
        Serial.print("STATUS: PID Output: ");
        Serial.print(pidOutput);
        Serial.print("%, Target: ");
        Serial.print(PID_setpoint);
        Serial.print("°C, Current: ");
        Serial.print(temperature);
        Serial.println("°C");
        
        lcd.setCursor(0, 3);
        lcd.print("PID: ON             ");
      }
    } else {
      if (coolerRunning) {
        digitalWrite(RELAY_PIN, LOW);
        coolerRunning = false;
        
        Serial.println("STATUS: PID Cooler STOPPED!");
        Serial.print("STATUS: PID Output: ");
        Serial.print(pidOutput);
        Serial.print("%, Target: ");
        Serial.print(PID_setpoint);
        Serial.print("°C, Current: ");
        Serial.print(temperature);
        Serial.println("°C");
        
        lcd.setCursor(0, 3);
        lcd.print("PID: OFF            ");
      }
    }
  } else {
    // Traditional On/Off Control Mode
    if (!coolerRunning && temperature >= COOLER_START_TEMP) {
      // Start the cooler
      digitalWrite(RELAY_PIN, HIGH);
      coolerRunning = true;
      
      if (!coolerEverStarted) {
        coolerStartTime = millis();
        coolerEverStarted = true;
      }
      
      Serial.println("STATUS: Cooler STARTED!");
      Serial.print("STATUS: Start temperature: ");
      Serial.print(temperature);
      Serial.println("°C");
      
      lcd.setCursor(0, 3);
      lcd.print("Cooler: ON          ");
    }
    else if (coolerRunning && temperature <= COOLER_STOP_TEMP) {
      // Stop the cooler
      digitalWrite(RELAY_PIN, LOW);
      coolerRunning = false;
      
      Serial.println("STATUS: Cooler STOPPED!");
      Serial.print("STATUS: Stop temperature: ");
      Serial.print(temperature);
      Serial.println("°C");
      
      lcd.setCursor(0, 3);
      lcd.print("Cooler: OFF         ");
    }
  }
  
  // Update runtime and total elapsed time
  if (coolerEverStarted) {
    totalElapsedTime = millis() - coolerStartTime;
    
    if (coolerRunning) {
      // If currently running, cooler runtime is same as total elapsed
      coolerRunTime = totalElapsedTime;
    }
    // If stopped, coolerRunTime keeps the last value when it was running
  }
}

void manualCoolerControl(bool turnOn) {
  manualOverride = true;
  
  if (turnOn && !coolerRunning) {
    // Turn cooler ON manually
    digitalWrite(RELAY_PIN, HIGH);
    coolerRunning = true;
    
    if (!coolerEverStarted) {
      coolerStartTime = millis();
      coolerEverStarted = true;
    }
    
    Serial.println("STATUS: Cooler turned ON manually!");
    lcd.setCursor(0, 3);
    lcd.print("Manual: ON          ");
    
  } else if (!turnOn && coolerRunning) {
    // Turn cooler OFF manually
    digitalWrite(RELAY_PIN, LOW);
    coolerRunning = false;
    
    Serial.println("STATUS: Cooler turned OFF manually!");
    lcd.setCursor(0, 3);
    lcd.print("Manual: OFF         ");
  }
}

void processSerialCommand(String command) {
  command.trim();
  command.toUpperCase();
  
  if (command.startsWith("AT+")) {
    String cmd = command.substring(3);
    
    if (cmd == "HELP") {
      Serial.println("OK");
      Serial.println("Available AT Commands:");
      Serial.println("AT+HELP - Show this help");
      Serial.println("AT+STATUS - Show current status");
      Serial.println("AT+COOLER=ON - Turn cooler ON manually");
      Serial.println("AT+COOLER=OFF - Turn cooler OFF manually");
      Serial.println("AT+COOLER=AUTO - Return to automatic mode");
      Serial.println("AT+SETSTART=XX.X - Set start temperature (°C)");
      Serial.println("AT+SETSTOP=XX.X - Set stop temperature (°C)");
      Serial.println("AT+GETTHRESH - Get current thresholds");
      Serial.println("AT+RESET - Reset cooler timing");
      Serial.println("AT+DATA - Get current sensor data");
      Serial.println("AT+PID=ON - Enable PID control mode");
      Serial.println("AT+PID=OFF - Disable PID control mode");
      Serial.println("AT+PIDSET=XX.X - Set PID setpoint temperature");
      Serial.println("AT+PIDKP=XX.X - Set PID Kp parameter");
      Serial.println("AT+PIDKI=XX.X - Set PID Ki parameter");
      Serial.println("AT+PIDKD=XX.X - Set PID Kd parameter");
      Serial.println("AT+PIDGET - Get all PID parameters");
      Serial.println("AT+PIDRESET - Reset PID integral and derivative");
      
    } else if (cmd == "STATUS") {
      Serial.println("OK");
      Serial.print("STATUS: Device: ESP8266_BME280, Uptime: ");
      Serial.print(millis() / 1000);
      Serial.println("s");
      Serial.print("STATUS: Cooler: ");
      Serial.print(coolerRunning ? "ON" : "OFF");
      Serial.print(", Mode: ");
      Serial.print(manualOverride ? "MANUAL" : (PID_enabled ? "PID" : "AUTO"));
      Serial.println();
      if (PID_enabled) {
        Serial.print("STATUS: PID Setpoint: ");
        Serial.print(PID_setpoint);
        Serial.print("°C, Output: ");
        Serial.print(PID_output);
        Serial.println("%");
      }
      if (coolerEverStarted) {
        Serial.print("STATUS: Runtime: ");
        Serial.print(coolerRunTime / 1000);
        Serial.print("s, Elapsed: ");
        Serial.print(totalElapsedTime / 1000);
        Serial.println("s");
      }
      
    } else if (cmd.startsWith("COOLER=")) {
      String value = cmd.substring(7);
      if (value == "ON") {
        manualCoolerControl(true);
        Serial.println("OK");
        Serial.println("STATUS: Cooler turned ON manually");
      } else if (value == "OFF") {
        manualCoolerControl(false);
        Serial.println("OK");
        Serial.println("STATUS: Cooler turned OFF manually");
      } else if (value == "AUTO") {
        manualOverride = false;
        Serial.println("OK");
        Serial.println("STATUS: Cooler returned to automatic mode");
      } else {
        Serial.println("ERROR: Invalid cooler command. Use ON, OFF, or AUTO");
      }
      
    } else if (cmd.startsWith("SETSTART=")) {
      String value = cmd.substring(9);
      float newTemp = value.toFloat();
      if (newTemp > 0 && newTemp < 100) {
        COOLER_START_TEMP = newTemp;
        Serial.println("OK");
        Serial.print("STATUS: Start temperature set to ");
        Serial.print(COOLER_START_TEMP);
        Serial.println("°C");
      } else {
        Serial.println("ERROR: Invalid temperature. Use 0-100°C");
      }
      
    } else if (cmd.startsWith("SETSTOP=")) {
      String value = cmd.substring(8);
      float newTemp = value.toFloat();
      if (newTemp >= -20 && newTemp < 50) {
        COOLER_STOP_TEMP = newTemp;
        Serial.println("OK");
        Serial.print("STATUS: Stop temperature set to ");
        Serial.print(COOLER_STOP_TEMP);
        Serial.println("°C");
      } else {
        Serial.println("ERROR: Invalid temperature. Use -20 to 50°C");
      }
      
    } else if (cmd == "GETTHRESH") {
      Serial.println("OK");
      Serial.print("STATUS: Start temperature: ");
      Serial.print(COOLER_START_TEMP);
      Serial.println("°C");
      Serial.print("STATUS: Stop temperature: ");
      Serial.print(COOLER_STOP_TEMP);
      Serial.println("°C");
      
    } else if (cmd == "RESET") {
      coolerRunning = false;
      manualOverride = false;
      coolerStartTime = 0;
      coolerRunTime = 0;
      totalElapsedTime = 0;
      coolerEverStarted = false;
      digitalWrite(RELAY_PIN, LOW);
      Serial.println("OK");
      Serial.println("STATUS: Cooler system reset");
      
    } else if (cmd == "DATA") {
      float temperature = bme.readTemperature();
      float humidity = bme.readHumidity();
      float pressure = bme.readPressure() / 100.0F;
      Serial.println("OK");
      sendSensorData(temperature, humidity, pressure);
      
    } else if (cmd.startsWith("PID=")) {
      String value = cmd.substring(4);
      if (value == "ON") {
        PID_enabled = true;
        manualOverride = false; // Disable manual override when PID is enabled
        Serial.println("OK");
        Serial.println("STATUS: PID control mode ENABLED");
      } else if (value == "OFF") {
        PID_enabled = false;
        Serial.println("OK");
        Serial.println("STATUS: PID control mode DISABLED");
      } else {
        Serial.println("ERROR: Invalid PID command. Use ON or OFF");
      }
      
    } else if (cmd.startsWith("PIDSET=")) {
      String value = cmd.substring(7);
      float newSetpoint = value.toFloat();
      if (newSetpoint >= -50 && newSetpoint <= 100) {
        PID_setpoint = newSetpoint;
        Serial.println("OK");
        Serial.print("STATUS: PID setpoint set to ");
        Serial.print(PID_setpoint);
        Serial.println("°C");
      } else {
        Serial.println("ERROR: Invalid setpoint. Use -50 to 100°C");
      }
      
    } else if (cmd.startsWith("PIDKP=")) {
      String value = cmd.substring(6);
      float newKp = value.toFloat();
      if (newKp >= 0 && newKp <= 1000) {
        PID_Kp = newKp;
        Serial.println("OK");
        Serial.print("STATUS: PID Kp set to ");
        Serial.println(PID_Kp);
      } else {
        Serial.println("ERROR: Invalid Kp value. Use 0-1000");
      }
      
    } else if (cmd.startsWith("PIDKI=")) {
      String value = cmd.substring(6);
      float newKi = value.toFloat();
      if (newKi >= 0 && newKi <= 100) {
        PID_Ki = newKi;
        Serial.println("OK");
        Serial.print("STATUS: PID Ki set to ");
        Serial.println(PID_Ki);
      } else {
        Serial.println("ERROR: Invalid Ki value. Use 0-100");
      }
      
    } else if (cmd.startsWith("PIDKD=")) {
      String value = cmd.substring(6);
      float newKd = value.toFloat();
      if (newKd >= 0 && newKd <= 10000) {
        PID_Kd = newKd;
        Serial.println("OK");
        Serial.print("STATUS: PID Kd set to ");
        Serial.println(PID_Kd);
      } else {
        Serial.println("ERROR: Invalid Kd value. Use 0-10000");
      }
      
    } else if (cmd == "PIDGET") {
      Serial.println("OK");
      Serial.print("STATUS: PID Enabled: ");
      Serial.println(PID_enabled ? "YES" : "NO");
      Serial.print("STATUS: PID Setpoint: ");
      Serial.print(PID_setpoint);
      Serial.println("°C");
      Serial.print("STATUS: PID Kp: ");
      Serial.println(PID_Kp);
      Serial.print("STATUS: PID Ki: ");
      Serial.println(PID_Ki);
      Serial.print("STATUS: PID Kd: ");
      Serial.println(PID_Kd);
      Serial.print("STATUS: PID Output: ");
      Serial.print(PID_output);
      Serial.println("%");
      Serial.print("STATUS: PID Error: ");
      Serial.print(PID_error);
      Serial.println("°C");
      
    } else if (cmd == "PIDRESET") {
      PID_integral = 0;
      PID_derivative = 0;
      PID_last_error = 0;
      PID_output = 0;
      Serial.println("OK");
      Serial.println("STATUS: PID parameters reset");
      
    } else {
      Serial.println("ERROR: Unknown command. Use AT+HELP for available commands");
    }
  } else {
    Serial.println("ERROR: Commands must start with AT+");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  // Initialize relay pin
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW); // Initialize relay OFF (LOW = OFF for your relay)
  
  Serial.println("STATUS: ESP8266 BME280 Cooler Controller Ready");
  Serial.println("STATUS: Relay initialized on GPIO14 (OFF)");
  Serial.println("STATUS: Send AT+HELP for available commands");

  // Initialize I2C with custom pins (SDA = 5, SCL = 4)
  Wire.begin(5, 4); // GPIO5 = D1, GPIO4 = D2

  // Initialize LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("BME280 Sensor");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");

  Serial.println("STATUS: Initializing BME280 sensor");

  // Initialize BME280
  if (bme.begin(0x76)) {
    Serial.println("STATUS: BME280 sensor ready");
    lcd.setCursor(0, 1);
    lcd.print("BME280 Ready!       ");
  } else {
    Serial.println("ERROR: BME280 sensor initialization failed");
    lcd.setCursor(0, 1);
    lcd.print("BME280 Error!       ");
  }
  
  delay(2000);
  lcd.clear();
  
  // Display cooler thresholds
  Serial.println("STATUS: Cooler Control Configuration:");
  Serial.print("STATUS: Start temperature: ");
  Serial.print(COOLER_START_TEMP);
  Serial.println("°C");
  Serial.print("STATUS: Stop temperature: ");
  Serial.print(COOLER_STOP_TEMP);
  Serial.println("°C");
  
  // Reserve string space for serial input
  inputString.reserve(200);
}

void loop() {
  // Process serial commands
  if (stringComplete) {
    processSerialCommand(inputString);
    inputString = "";
    stringComplete = false;
  }
  
  // Read sensor values
  float temperature = bme.readTemperature();
  float humidity = bme.readHumidity();
  float pressure = bme.readPressure() / 100.0F;
  
  // Control cooler based on temperature (if not in manual override)
  controlCooler(temperature);
  
  // Display on LCD (20x4 format)
  lcd.clear();
  
  // Line 1: Temperature and humidity
  lcd.setCursor(0, 0);
  lcd.print("T:");
  lcd.print(temperature, 1);
  lcd.print("C H:");
  lcd.print(humidity, 1);
  lcd.print("%");
  
  // Line 2: Pressure
  lcd.setCursor(0, 1);
  lcd.print("P:");
  lcd.print(pressure, 1);
  lcd.print(" hPa");
  
  // Line 3: Cooler status and runtime
  lcd.setCursor(0, 2);
  if (coolerRunning) {
    if (manualOverride) {
      lcd.print("Manual: ON ");
    } else {
      lcd.print("Auto: ON ");
    }
    lcd.print(coolerRunTime / 1000);
    lcd.print("s");
  } else if (coolerEverStarted) {
    if (manualOverride) {
      lcd.print("Manual: OFF ");
    } else {
      lcd.print("Auto: OFF ");
    }
    lcd.print(totalElapsedTime / 1000);
    lcd.print("s");
  } else {
    lcd.print("Cooler: READY");
  }
  
  // Line 4: System uptime
  lcd.setCursor(0, 3);
  lcd.print("Uptime: ");
  lcd.print(millis() / 1000);
  lcd.print("s");

  // Send sensor data via serial every 5 seconds
  unsigned long currentTime = millis();
  if (currentTime - lastDataSend >= DATA_SEND_INTERVAL) {
    sendSensorData(temperature, humidity, pressure);
    lastDataSend = currentTime;
  }

  delay(2000);
}

// Serial event handler
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      stringComplete = true;
    } else if (inChar != '\r') {
      inputString += inChar;
    }
  }
}