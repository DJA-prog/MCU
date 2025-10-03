#include "secrets.h"

// WiFi credentials
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// MQTT broker settings
const char* MQTT_SERVER = "YOUR_MQTT_SERVER_IP";
const int MQTT_PORT = 1883;
const char* MQTT_USER = "YOUR_MQTT_USERNAME";  // Leave empty if no authentication
const char* MQTT_PASSWORD = "YOUR_MQTT_PASSWORD";  // Leave empty if no authentication
const char* MQTT_CLIENT_ID = "ESP8266_BME280_Sensor";
const char* MQTT_TOPIC = "sensors/cooler";
