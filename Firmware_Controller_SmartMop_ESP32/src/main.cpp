
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#include "config.h"

// Konstanta internal main.cpp. Tidak mengubah config.h milik pengguna.
static constexpr uint32_t HTTP_TIMEOUT_MS = 5000;
static constexpr uint32_t ACK_RETRY_INTERVAL_MS = 3000;
static constexpr uint32_t SENSOR_READ_INTERVAL_MS = 1000;
static constexpr uint8_t BATTERY_SAMPLE_COUNT = 10;
static constexpr float BATTERY_LOW_VOLTAGE = 10.5f;
static constexpr uint8_t MOTOR_SPEED_PWM = 180;
static constexpr uint32_t MOTOR_PWM_FREQUENCY = 20000;
static constexpr uint8_t MOTOR_PWM_RESOLUTION = 8;
// GPIO35 ESP32 tidak mempunyai internal pull-up. Gunakan pull-up eksternal 10k ke 3.3V.
static constexpr uint8_t SOAP_FLOAT_ACTIVE_LOW = 1;
// Ubah menjadi 1 jika arah putaran motor sisi terkait terbalik.
static constexpr uint8_t MOTOR_KIRI_REVERSE_DIR = 0;
static constexpr uint8_t MOTOR_KANAN_REVERSE_DIR = 0;

// ============================================================
// 1. OBJEK DAN VARIABEL GLOBAL
// ============================================================

WiFiClient wifiClient;

enum RobotState {
    STATE_IDLE,
    STATE_MOVING,
    STATE_CLEANING,
    STATE_EMERGENCY_STOP,
    STATE_OFFLINE
};

RobotState robotState = STATE_IDLE;

bool cleaningActive = false;
bool emergencyStopLatched = false;
bool soapAvailable = false;
bool batteryLow = false;
bool currentModeAutomatic = true;

bool pumpActive = false;

float batteryVoltage = 0.0f;
float batteryPercent = 0.0f;

int wifiRssi = 0;

int64_t activeSessionId = -1;

// Timer gerakan
uint32_t movementStartedAt = 0;
uint32_t movementDurationMs = 0;

// Timer cleaning
uint32_t cleaningStartedAt = 0;
uint32_t cleaningDurationMs = 0;

// Timer pompa
uint32_t pumpStartedAt = 0;
uint32_t pumpDurationMs = DEFAULT_PUMP_DURATION;

// Timer komunikasi
uint32_t lastWifiAttemptAt = 0;
uint32_t lastServerSuccessAt = 0;
uint32_t lastPollAt = 0;
uint32_t lastHeartbeatAt = 0;
uint32_t lastTelemetryAt = 0;
uint32_t lastSensorReadAt = 0;
uint32_t lastAckRetryAt = 0;

// Penyimpanan ACK yang gagal dikirim
String pendingAckUrl;
String pendingAckBody;
bool ackPending = false;

// ============================================================
// 2. DEKLARASI FUNGSI
// ============================================================

// Inisialisasi
void initializePins();
void connectWiFi();
void maintainWiFi();

// Safety
void updateSafety();
void updateActuatorTimers();
void stopAllActuators();

// Motor roda
void moveForward(uint32_t durationMs);
void moveBackward(uint32_t durationMs);
void stopMovement();

// Motor pel
void startMopMotors();
void stopMopMotors();

// Pompa
void activatePump(uint32_t durationMs);
void deactivatePump();

// Sensor
void readSensors();
float readBatteryVoltage();
float calculateBatteryPercent(float voltage);
bool readSoapAvailability();

// Komunikasi backend
void sendHeartbeat();
void sendTelemetry();
void pollCommands();

bool httpGetJson(
    const String& url,
    JsonDocument& response
);

bool httpPostJson(
    const String& url,
    const String& body,
    int& httpCode
);

bool httpPutJson(
    const String& url,
    const String& body,
    int& httpCode
);

// Command
bool executeCommand(JsonObjectConst command);

void sendCommandAck(
    int64_t commandId,
    bool success,
    const char* message
);

void retryPendingAck();

// Cleaning
void updateCleaningSession(
    const char* status,
    const char* notes
);

// Utilitas
uint32_t clampDuration(
    uint32_t requested,
    uint32_t maximum
);

String robotStateName();

// ============================================================
// 3. SETUP
// ============================================================

