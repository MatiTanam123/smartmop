
#ifndef CONFIG_H
#define CONFIG_H

// ==================================================
// KONFIGURASI WIFI DAN BACKEND
// ==================================================

#define WIFI_SSID       "NAMA_WIFI"
#define WIFI_PASSWORD   "PASSWORD_WIFI"

#define API_BASE_URL    "http://192.168.1.100:5000/api"
#define API_DEVICE_KEY  "ISI_DEVICE_KEY"

#define DEVICE_CODE     "ESP32_MAIN_01"
#define FIRMWARE_VERSION "1.0.0"


// ==================================================
// MOTOR PENGGERAK - DRIVER BTS7960
// ==================================================

// Motor sisi kiri
#define MOTOR_KIRI_RPWM  25
#define MOTOR_KIRI_LPWM  26
#define MOTOR_KIRI_REN   18
#define MOTOR_KIRI_LEN   19

// Motor sisi kanan
#define MOTOR_KANAN_RPWM 27
#define MOTOR_KANAN_LPWM 14
#define MOTOR_KANAN_REN  21
#define MOTOR_KANAN_LEN  22


// ==================================================
// MOTOR PEL
// ==================================================

#define MOTOR_PEL_IN1  32
#define MOTOR_PEL_IN2  33


// ==================================================
// POMPA SABUN
// ==================================================

#define POMPA_PIN 23


// ==================================================
// SENSOR
// ==================================================

// Sensor tegangan baterai
#define SENSOR_BATERAI_PIN 34

// Sensor level sabun (float switch)
#define SENSOR_SABUN_PIN  35


// ==================================================
// KONFIGURASI PEMBACAAN BATERAI
// ==================================================

// Nilai resistor pembagi tegangan (contoh)
#define BATTERY_R1  30000.0
#define BATTERY_R2  7500.0

#define BATTERY_ADC_MAX 4095.0
#define BATTERY_REFERENCE_VOLTAGE 3.3

// Kalibrasi pembacaan tegangan
#define BATTERY_CALIBRATION 1.0


// ==================================================
// KONFIGURASI WAKTU
// ==================================================

#define WIFI_RECONNECT_INTERVAL 5000

#define HEARTBEAT_INTERVAL 30000
#define TELEMETRY_INTERVAL 10000
#define COMMAND_POLL_INTERVAL 2000

#define SERVER_TIMEOUT 30000

// Durasi gerakan default
#define DEFAULT_MOVEMENT_DURATION 1000
#define MAX_MOVEMENT_DURATION 5000

// Durasi pompa
#define DEFAULT_PUMP_DURATION 1000

// Durasi pembersihan
#define DEFAULT_CLEANING_DURATION 30000


#endif
