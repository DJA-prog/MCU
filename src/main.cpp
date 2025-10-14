#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <LiquidCrystal_I2C.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "secrets.h"

// Create BME280 instance
Adafruit_BME280 bme;

// Create LCD instance (address 0x26, 20 columns, 4 rows)
LiquidCrystal_I2C lcd(0x26, 20, 4);

// WiFi and MQTT clients
WiFiClient espClient;
PubSubClient client(espClient);

// Timing variables
unsigned long lastMqttPublish = 0;
const unsigned long MQTT_PUBLISH_INTERVAL = 5000; // 5 seconds

// Cooler control variables
const int RELAY_PIN = 14; // GPIO14 for relay control
bool coolerRunning = false;
bool manualOverride = false; // Manual control override
unsigned long coolerStartTime = 0;
unsigned long coolerRunTime = 0;
unsigned long totalElapsedTime = 0; // Total time since first cooler start
bool coolerEverStarted = false; // Track if cooler has ever been started
bool mqttConnectedOnce = false; // Track if MQTT has been connected at least once
const float COOLER_START_TEMP = 25.0; // Start cooler at 25°C (adjust as needed)
const float COOLER_STOP_TEMP = 3.5;   // Stop cooler at 3.5°C

void setupWiFi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(WIFI_SSID);
  
  lcd.setCursor(0, 2);
  lcd.print("Connecting WiFi...  ");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  
  lcd.setCursor(0, 2);
  lcd.print("WiFi Connected!     ");
}

void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    lcd.setCursor(0, 3);
    lcd.print("MQTT Connecting...  ");
    
    if (client.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASSWORD)) {
      Serial.println("connected");
      lcd.setCursor(0, 3);
      lcd.print("MQTT Connected!     ");
      
      // Subscribe to control topic for remote cooler control
      client.subscribe("sensors/cooler/control");
      Serial.println("📡 Subscribed to sensors/cooler/control");
      
      // Turn on cooler after first MQTT connection
      if (!mqttConnectedOnce) {
        mqttConnectedOnce = true;
        digitalWrite(RELAY_PIN, HIGH);  // Turn cooler ON
        coolerRunning = true;
        coolerStartTime = millis();
        coolerEverStarted = true;
        
        Serial.println("🧊 Cooler STARTED after MQTT connection!");
        
        // Update LCD
        lcd.setCursor(0, 3);
        lcd.print("Cooler: ON          ");
        delay(2000); // Show the message for 2 seconds
      }
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      lcd.setCursor(0, 3);
      lcd.print("MQTT Failed!        ");
      delay(5000);
    }
  }
}

void publishSensorData(float temperature, float humidity, float pressure) {
  // Create JSON payload
  StaticJsonDocument<350> doc; // Increased size for additional data
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
  
  char buffer[400];
  serializeJson(doc, buffer);
  
  if (client.publish(MQTT_TOPIC, buffer)) {
    Serial.println("Data published successfully");
    Serial.println(buffer);
  } else {
    Serial.println("Failed to publish data");
  }
}