void setup() {

    Serial.begin(115200);

    delay(100);

    Serial.println();
    Serial.println("====================================");
    Serial.println(" SMARTMOP ESP32 MAIN CONTROLLER");
    Serial.println(" Firmware Version 1.0.0");
    Serial.println("====================================");

    // Inisialisasi seluruh pin
    initializePins();

    // Semua aktuator harus OFF ketika boot
    stopAllActuators();

    // Konfigurasi ADC ESP32
    analogReadResolution(12);

    analogSetPinAttenuation(
        SENSOR_BATERAI_PIN,
        ADC_11db
    );

    // Konfigurasi Wi-Fi
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);

    connectWiFi();

    Serial.println("Controller berhasil diinisialisasi.");
}

// ============================================================
// 4. LOOP UTAMA
// ============================================================

void loop() {

    uint32_t now = millis();

    // Mempertahankan koneksi Wi-Fi
    maintainWiFi();

    // Membaca sensor
    readSensors();

    // Memeriksa timer aktuator
    updateActuatorTimers();

    // Pemeriksaan keselamatan
    updateSafety();

    if (WiFi.status() == WL_CONNECTED) {

        // Heartbeat setiap 10 detik
        if (now - lastHeartbeatAt >= HEARTBEAT_INTERVAL) {

            lastHeartbeatAt = now;

            sendHeartbeat();
        }

        // Telemetri setiap 5 detik
        if (now - lastTelemetryAt >= TELEMETRY_INTERVAL) {

            lastTelemetryAt = now;

            sendTelemetry();
        }

        // Polling command
        if (!emergencyStopLatched &&
            now - lastPollAt >= COMMAND_POLL_INTERVAL) {

            lastPollAt = now;

            pollCommands();
        }

        // Mengirim ulang ACK jika sebelumnya gagal
        retryPendingAck();
    }

    // Tidak menggunakan delay panjang
    delay(2);
}

// ============================================================
// 5. INISIALISASI PIN
// ============================================================

void initializePins() {

    // Driver BTS7960 / IBT-2 sisi kiri dan kanan
    pinMode(MOTOR_KIRI_RPWM, OUTPUT);
    pinMode(MOTOR_KIRI_LPWM, OUTPUT);
    pinMode(MOTOR_KIRI_REN, OUTPUT);
    pinMode(MOTOR_KIRI_LEN, OUTPUT);

    pinMode(MOTOR_KANAN_RPWM, OUTPUT);
    pinMode(MOTOR_KANAN_LPWM, OUTPUT);
    pinMode(MOTOR_KANAN_REN, OUTPUT);
    pinMode(MOTOR_KANAN_LEN, OUTPUT);

    // Arduino-ESP32 pada versi ini mengatur resolusi dan frekuensi
    // secara global, bukan per-pin.
    analogWriteResolution(MOTOR_PWM_RESOLUTION);
    analogWriteFrequency(MOTOR_PWM_FREQUENCY);

    pinMode(MOTOR_PEL_IN1, OUTPUT);
    pinMode(MOTOR_PEL_IN2, OUTPUT);
    pinMode(POMPA_PIN, OUTPUT);

    pinMode(SENSOR_BATERAI_PIN, INPUT);
    pinMode(SENSOR_SABUN_PIN, INPUT);

    stopAllActuators();
}

// ============================================================
// 6. KONEKSI WIFI
// ============================================================

void connectWiFi() {

    Serial.print("Menghubungkan Wi-Fi: ");
    Serial.println(WIFI_SSID);

    WiFi.begin(
        WIFI_SSID,
        WIFI_PASSWORD
    );

    lastWifiAttemptAt = millis();
}

void maintainWiFi() {

    if (WiFi.status() == WL_CONNECTED) {
        return;
    }

    // Jika koneksi hilang, semua aktuator OFF
    stopAllActuators();

    robotState = STATE_OFFLINE;

    uint32_t now = millis();

    if (now - lastWifiAttemptAt >= WIFI_RECONNECT_INTERVAL) {

        lastWifiAttemptAt = now;

        Serial.println("Wi-Fi terputus. Reconnecting...");

        WiFi.disconnect();

        WiFi.begin(
            WIFI_SSID,
            WIFI_PASSWORD
        );
    }
}

// ============================================================
// 7. SISTEM KESELAMATAN
// ============================================================

