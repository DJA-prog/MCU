#include "secrets.h"

// WiFi credentials
const char* WIFI_SSID = "Raptor95";
const char* WIFI_PASSWORD = "12345@admin!";

// MQTT broker settings
const char* MQTT_SERVER = "192.168.1.1";
const int MQTT_PORT = 1883;
const char* MQTT_USER = "hass";  // Leave empty if no authentication
const char* MQTT_PASSWORD = "12345@admin";  // Leave empty if no authentication
const char* MQTT_CLIENT_ID = "ESP8266_BME280_Sensor";
const char* MQTT_TOPIC = "sensors/cooler";
