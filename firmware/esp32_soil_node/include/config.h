// =============================================================================
//  Smart Soil Node — configuration (edit this file before flashing)
//  Sensors-only, advisory-only: this firmware NEVER drives valves, relays or pumps.
// =============================================================================
#pragma once

// ---------- Identity & server (pre-filled by the in-app PDF exporter) --------
#define DEVICE_ID        "EGY-NODE-001"
#define FARM_ID          "1"
#define ZONE_ID          "1"
#define API_TOKEN        "PASTE_DEVICE_API_TOKEN_HERE"            // from data/seed_device_token.txt or the Simulator Lab page
#define INGEST_URL       "http://192.168.1.50:8000/api/v1/telemetry/ingest"  // your PC's LAN IP (run: python run.py --host 0.0.0.0)
#define FIRMWARE_VERSION "1.0.0"

// ---------- Wi-Fi ------------------------------------------------------------
#define WIFI_SSID        "YOUR_WIFI_SSID"
#define WIFI_PASSWORD    "YOUR_WIFI_PASSWORD"
#define WIFI_TIMEOUT_MS  20000

// ---------- 4G LTE-M / NB-IoT (optional, via TinyGSM + SIM7080G/SIM7600) -----
// Not compiled by default. Fill these and port connectNetwork() to TinyGSM if
// the field has no Wi-Fi coverage.
#define GSM_APN          "YOUR_SIM_APN"            // your mobile operator's APN
#define GSM_APN_USER     ""
#define GSM_APN_PASS     ""

// ---------- Optional MQTT over TLS uplink (instead of HTTPS POST) -----------
#define USE_MQTT         0
#define MQTT_HOST        "broker.example.com"
#define MQTT_PORT        8883
#define MQTT_USER        ""
#define MQTT_PASS        ""

// ---------- Timing -----------------------------------------------------------
#define REPORT_INTERVAL_MIN   10      // spec: poll every 5–15 minutes
#define SENSOR_WARMUP_MS      2000    // RS485 probes need ~1–2 s after power-up
#define MEDIAN_SAMPLES        5       // median noise filter (spec 6.1)
#define WIND_SAMPLE_MS        5000

// ---------- Behaviour --------------------------------------------------------
#define SEND_ATC_EC           1       // 1 = node applies ATC (EC25) and sets ec_atc_applied=true
#define ATC_COEFF             0.019f  // spec Section 7.3 formula 2
#define BUFFER_MAX_RECORDS    200     // offline LittleFS ring buffer
#define BATTERY_LOW_V         12.0f   // LiFePO4 12.8 V pack ≈ 20 % state of charge

// ---------- Pin map ------------------------------------------------------------
#if defined(BOARD_ESP32_CLASSIC)
  #define PIN_RS485_RX     16
  #define PIN_RS485_TX     17
  #define PIN_RS485_DE_RE  4
  #define PIN_I2C_SDA      21
  #define PIN_I2C_SCL      22
  #define PIN_RAIN         27   // RTC GPIO — wakes the node on each bucket tip
  #define PIN_WIND         26
  #define PIN_SENSOR_PWR   25   // gate of the logic-level MOSFET feeding the 12 V boost converter
  #define PIN_BATT_ADC     34
#else  // ESP32-S3-DevKitC-1 (default)
  #define PIN_RS485_RX     18
  #define PIN_RS485_TX     17
  #define PIN_RS485_DE_RE  16
  #define PIN_I2C_SDA      8
  #define PIN_I2C_SCL      9
  #define PIN_RAIN         4    // RTC GPIO
  #define PIN_WIND         5
  #define PIN_SENSOR_PWR   15
  #define PIN_BATT_ADC     1    // ADC1_CH0
#endif

#define BATT_DIVIDER_RATIO   5.545f   // 100 kΩ / 22 kΩ divider: Vbatt = Vadc × (122/22)

// ---------- RS485 Modbus RTU soil probes ---------------------------------------
#define MODBUS_BAUD          9600
#define PROBE_UPPER_ADDR     1        // Sensor A (feeder roots, 10–25 cm)
#define PROBE_LOWER_ADDR     2        // Sensor B (bottom of root zone, 20–60 cm)
#define UPPER_DEPTH_CM       15       // set from spec Table 4.1 for your crop
#define LOWER_DEPTH_CM       35

// Register map for the common "7-in-1" RS485 soil probe (moisture/temp/EC/pH/NPK).
// VERIFY AGAINST YOUR PROBE'S DATASHEET — vendors differ.
#define REG_PH               0x0006   // ×0.01 pH
#define REG_MOISTURE         0x0012   // ×0.1 %VWC   (block of 4: moisture, temp, -, EC)
#define REG_TEMPERATURE      0x0013   // ×0.1 °C, signed
#define REG_EC               0x0015   // µS/cm (bulk EC)
#define REG_NITROGEN         0x001E   // mg/kg (block of 3: N, P, K)
#define REG_PHOSPHORUS       0x001F
#define REG_POTASSIUM        0x0020

// ---------- I2C analog front-end (ADS1115) ------------------------------------
#define ADS_MAIN_ADDR        0x48     // A0 ORP, A1 tensiometer, A2 PAR, A3 leaf wetness
#define ADS_AUX_ADDR         0x49     // A0 soil O2 (optional)
#define SHT31_ADDR           0x44
#define INA219_ADDR          0x40     // solar charge current

// Linear transfer functions (value = volts × GAIN + OFFSET) — set from each transmitter's datasheet.
#define ORP_MV_PER_V         1000.0f  // e.g. isolated ORP transmitter 0–2 V → −1000…+1000 mV
#define ORP_MV_OFFSET        -1000.0f
#define TENSION_KPA_PER_V    85.36f   // Watermark interface 0–2.8 V → 0–239 kPa
#define TENSION_KPA_OFFSET   0.0f
#define PAR_PER_V            1000.0f  // quantum sensor 0–2.5 V → 0–2500 µmol/m²/s
#define LEAF_WET_V_DRY       0.445f   // dielectric leaf-wetness sensor: dry / fully wet voltages
#define LEAF_WET_V_WET       1.400f
#define O2_MV_AT_AIR         55.0f    // galvanic O2 sensor output in free air (20.95 % O2) — calibrate

// ---------- Rain & wind --------------------------------------------------------
#define RAIN_MM_PER_TIP      0.2794f
#define WIND_MS_PER_HZ       0.667f   // cup anemometer: 2.4 km/h per Hz