void updateSafety() {

    // Emergency stop memiliki prioritas tertinggi
    if (emergencyStopLatched) {

        stopAllActuators();

        robotState = STATE_EMERGENCY_STOP;

        return;
    }

    // Wi-Fi terputus
    if (WiFi.status() != WL_CONNECTED) {

        stopAllActuators();

        robotState = STATE_OFFLINE;

        return;
    }

    // Backend tidak memberikan respons terlalu lama
    if (lastServerSuccessAt == 0 ||
        millis() - lastServerSuccessAt >
        SERVER_TIMEOUT) {

        stopAllActuators();

        robotState = STATE_OFFLINE;
    }
}

// ============================================================
// 8. TIMER AKTUATOR
// ============================================================

void updateActuatorTimers() {

    uint32_t now = millis();

    // ----------------------------------------
    // Timer motor roda
    // ----------------------------------------

    if (robotState == STATE_MOVING &&
        movementDurationMs > 0 &&
        now - movementStartedAt >= movementDurationMs) {

        stopMovement();

        Serial.println(
            "Durasi gerakan selesai. Motor roda OFF."
        );
    }

    // ----------------------------------------
    // Timer pompa
    // ----------------------------------------

    if (pumpActive &&
        now - pumpStartedAt >= pumpDurationMs) {

        deactivatePump();

        Serial.println(
            "Timeout pompa. Pompa otomatis OFF."
        );
    }

    // ----------------------------------------
    // Timer cleaning
    // ----------------------------------------

    if (cleaningActive &&
        cleaningDurationMs > 0 &&
        now - cleaningStartedAt >= cleaningDurationMs) {

        stopMopMotors();

        deactivatePump();

        stopMovement();

        cleaningActive = false;

        cleaningDurationMs = 0;

        robotState = STATE_IDLE;

        Serial.println(
            "Durasi cleaning selesai."
        );

        updateCleaningSession(
            "completed",
            "Cleaning selesai berdasarkan timer firmware."
        );
    }
}

// ============================================================
// 9. KONTROL MOTOR RODA
// ============================================================

void setBts7960Motor(uint8_t rpwmPin, uint8_t lpwmPin,
                       uint8_t renPin, uint8_t lenPin,
                       bool forward, uint8_t speed) {
    digitalWrite(renPin, HIGH);
    digitalWrite(lenPin, HIGH);
    if (forward) {
        analogWrite(rpwmPin, speed);
        analogWrite(lpwmPin, 0);
    } else {
        analogWrite(rpwmPin, 0);
        analogWrite(lpwmPin, speed);
    }
}

void stopBts7960Motor(uint8_t rpwmPin, uint8_t lpwmPin,
                       uint8_t renPin, uint8_t lenPin) {
    analogWrite(rpwmPin, 0);
    analogWrite(lpwmPin, 0);
    digitalWrite(renPin, LOW);
    digitalWrite(lenPin, LOW);
}

void moveForward(uint32_t durationMs) {
    if (emergencyStopLatched || WiFi.status() != WL_CONNECTED) return;

    setBts7960Motor(MOTOR_KIRI_RPWM, MOTOR_KIRI_LPWM, MOTOR_KIRI_REN, MOTOR_KIRI_LEN,
                    MOTOR_KIRI_REVERSE_DIR ? false : true, MOTOR_SPEED_PWM);
    setBts7960Motor(MOTOR_KANAN_RPWM, MOTOR_KANAN_LPWM, MOTOR_KANAN_REN, MOTOR_KANAN_LEN,
                    MOTOR_KANAN_REVERSE_DIR ? false : true, MOTOR_SPEED_PWM);

    movementStartedAt = millis();
    movementDurationMs = clampDuration(durationMs, MAX_MOVEMENT_DURATION);
    robotState = STATE_MOVING;
    Serial.printf("ROBOT FORWARD: %lu ms\n", (unsigned long)movementDurationMs);
}

void moveBackward(uint32_t durationMs) {
    if (emergencyStopLatched || WiFi.status() != WL_CONNECTED) return;

    setBts7960Motor(MOTOR_KIRI_RPWM, MOTOR_KIRI_LPWM, MOTOR_KIRI_REN, MOTOR_KIRI_LEN,
                    MOTOR_KIRI_REVERSE_DIR ? true : false, MOTOR_SPEED_PWM);
    setBts7960Motor(MOTOR_KANAN_RPWM, MOTOR_KANAN_LPWM, MOTOR_KANAN_REN, MOTOR_KANAN_LEN,
                    MOTOR_KANAN_REVERSE_DIR ? true : false, MOTOR_SPEED_PWM);

    movementStartedAt = millis();
    movementDurationMs = clampDuration(durationMs, MAX_MOVEMENT_DURATION);
    robotState = STATE_MOVING;
    Serial.printf("ROBOT BACKWARD: %lu ms\n", (unsigned long)movementDurationMs);
}