void controlCooler(float temperature) {
  // Check if cooler should start
  if (!coolerRunning && temperature >= COOLER_START_TEMP) {
    // Start the cooler
    digitalWrite(RELAY_PIN, HIGH);  // Activate relay (HIGH = ON for your relay)
    coolerRunning = true;
    
    // Set start time for first run or restart
    if (!coolerEverStarted) {
      coolerStartTime = millis();
      coolerEverStarted = true;
    }
    
    Serial.println("🧊 Cooler STARTED!");
    Serial.print("Start temperature: ");
    Serial.print(temperature);
    Serial.println("°C");
    
    // Update LCD
    lcd.setCursor(0, 3);
    lcd.print("Cooler: ON          ");
  }
  // Check if cooler should stop
  else if (coolerRunning && temperature <= COOLER_STOP_TEMP) {
    // Stop the cooler
    digitalWrite(RELAY_PIN, LOW); // Deactivate relay (LOW = OFF for your relay)
    coolerRunning = false;
    
    Serial.println("🛑 Cooler STOPPED!");
    Serial.print("Stop temperature: ");
    Serial.print(temperature);
    Serial.println("°C");
    
    // Update LCD
    lcd.setCursor(0, 3);
    lcd.print("Cooler: OFF         ");
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

void setup()
{
  Serial.begin(115200);
  delay(1000);

  // Initialize relay pin
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW); // Initialize relay OFF (LOW = OFF for your relay)
  
  Serial.println("🔌 Relay initialized on GPIO14 (OFF)");

  // Initialize I2C with custom pins (SDA = 5, SCL = 4)
  Wire.begin(5, 4); // GPIO5 = D1, GPIO4 = D2

  // Initialize LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("BME280 Sensor");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");

  Serial.println(F("BMP280 test"));

  // Initialize BME280
  if (bme.begin(0x76))
  {
    Serial.println("BME280 started");
    lcd.setCursor(0, 1);
    lcd.print("BME280 Ready!       ");
  }
  else
  {
    Serial.println("Error initializing BME280");
    lcd.setCursor(0, 1);
    lcd.print("BME280 Error!       ");
  }
  
  delay(2000);
  
  // Setup WiFi
  setupWiFi();
  
  // Setup MQTT
  client.setServer(MQTT_SERVER, MQTT_PORT);
  client.setCallback(onMqttMessage); // Set callback for incoming messages
  
  delay(2000);
  lcd.clear();
  
  // Display cooler thresholds
  Serial.println("🧊 Cooler Control Configuration:");
  Serial.print("Start temperature: ");
  Serial.print(COOLER_START_TEMP);
  Serial.println("°C");
  Serial.print("Stop temperature: ");
  Serial.print(COOLER_STOP_TEMP);
  Serial.println("°C");
}

void loop()
{
  // Ensure MQTT connection
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();
  
  // Read sensor values
  float temperature = bme.readTemperature();
  float humidity = bme.readHumidity();
  float pressure = bme.readPressure() / 100.0F;
  
  // Control cooler based on temperature
  controlCooler(temperature);
  
  // Display on Serial Monitor
  Serial.print(F("Temperature = "));
  Serial.print(temperature);
  Serial.println(" °C");

  Serial.print(F("Humidity = "));
  Serial.print(humidity);
  Serial.println(" %");

  Serial.print(F("Pressure = "));
  Serial.print(pressure);
  Serial.println(" hPa");

  // Always show timing information if cooler has ever started
  if (coolerEverStarted) {
    Serial.print(F("Total elapsed time = "));
    Serial.print(totalElapsedTime / 1000);
    Serial.println(" seconds");
    
    if (coolerRunning) {
      Serial.print(F("Cooler runtime = "));
      Serial.print(coolerRunTime / 1000);
      Serial.println(" seconds (RUNNING)");
    } else {
      Serial.print(F("Last cooler runtime = "));
      Serial.print(coolerRunTime / 1000);
      Serial.println(" seconds (STOPPED)");
    }
  }

  Serial.println();

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
  
  // Line 4: Connection status and uptime
  lcd.setCursor(0, 3);
  if (WiFi.status() == WL_CONNECTED && client.connected()) {
    lcd.print("Online ");
    lcd.print(millis() / 1000);
    lcd.print("s");
  } else {
    lcd.print("Offline");
  }

  // Publish to MQTT every 5 seconds
  unsigned long currentTime = millis();
  if (currentTime - lastMqttPublish >= MQTT_PUBLISH_INTERVAL) {
    if (client.connected()) {
      publishSensorData(temperature, humidity, pressure);
    }
    lastMqttPublish = currentTime;
  }

  delay(2000);
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  // Convert payload to string
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  Serial.print("MQTT message received on topic: ");
  Serial.println(topic);
  Serial.print("Message: ");
  Serial.println(message);
  
  // Check if this is a cooler control command
  if (String(topic) == "sensors/cooler/control") {
    if (message == "ON" || message == "on") {
      manualCoolerControl(true);
    } else if (message == "OFF" || message == "off") {
      manualCoolerControl(false);
    } else if (message == "AUTO" || message == "auto") {
      // Return to automatic temperature control
      manualOverride = false;
      Serial.println("🔄 Cooler returned to automatic temperature control");
      lcd.setCursor(0, 3);
      lcd.print("Auto Mode           ");
      delay(2000);
    }
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
    
    Serial.println("🧊 Cooler turned ON manually!");
    lcd.setCursor(0, 3);
    lcd.print("Manual: ON          ");
    
  } else if (!turnOn && coolerRunning) {
    // Turn cooler OFF manually
    digitalWrite(RELAY_PIN, LOW);
    coolerRunning = false;
    
    Serial.println("🛑 Cooler turned OFF manually!");
    lcd.setCursor(0, 3);
    lcd.print("Manual: OFF         ");
  }
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
