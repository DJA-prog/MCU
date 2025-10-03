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

void publishSensorData(float temperature, float pressure, float altitude) {
  // Create JSON payload
  StaticJsonDocument<200> doc;
  doc["temperature"] = round(temperature * 10) / 10.0; // Round to 1 decimal
  doc["pressure"] = round(pressure * 10) / 10.0;
  doc["altitude"] = round(altitude);
  doc["timestamp"] = millis();
  doc["device"] = "ESP8266_BME280";
  
  char buffer[256];
  serializeJson(doc, buffer);
  
  if (client.publish(MQTT_TOPIC, buffer)) {
    Serial.println("Data published successfully");
    Serial.println(buffer);
  } else {
    Serial.println("Failed to publish data");
  }
}

void setup()
{
  Serial.begin(115200);
  delay(1000);

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
  
  delay(2000);
  lcd.clear();
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
  float pressure = bme.readPressure() / 100.0F;
  float altitude = bme.readAltitude(1013.25);
  
  // Display on Serial Monitor
  Serial.print(F("Temperature = "));
  Serial.print(temperature);
  Serial.println(" °C");

  Serial.print(F("Pressure = "));
  Serial.print(pressure);
  Serial.println(" hPa");

  Serial.print(F("Approx altitude = "));
  Serial.print(altitude);
  Serial.println(" m");

  Serial.println();

  // Display on LCD
  lcd.clear();
  
  // Line 1: Temperature
  lcd.setCursor(0, 0);
  lcd.print("Temp: ");
  lcd.print(temperature, 1);
  lcd.print(" C");
  
  // Line 2: Pressure
  lcd.setCursor(0, 1);
  lcd.print("Press:");
  lcd.print(pressure, 1);
  lcd.print("hPa");
  
  // Line 3: Altitude
  lcd.setCursor(0, 2);
  lcd.print("Alt: ");
  lcd.print(altitude, 0);
  lcd.print(" m");
  
  // Line 4: Connection status
  lcd.setCursor(0, 3);
  if (WiFi.status() == WL_CONNECTED && client.connected()) {
    lcd.print("Online - ");
    lcd.print(millis() / 1000);
    lcd.print("s");
  } else {
    lcd.print("Offline");
  }

  // Publish to MQTT every 5 seconds
  unsigned long currentTime = millis();
  if (currentTime - lastMqttPublish >= MQTT_PUBLISH_INTERVAL) {
    if (client.connected()) {
      publishSensorData(temperature, pressure, altitude);
    }
    lastMqttPublish = currentTime;
  }

  delay(2000);
}