void stopMovement() {
    stopBts7960Motor(MOTOR_KIRI_RPWM, MOTOR_KIRI_LPWM, MOTOR_KIRI_REN, MOTOR_KIRI_LEN);
    stopBts7960Motor(MOTOR_KANAN_RPWM, MOTOR_KANAN_LPWM, MOTOR_KANAN_REN, MOTOR_KANAN_LEN);
    movementDurationMs = 0;

    if (!cleaningActive && !emergencyStopLatched) {
        robotState = WiFi.status() == WL_CONNECTED ? STATE_IDLE : STATE_OFFLINE;
    }
}

// ============================================================
// 10. KONTROL MOTOR PEL
// ============================================================

void startMopMotors() {

    if (emergencyStopLatched ||
        !cleaningActive) {

        return;
    }

    digitalWrite(MOTOR_PEL_IN1, HIGH);

    digitalWrite(MOTOR_PEL_IN2, HIGH);

    Serial.println(
        "Motor pel kiri dan kanan ON."
    );
}

void stopMopMotors() {

    digitalWrite(MOTOR_PEL_IN1, LOW);

    digitalWrite(MOTOR_PEL_IN2, LOW);

    Serial.println(
        "Motor pel OFF."
    );
}

// ============================================================
// 11. KONTROL POMPA SABUN
// ============================================================

void activatePump(uint32_t durationMs) {

    // Pompa hanya boleh aktif ketika cleaning berjalan
    if (emergencyStopLatched ||
        !cleaningActive ||
        !soapAvailable) {

        Serial.println(
            "Pompa ditolak: cleaning tidak aktif atau sabun rendah."
        );

        return;
    }

    uint32_t safeDuration = clampDuration(
        durationMs,
        DEFAULT_PUMP_DURATION
    );

    digitalWrite(POMPA_PIN, HIGH);

    pumpActive = true;

    pumpStartedAt = millis();

    pumpDurationMs = safeDuration;

    Serial.printf(
        "Pompa ON: %lu ms\n",
        (unsigned long)safeDuration
    );
}

void deactivatePump() {

    digitalWrite(POMPA_PIN, LOW);

    pumpActive = false;
}

// ============================================================
// 12. MEMATIKAN SEMUA AKTUATOR
// ============================================================

void stopAllActuators() {

    stopMovement();

    stopMopMotors();

    deactivatePump();

    cleaningActive = false;

    cleaningDurationMs = 0;
}

// ============================================================
// 13. PEMBACAAN SENSOR
// ============================================================

void readSensors() {

    if (millis() - lastSensorReadAt <
        SENSOR_READ_INTERVAL_MS) {

        return;
    }

    lastSensorReadAt = millis();

    // Baterai
    batteryVoltage = readBatteryVoltage();

    batteryPercent = calculateBatteryPercent(
        batteryVoltage
    );

    batteryLow =
        batteryVoltage > 0 &&
        batteryVoltage <= BATTERY_LOW_VOLTAGE;

    // Sabun
    soapAvailable = readSoapAvailability();

    // Wi-Fi
    if (WiFi.status() == WL_CONNECTED) {
        wifiRssi = WiFi.RSSI();
    }

    Serial.println("--------------------------------");

    Serial.printf(
        "Battery Voltage : %.2f V\n",
        batteryVoltage
    );

    Serial.printf(
        "Battery Percent : %.1f %%\n",
        batteryPercent
    );

    Serial.printf(
        "Battery Low     : %s\n",
        batteryLow ? "YES" : "NO"
    );

    Serial.printf(
        "Soap Status     : %s\n",
        soapAvailable ? "AVAILABLE" : "LOW/EMPTY"
    );

    Serial.printf(
        "WiFi RSSI       : %d dBm\n",
        wifiRssi
    );

    Serial.println("--------------------------------");
}

// ============================================================
// 14. MEMBACA TEGANGAN BATERAI
// ============================================================

