/*
  SmartMop ESP32 DevKit - HTTP communication outline

  This is a communication example, NOT a complete motor-control firmware.
  Implement the TODO functions using the exact pins, motor drivers, and
  emergency-stop circuit of your assembled robot before powering actuators.

  Required Arduino libraries:
    - ArduinoJson
    - ESP32 board package

  Set WIFI_SSID, WIFI_PASSWORD, and API_BASE for your local network.
*/
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "NAMA_WIFI";
const char* WIFI_PASSWORD = "PASSWORD_WIFI";
const char* API_BASE = "http://192.168.1.10:5000/api";
const char* DEVICE_CODE = "ESP32_MAIN_01";
const char* DEVICE_API_KEY = ""; // Must match backend .env if enabled.

unsigned long lastHeartbeat = 0;
unsigned long lastPoll = 0;

void addAuth(HTTPClient& http) {
  http.addHeader("Content-Type", "application/json");
  if (strlen(DEVICE_API_KEY) > 0) http.addHeader("X-Device-Key", DEVICE_API_KEY);
}

void motorStopAll() {
  // TODO: Set motor roda kiri/kanan OFF.
  // TODO: Set kedua motor pel OFF.
  // TODO: Set pompa OFF.
  // Hardware emergency-stop harus tetap memutus daya aktuator secara fisik.
}

void executeCommand(const char* type, JsonObject payload) {
  if (strcmp(type, "emergency_stop") == 0 || strcmp(type, "clean_stop") == 0) {
    motorStopAll();
    return;
  }
  if (strcmp(type, "set_mode") == 0) {
    const char* mode = payload["mode"] | "automatic";
    // TODO: Store mode for the control state machine.
    Serial.printf("Mode: %s\n", mode);
    return;
  }
  if (strcmp(type, "move") == 0) {
    const char* direction = payload["direction"] | "berhenti";
    // TODO: Convert direction to motor driver commands and add timeout.
    Serial.printf("Move: %s\n", direction);
    return;
  }
  if (strcmp(type, "clean_start") == 0 || strcmp(type, "approach_spill") == 0) {
    // TODO: Implement safe approach/mopping state machine.
    // approach_spill bbox x/y/width/height are normalized image coordinates,
    // not physical robot coordinates. Calibrate camera geometry first.
    Serial.printf("Cleaning command: %s\n", type);
    return;
  }
  if (strcmp(type, "pump_set") == 0) {
    bool on = payload["on"] | false;
    // TODO: Drive pump MOSFET and enforce a maximum run-time timeout.
    Serial.printf("Pump: %s\n", on ? "ON" : "OFF");
    return;
  }
  if (strcmp(type, "mop_motor_set") == 0) {
    bool on = payload["on"] | false;
    // TODO: Drive both mop motor MOSFETs.
    Serial.printf("Mop motors: %s\n", on ? "ON" : "OFF");
    return;
  }
  if (strcmp(type, "camera_quality") == 0) {
    // This command belongs to the ESP32-CAM, not the controller.
    return;
  }
}

void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.begin(String(API_BASE) + "/device/heartbeat");
  addAuth(http);
  StaticJsonDocument<192> doc;
  doc["device_code"] = DEVICE_CODE;
  doc["wifi_rssi"] = WiFi.RSSI();
  doc["firmware_version"] = "0.1.0";
  String body;
  serializeJson(doc, body);
  http.POST(body);
  http.end();
}

void pollCommands() {
  if (WiFi.status() != WL_CONNECTED) {
    motorStopAll();
    return;
  }
  HTTPClient http;
  String url = String(API_BASE) + "/device/commands?device_code=" + DEVICE_CODE + "&limit=5";
  http.begin(url);
  if (strlen(DEVICE_API_KEY) > 0) http.addHeader("X-Device-Key", DEVICE_API_KEY);
  int code = http.GET();
  if (code == 200) {
    DynamicJsonDocument doc(8192);
    DeserializationError err = deserializeJson(doc, http.getString());
    if (!err) {
      for (JsonObject command : doc["commands"].as<JsonArray>()) {
        int id = command["command_id"] | 0;
        const char* type = command["command_type"] | "";
        JsonObject payload = command["payload"].as<JsonObject>();
        executeCommand(type, payload);

        HTTPClient ack;
        ack.begin(String(API_BASE) + "/device/commands/" + id + "/ack");
        addAuth(ack);
        StaticJsonDocument<192> response;
        response["status"] = "acknowledged";
        response["response"]["received"] = true;
        String body;
        serializeJson(response, body);
        ack.POST(body);
        ack.end();
      }
    }
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  motorStopAll();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(300);
  Serial.println("SmartMop controller connected.");
  sendHeartbeat();
}

void loop() {
  unsigned long now = millis();
  if (WiFi.status() != WL_CONNECTED) {
    motorStopAll();
    WiFi.reconnect();
    delay(100);
    return;
  }
  if (now - lastHeartbeat >= 10000) {
    lastHeartbeat = now;
    sendHeartbeat();
  }
  if (now - lastPoll >= 700) {
    lastPoll = now;
    pollCommands();
  }
  delay(10);
}