float readBatteryVoltage() {

    uint32_t totalMilliVolt = 0;

    for (uint8_t i = 0;
         i < BATTERY_SAMPLE_COUNT;
         i++) {

        totalMilliVolt += analogReadMilliVolts(
            SENSOR_BATERAI_PIN
        );
    }

    float adcMilliVolt =
        (float)totalMilliVolt / BATTERY_SAMPLE_COUNT;

    float adcVoltage = adcMilliVolt / 1000.0f;

    float dividerRatio =
        (BATTERY_R1 +
         BATTERY_R2) /
        BATTERY_R2;

    float batteryVoltage =
        adcVoltage *
        dividerRatio *
        BATTERY_CALIBRATION;

    return batteryVoltage;
}

// ============================================================
// 15. ESTIMASI PERSENTASE BATERAI 3S
// ============================================================

float calculateBatteryPercent(float voltage) {

    const float voltageTable[] = {
        9.00, 9.30, 9.60, 9.90,
        10.20, 10.50, 10.80, 11.10,
        11.40, 11.70, 12.00, 12.30,
        12.60
    };

    const float percentTable[] = {
        0, 3, 7, 12,
        20, 30, 42, 55,
        68, 80, 90, 96,
        100
    };

    const size_t tableSize =
        sizeof(voltageTable) /
        sizeof(voltageTable[0]);

    if (voltage <= voltageTable[0]) {
        return 0;
    }

    if (voltage >= voltageTable[tableSize - 1]) {
        return 100;
    }

    for (size_t i = 0;
         i < tableSize - 1;
         i++) {

        if (voltage >= voltageTable[i] &&
            voltage <= voltageTable[i + 1]) {

            float ratio =
                (voltage - voltageTable[i]) /
                (voltageTable[i + 1] - voltageTable[i]);

            return percentTable[i] +
                ratio *
                (percentTable[i + 1] - percentTable[i]);
        }
    }

    return 0;
}

// ============================================================
// 16. MEMBACA SENSOR LEVEL SABUN
// ============================================================

bool readSoapAvailability() {

    int pinValue = digitalRead(SENSOR_SABUN_PIN);

    if (SOAP_FLOAT_ACTIVE_LOW) {

        return pinValue == LOW;
    }

    return pinValue == HIGH;
}

// ============================================================
// 17. HTTP GET
// ============================================================

bool httpGetJson(
    const String& url,
    JsonDocument& response
) {

    if (WiFi.status() != WL_CONNECTED) {
        return false;
    }

    HTTPClient http;

    http.setTimeout(HTTP_TIMEOUT_MS);

    if (!http.begin(wifiClient, url)) {
        return false;
    }

    // Autentikasi perangkat wajib
    http.addHeader(
        "X-Device-Key",
        API_DEVICE_KEY
    );

    http.addHeader(
        "Accept",
        "application/json"
    );

    int httpCode = http.GET();

    bool success = false;

    if (httpCode >= 200 && httpCode < 300) {

        String body = http.getString();

        DeserializationError error =
            deserializeJson(response, body);

        if (!error &&
            response["success"] == true) {

            success = true;

            lastServerSuccessAt = millis();
        }
    }

    Serial.printf(
        "HTTP GET: %d\n",
        httpCode
    );

    http.end();

    return success;
}

// ============================================================
// 18. HTTP POST
// ============================================================

bool httpPostJson(
    const String& url,
    const String& body,
    int& httpCode
) {

    if (WiFi.status() != WL_CONNECTED) {

        httpCode = -1;

        return false;
    }

    HTTPClient http;

    http.setTimeout(HTTP_TIMEOUT_MS);

    if (!http.begin(wifiClient, url)) {

        httpCode = -1;

        return false;
    }

    http.addHeader(
        "Content-Type",
        "application/json"
    );

    http.addHeader(
        "X-Device-Key",
        API_DEVICE_KEY
    );

    httpCode = http.POST(body);

    bool success = false;

    if (httpCode >= 200 && httpCode < 300) {

        String responseBody = http.getString();

        JsonDocument response;

        DeserializationError error =
            deserializeJson(response, responseBody);

        success =
            !error &&
            response["success"] == true;

        if (success) {
            lastServerSuccessAt = millis();
        }
    }

    Serial.printf(
        "HTTP POST: %d\n",
        httpCode
    );

    http.end();

    return success;
}

// ============================================================
// 19. HTTP PUT
// ============================================================

bool httpPutJson(
    const String& url,
    const String& body,
    int& httpCode
) {

    if (WiFi.status() != WL_CONNECTED) {

        httpCode = -1;

        return false;
    }

    HTTPClient http;

    http.setTimeout(HTTP_TIMEOUT_MS);

    if (!http.begin(wifiClient, url)) {

        httpCode = -1;

        return false;
    }

    http.addHeader(
        "Content-Type",
        "application/json"
    );

    http.addHeader(
        "X-Device-Key",
        API_DEVICE_KEY
    );

    httpCode = http.PUT(body);

    bool success = false;

    if (httpCode >= 200 && httpCode < 300) {

        String responseBody = http.getString();

        JsonDocument response;

        DeserializationError error =
            deserializeJson(response, responseBody);

        success =
            !error &&
            response["success"] == true;

        if (success) {
            lastServerSuccessAt = millis();
        }
    }

    Serial.printf(
        "HTTP PUT: %d\n",
        httpCode
    );

    http.end();

    return success;
}

// ============================================================
// 20. HEARTBEAT KE BACKEND
// ============================================================

void sendHeartbeat() {

    JsonDocument doc;

    doc["device_code"] = DEVICE_CODE;

    doc["wifi_rssi"] = WiFi.RSSI();

    doc["firmware_version"] = FIRMWARE_VERSION;

    doc["ip_address"] = WiFi.localIP().toString();

    String body;

    serializeJson(doc, body);

    int httpCode = 0;

    bool success = httpPostJson(
        String(API_BASE_URL) + "/device/heartbeat",
        body,
        httpCode
    );

    if (success) {

        Serial.println(
            "Heartbeat berhasil dikirim."
        );

    } else {

        Serial.println(
            "Heartbeat gagal dikirim."
        );
    }
}

// ============================================================
// 21. TELEMETRI KE BACKEND
// ============================================================

void sendTelemetry() {

    JsonDocument doc;

    doc["device_code"] = DEVICE_CODE;

    // Data baterai
    doc["battery_voltage"] = batteryVoltage;
    doc["battery_percent"] = batteryPercent;

    // Data sabun
    doc["soap_available"] = soapAvailable;

    // WiFi
    doc["wifi_rssi"] = WiFi.RSSI();

    String body;

    serializeJson(doc, body);

    int httpCode = 0;

    bool success = httpPostJson(
        String(API_BASE_URL) + "/device/telemetry",
        body,
        httpCode
    );

    if (success) {
        Serial.println("Telemetry berhasil dikirim.");
    } else {
        Serial.println("Telemetry gagal dikirim.");
    }
}

// ============================================================
// 22. POLLING COMMAND DARI FLASK
// ============================================================

void pollCommands() {

    if (emergencyStopLatched) {
        return;
    }

    String url =
        String(API_BASE_URL) +
        "/commands/pending?device_code=" +
        DEVICE_CODE;

    JsonDocument response;

    if (!httpGetJson(url, response)) {

        Serial.println(
            "Gagal mengambil command dari backend."
        );

        return;
    }

    // Source route Flask mengembalikan array pada field data
    JsonArray commands =
        response["data"].as<JsonArray>();

    if (commands.isNull() ||
        commands.size() == 0) {

        return;
    }

    for (JsonObject command : commands) {

        int64_t commandId =
            command["command_id"] | -1;

        if (commandId < 0) {
            continue;
        }

        // ArduinoJson v7: command sudah bertipe JsonObject.
        // Konversikan langsung ke JsonObjectConst untuk fungsi eksekusi.
        JsonObjectConst commandConst = command;
        bool success = executeCommand(commandConst);

        const char* message = success
            ? "Command berhasil diproses controller."
            : "Command ditolak atau gagal diproses.";

        sendCommandAck(
            commandId,
            success,
            message
        );

        if (emergencyStopLatched) {
            break;
        }
    }
}

// ============================================================
// 23. EKSEKUSI COMMAND
// ============================================================

bool executeCommand(JsonObjectConst command) {

    const char* type =
        command["command_type"] | "";

    JsonObjectConst payload =
        command["command_payload"].as<JsonObjectConst>();

    int64_t sessionId =
        command["session_id"] | -1;

    Serial.println();

    Serial.printf(
        "COMMAND: %s\n",
        type
    );

    // ----------------------------------------
    // EMERGENCY STOP
    // ----------------------------------------

    if (strcmp(type, "emergency_stop") == 0) {

        stopAllActuators();

        emergencyStopLatched = true;

        robotState = STATE_EMERGENCY_STOP;

        Serial.println(
            "EMERGENCY STOP AKTIF!"
        );

        return true;
    }

    if (emergencyStopLatched) {
        return false;
    }

    // ----------------------------------------
    // SET MODE
    // ----------------------------------------

    if (strcmp(type, "set_mode") == 0) {

        const char* mode =
            payload["mode"] | "automatic";

        if (strcmp(mode, "automatic") == 0) {

            currentModeAutomatic = true;

            return true;
        }

        if (strcmp(mode, "manual") == 0) {

            currentModeAutomatic = false;

            return true;
        }

        return false;
    }

    // ----------------------------------------
    // MOVE
    // ----------------------------------------

    if (strcmp(type, "move") == 0) {

        const char* direction =
            payload["direction"] | "";

        uint32_t duration =
            payload["duration_ms"] |
            DEFAULT_MOVEMENT_DURATION;

        duration = clampDuration(
            duration,
            MAX_MOVEMENT_DURATION
        );

        if (strcmp(direction, "maju") == 0 ||
            strcmp(direction, "forward") == 0) {

            moveForward(duration);

            return true;
        }

        if (strcmp(direction, "mundur") == 0 ||
            strcmp(direction, "backward") == 0) {

            moveBackward(duration);

            return true;
        }

        if (strcmp(direction, "berhenti") == 0 ||
            strcmp(direction, "stop") == 0) {

            stopMovement();

            return true;
        }

        // Kiri dan kanan belum didukung
        return false;
    }

    // ----------------------------------------
    // APPROACH SPILL
    // ----------------------------------------

    if (strcmp(type, "approach_spill") == 0) {

        if (sessionId > 0) {
            activeSessionId = sessionId;
        }

        uint32_t duration =
            payload["duration_ms"] |
            DEFAULT_MOVEMENT_DURATION;

        duration = clampDuration(
            duration,
            MAX_MOVEMENT_DURATION
        );

        // Backend saat ini belum memberikan arah
        // eksplisit. Perilaku default adalah maju.
        moveForward(duration);

        return true;
    }

    // ----------------------------------------
    // CLEAN START
    // ----------------------------------------

    if (strcmp(type, "clean_start") == 0) {

        if (sessionId > 0) {
            activeSessionId = sessionId;
        }

        uint32_t seconds =
            payload["duration_seconds"] | 10;

        cleaningDurationMs = clampDuration(
            seconds * 1000UL,
            DEFAULT_CLEANING_DURATION
        );

        stopMovement();

        cleaningActive = true;

        cleaningStartedAt = millis();

        robotState = STATE_CLEANING;

        startMopMotors();

        // Pompa hanya satu pulsa singkat
        if (soapAvailable) {

            activatePump(
                DEFAULT_PUMP_DURATION
            );

        } else {

            Serial.println(
                "Sabun rendah. Pompa tidak diaktifkan."
            );
        }

        updateCleaningSession(
            "mopping",
            "Motor pel mulai bekerja."
        );

        return true;
    }

    // ----------------------------------------
    // CLEAN STOP
    // ----------------------------------------

    if (strcmp(type, "clean_stop") == 0) {

        stopMopMotors();

        deactivatePump();

        stopMovement();

        cleaningActive = false;

        cleaningDurationMs = 0;

        robotState = STATE_IDLE;

        updateCleaningSession(
            "cancelled",
            "Cleaning dihentikan oleh backend."
        );

        return true;
    }

    // ----------------------------------------
    // MOTOR PEL ON/OFF
    // ----------------------------------------

    if (strcmp(type, "mop_motor_set") == 0) {

        bool on = payload["on"] | false;

        if (on) {

            if (!cleaningActive) {
                return false;
            }

            startMopMotors();

        } else {

            stopMopMotors();
        }

        return true;
    }

    // ----------------------------------------
    // POMPA ON/OFF
    // ----------------------------------------

    if (strcmp(type, "pump_set") == 0) {

        bool on = payload["on"] | false;

        if (on) {

            if (!cleaningActive ||
                !soapAvailable) {

                return false;
            }

            activatePump(
                DEFAULT_PUMP_DURATION
            );

        } else {

            deactivatePump();
        }

        return true;
    }

    // ----------------------------------------
    // CAMERA QUALITY
    // ----------------------------------------

    if (strcmp(type, "camera_quality") == 0) {

        Serial.println(
            "camera_quality bukan command ESP32_MAIN_01."
        );

        return false;
    }

    // ----------------------------------------
    // COMMAND TIDAK DIKENAL
    // ----------------------------------------

    Serial.printf(
        "Command tidak dikenal: %s\n",
        type
    );

    return false;
}

// ============================================================
// 24. ACK COMMAND KE FLASK
// ============================================================

void sendCommandAck(
    int64_t commandId,
    bool success,
    const char* message
) {

    JsonDocument doc;

    // Sesuai source Backend/routes/command_routes.py
    doc["command_status"] =
        success ? "acknowledged" : "failed";

    doc["response_payload"]["ok"] = success;

    doc["response_payload"]["message"] = message;

    doc["response_payload"]["device_code"] =
        DEVICE_CODE;

    doc["response_payload"]["robot_state"] =
        robotStateName();

    String body;

    serializeJson(doc, body);

    char commandIdBuffer[24];

    snprintf(
        commandIdBuffer,
        sizeof(commandIdBuffer),
        "%lld",
        static_cast<long long>(commandId)
    );

    String url =
        String(API_BASE_URL) +
        "/commands/" +
        commandIdBuffer +
        "/ack";

    int httpCode = 0;

    if (httpPostJson(url, body, httpCode)) {

        Serial.printf(
            "ACK command %lld berhasil.\n",
            static_cast<long long>(commandId)
        );

        return;
    }

    // Jangan mengeksekusi command ulang.
    // Hanya kirim ulang ACK-nya.
    pendingAckUrl = url;

    pendingAckBody = body;

    ackPending = true;

    lastAckRetryAt = millis();

    Serial.println(
        "ACK gagal. Menunggu retry."
    );
}

// ============================================================
// 25. RETRY ACK
// ============================================================

void retryPendingAck() {

    if (!ackPending) {
        return;
    }

    if (millis() - lastAckRetryAt <
        ACK_RETRY_INTERVAL_MS) {

        return;
    }

    lastAckRetryAt = millis();

    int httpCode = 0;

    if (httpPostJson(
        pendingAckUrl,
        pendingAckBody,
        httpCode
    )) {

        ackPending = false;

        pendingAckUrl = "";

        pendingAckBody = "";

        Serial.println(
            "ACK tertunda berhasil dikirim."
        );
    }
}

// ============================================================
// 26. UPDATE STATUS CLEANING
// ============================================================

void updateCleaningSession(
    const char* status,
    const char* notes
) {

    if (activeSessionId <= 0) {
        return;
    }

    JsonDocument doc;

    // Nama field sesuai route Flask
    doc["session_status"] = status;

    doc["notes"] = notes;

    if (strcmp(status, "completed") == 0 &&
        cleaningStartedAt > 0) {

        doc["mop_duration_seconds"] =
            (millis() - cleaningStartedAt) / 1000;
    }

    String body;

    serializeJson(doc, body);

    char sessionIdBuffer[24];

    snprintf(
        sessionIdBuffer,
        sizeof(sessionIdBuffer),
        "%lld",
        static_cast<long long>(activeSessionId)
    );

    String url =
        String(API_BASE_URL) +
        "/cleaning/" +
        sessionIdBuffer +
        "/status";

    int httpCode = 0;

    if (!httpPutJson(url, body, httpCode)) {

        Serial.println(
            "Update status cleaning gagal."
        );
    }

    if (strcmp(status, "completed") == 0 ||
        strcmp(status, "failed") == 0 ||
        strcmp(status, "cancelled") == 0) {

        activeSessionId = -1;
    }
}

// ============================================================
// 27. UTILITAS
// ============================================================

uint32_t clampDuration(
    uint32_t requested,
    uint32_t maximum
) {

    if (requested == 0) {
        return maximum;
    }

    if (requested > maximum) {
        return maximum;
    }

    return requested;
}

String robotStateName() {

    switch (robotState) {

        case STATE_IDLE:
            return "IDLE";

        case STATE_MOVING:
            return "MOVING";

        case STATE_CLEANING:
            return "CLEANING";

        case STATE_EMERGENCY_STOP:
            return "EMERGENCY_STOP";

        case STATE_OFFLINE:
            return "OFFLINE";

        default:
            return "UNKNOWN";
    }
}
