// =============================================================================
//  Smart Soil Node — ESP32 / ESP32-S3 sensors-only firmware  (v1.0.0)
//
//  Wake → power probes → poll dual-depth RS485 soil probes (median of 5) →
//  read ORP / tensiometer / PAR / leaf wetness / O2 (ADS1115), air T/RH (SHT31),
//  wind, rain, battery & solar → ATC (EC25) → build the spec Section 6.2 JSON →
//  flush offline buffer → POST to /api/v1/telemetry/ingest → deep sleep.
//
//  ADVISORY / SENSORS-ONLY: there is no relay, valve, pump or downlink code.
// =============================================================================
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LittleFS.h>
#include <time.h>
#include <vector>
#include <ArduinoJson.h>
#include <ModbusMaster.h>
#include <Adafruit_SHT31.h>
#include <Adafruit_ADS1X15.h>
#include <Adafruit_INA219.h>
#include <PubSubClient.h>
#include "esp_sleep.h"
#include "driver/rtc_io.h"
#include "config.h"

// ---------------------------------------------------------------- state ------
RTC_DATA_ATTR uint32_t rainTips = 0;          // survives deep sleep
RTC_DATA_ATTR uint32_t bootCount = 0;
RTC_DATA_ATTR time_t lastReportEpoch = 0;
RTC_DATA_ATTR time_t nextReportEpoch = 0;

static const char* BUFFER_FILE = "/buffer.jsonl";
static const uint32_t MIN_VALID_EPOCH = 1700000000UL;  // 2023-11-14

HardwareSerial RS485(1);
ModbusMaster probe;
Adafruit_SHT31 sht31;
Adafruit_ADS1115 adsMain;
Adafruit_ADS1115 adsAux;
Adafruit_INA219 ina219(INA219_ADDR);
bool haveSht = false, haveAdsMain = false, haveAdsAux = false, haveIna = false;
volatile uint32_t windPulses = 0;
uint32_t awakeSince = 0;

struct ProbeData {
  bool ok = false;
  float vwc = NAN, temp = NAN, ecBulk = NAN, ecPore = NAN, ph = NAN, n = NAN, p = NAN, k = NAN;
};

// ---------------------------------------------------------------- helpers ----
static float medianOf(float* v, int n) {
  float tmp[16];
  int m = 0;
  for (int i = 0; i < n && m < 16; i++) if (!isnan(v[i])) tmp[m++] = v[i];
  if (m == 0) return NAN;
  for (int i = 1; i < m; i++) {            // insertion sort
    float key = tmp[i]; int j = i - 1;
    while (j >= 0 && tmp[j] > key) { tmp[j + 1] = tmp[j]; j--; }
    tmp[j + 1] = key;
  }
  return (m % 2) ? tmp[m / 2] : 0.5f * (tmp[m / 2 - 1] + tmp[m / 2]);
}

static float ec25(float ec, float tSoil) {        // spec Section 7.3 formula 2
  if (isnan(ec) || isnan(tSoil)) return ec;
  return ec / (1.0f + ATC_COEFF * (tSoil - 25.0f));
}

// Topp (1980) inverted with Newton's method: VWC (m3/m3) -> bulk permittivity.
static float permittivityFromVwc(float theta) {
  float e = 10.0f;
  for (int i = 0; i < 25; i++) {
    float f = -0.053f + 0.0292f * e - 0.00055f * e * e + 0.0000043f * e * e * e - theta;
    float df = 0.0292f - 0.0011f * e + 0.0000129f * e * e;
    if (fabsf(df) < 1e-6f) break;
    e -= f / df;
    if (e < 1.0f) e = 1.0f;
    if (e > 80.0f) e = 80.0f;
  }
  return e;
}

// Hilhorst (2000) pore-water EC from bulk EC. Unreliable below ~10 % VWC:
// calibrate against lab saturated-paste ECe using the app's lab profile.
static float porewaterEc(float ecBulk, float vwcPct, float tSoil) {
  if (isnan(ecBulk) || isnan(vwcPct)) return NAN;
  float eb = permittivityFromVwc(vwcPct / 100.0f);
  float ep = 80.3f - 0.37f * ((isnan(tSoil) ? 25.0f : tSoil) - 20.0f);
  float denom = eb - 4.1f;
  if (denom < 2.0f) denom = 2.0f;
  return ep * ecBulk / denom;
}

static void preTx() { digitalWrite(PIN_RS485_DE_RE, HIGH); }
static void postTx() { digitalWrite(PIN_RS485_DE_RE, LOW); }

static bool readRegs(uint8_t addr, uint16_t reg, uint8_t count, uint16_t* out) {
  probe.begin(addr, RS485);
  probe.preTransmission(preTx);
  probe.postTransmission(postTx);
  uint8_t rc = probe.readHoldingRegisters(reg, count);
  if (rc != probe.ku8MBSuccess) return false;
  for (uint8_t i = 0; i < count; i++) out[i] = probe.getResponseBuffer(i);
  return true;
}

static ProbeData readProbe(uint8_t addr, bool full) {
  ProbeData d;
  float vwc[MEDIAN_SAMPLES], tmp[MEDIAN_SAMPLES], ec[MEDIAN_SAMPLES], ph[MEDIAN_SAMPLES];
  float nn[MEDIAN_SAMPLES], pp[MEDIAN_SAMPLES], kk[MEDIAN_SAMPLES];
  int good = 0;
  for (int i = 0; i < MEDIAN_SAMPLES; i++) {
    vwc[i] = tmp[i] = ec[i] = ph[i] = nn[i] = pp[i] = kk[i] = NAN;
    uint16_t b[4];
    if (readRegs(addr, REG_MOISTURE, 4, b)) {
      vwc[i] = b[0] * 0.1f;
      tmp[i] = (int16_t)b[REG_TEMPERATURE - REG_MOISTURE] * 0.1f;
      ec[i] = b[REG_EC - REG_MOISTURE] / 1000.0f;   // µS/cm -> dS/m
      good++;
    }
    if (full) {
      uint16_t r1[1];
      if (readRegs(addr, REG_PH, 1, r1)) ph[i] = r1[0] * 0.01f;
      uint16_t r3[3];
      if (readRegs(addr, REG_NITROGEN, 3, r3)) { nn[i] = r3[0]; pp[i] = r3[1]; kk[i] = r3[2]; }
    }
    delay(200);
  }
  d.ok = good > 0;
  d.vwc = medianOf(vwc, MEDIAN_SAMPLES);
  d.temp = medianOf(tmp, MEDIAN_SAMPLES);
  d.ecBulk = medianOf(ec, MEDIAN_SAMPLES);
  d.ph = medianOf(ph, MEDIAN_SAMPLES);
  d.n = medianOf(nn, MEDIAN_SAMPLES);
  d.p = medianOf(pp, MEDIAN_SAMPLES);
  d.k = medianOf(kk, MEDIAN_SAMPLES);
  d.ecPore = porewaterEc(d.ecBulk, d.vwc, d.temp);
#if SEND_ATC_EC
  d.ecBulk = ec25(d.ecBulk, d.temp);
  d.ecPore = ec25(d.ecPore, d.temp);
#endif
  return d;
}

static float readAdsVolts(Adafruit_ADS1115& ads, uint8_t ch) {
  float v[MEDIAN_SAMPLES];
  for (int i = 0; i < MEDIAN_SAMPLES; i++) {
    v[i] = ads.computeVolts(ads.readADC_SingleEnded(ch));
    delay(20);
  }
  return medianOf(v, MEDIAN_SAMPLES);
}

static void IRAM_ATTR onWindPulse() { windPulses++; }

static void setNum(JsonObject o, const char* key, float v, int decimals) {
  if (isnan(v)) o[key] = nullptr;
  else o[key] = serialized(String(v, decimals));
}

static String isoTimestamp() {
  time_t now = time(nullptr);
  if (now < (time_t)MIN_VALID_EPOCH) return String();
  struct tm t;
  gmtime_r(&now, &t);
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &t);
  return String(buf);
}

// ---------------------------------------------------------------- network ----
static bool connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < WIFI_TIMEOUT_MS) delay(250);
  if (WiFi.status() != WL_CONNECTED) { Serial.println("[net] Wi-Fi failed"); return false; }
  Serial.printf("[net] Wi-Fi OK %s RSSI %d\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  if (time(nullptr) < (time_t)MIN_VALID_EPOCH) {
    configTime(0, 0, "pool.ntp.org", "time.google.com");
    uint32_t t1 = millis();
    while (time(nullptr) < (time_t)MIN_VALID_EPOCH && millis() - t1 < 6000) delay(200);
  }
  return true;
}

// Returns: 1 = delivered, 0 = keep for retry, -1 = rejected permanently (drop)
static int sendPayload(const String& json) {
#if USE_MQTT
  WiFiClientSecure tls;
  tls.setInsecure();                       // TODO: pin your broker's root CA for production
  PubSubClient mqtt(tls);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(2048);
  if (!mqtt.connect(DEVICE_ID, MQTT_USER, MQTT_PASS)) return 0;
  String topic = String("farms/") + FARM_ID + "/zones/" + ZONE_ID + "/telemetry";
  bool ok = mqtt.publish(topic.c_str(), json.c_str());
  mqtt.disconnect();
  return ok ? 1 : 0;
#else
  HTTPClient http;
  WiFiClient plain;
  WiFiClientSecure tls;
  String url = INGEST_URL;
  bool begun;
  if (url.startsWith("https://")) {
    tls.setInsecure();                     // TODO: pin the server certificate for production
    begun = http.begin(tls, url);
  } else {
    begun = http.begin(plain, url);
  }
  if (!begun) return 0;
  http.setTimeout(15000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Token", API_TOKEN);
  int code = http.POST(json);
  String body = http.getString();
  http.end();
  Serial.printf("[net] POST -> %d %s\n", code, body.substring(0, 120).c_str());
  if (code >= 200 && code < 300) return 1;
  if (code == 401 || code == 408 || code == 429 || code < 0 || code >= 500) return 0;
  return -1;                               // 4xx validation error: retrying will not help
#endif
}

// ---------------------------------------------------------------- buffer -----
static std::vector<String> bufferRead() {
  std::vector<String> lines;
  File f = LittleFS.open(BUFFER_FILE, "r");
  if (!f) return lines;
  while (f.available()) {
    String l = f.readStringUntil('\n');
    l.trim();
    if (l.length()) lines.push_back(l);
  }
  f.close();
  return lines;
}

static void bufferWrite(const std::vector<String>& lines) {
  File f = LittleFS.open(BUFFER_FILE, "w");
  if (!f) return;
  for (const auto& l : lines) f.println(l);
  f.close();
}

static void bufferAppend(const String& json) {
  std::vector<String> lines = bufferRead();
  lines.push_back(json);
  while (lines.size() > BUFFER_MAX_RECORDS) lines.erase(lines.begin());   // ring buffer: drop oldest
  bufferWrite(lines);
  Serial.printf("[buf] stored, %u record(s) waiting\n", (unsigned)lines.size());
}

static void bufferFlush() {
  std::vector<String> lines = bufferRead();
  if (lines.empty()) return;
  std::vector<String> keep;
  bool networkOk = true;
  for (const auto& l : lines) {
    if (!networkOk) { keep.push_back(l); continue; }
    int r = sendPayload(l);
    if (r == 0) { networkOk = false; keep.push_back(l); }
  }
  bufferWrite(keep);
  Serial.printf("[buf] flushed %u, kept %u\n", (unsigned)(lines.size() - keep.size()), (unsigned)keep.size());
}

// ---------------------------------------------------------------- sleep ------
static void goToSleep(uint32_t seconds) {
  if (seconds < 30) seconds = 30;
  Serial.printf("[pwr] deep sleep %u s\n", seconds);
  Serial.flush();
  digitalWrite(PIN_SENSOR_PWR, LOW);
  esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
  rtc_gpio_pullup_en((gpio_num_t)PIN_RAIN);
  rtc_gpio_pulldown_dis((gpio_num_t)PIN_RAIN);
  esp_sleep_enable_ext0_wakeup((gpio_num_t)PIN_RAIN, 0);   // reed switch closes to GND on each tip
  esp_deep_sleep_start();
}

static uint32_t secondsUntilNextReport() {
  time_t now = time(nullptr);
  if (now >= (time_t)MIN_VALID_EPOCH && nextReportEpoch > now) return (uint32_t)(nextReportEpoch - now);
  return REPORT_INTERVAL_MIN * 60;
}

// ---------------------------------------------------------------- main -------
void setup() {
  awakeSince = millis();
  Serial.begin(115200);
  delay(200);
  bootCount++;

  // A rain-bucket tip woke us: count it and go straight back to sleep.
  if (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_EXT0) {
    rainTips++;
    rtc_gpio_deinit((gpio_num_t)PIN_RAIN);
    pinMode(PIN_RAIN, INPUT_PULLUP);
    uint32_t t0 = millis();
    while (digitalRead(PIN_RAIN) == LOW && millis() - t0 < 500) delay(5);   // debounce
    goToSleep(secondsUntilNextReport());
  }

  Serial.printf("\n=== Smart Soil Node %s  boot #%u ===\n", FIRMWARE_VERSION, bootCount);
  pinMode(PIN_RS485_DE_RE, OUTPUT);
  postTx();
  pinMode(PIN_SENSOR_PWR, OUTPUT);
  pinMode(PIN_WIND, INPUT_PULLUP);
  rtc_gpio_deinit((gpio_num_t)PIN_RAIN);
  analogReadResolution(12);
  LittleFS.begin(true);
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);

  haveSht = sht31.begin(SHT31_ADDR);
  haveAdsMain = adsMain.begin(ADS_MAIN_ADDR);
  haveAdsAux = adsAux.begin(ADS_AUX_ADDR);
  haveIna = ina219.begin();
  if (haveAdsMain) adsMain.setGain(GAIN_ONE);        // ±4.096 V
  if (haveAdsAux) adsAux.setGain(GAIN_SIXTEEN);      // ±0.256 V for the mV-level O2 cell

  // ---- soil probes (12 V boost powered only while reading) ----
  digitalWrite(PIN_SENSOR_PWR, HIGH);
  delay(SENSOR_WARMUP_MS);
  RS485.begin(MODBUS_BAUD, SERIAL_8N1, PIN_RS485_RX, PIN_RS485_TX);
  ProbeData upper = readProbe(PROBE_UPPER_ADDR, true);
  ProbeData lower = readProbe(PROBE_LOWER_ADDR, false);

  float orp = NAN, tension = NAN, par = NAN, leafWet = NAN, o2 = NAN;
  if (haveAdsMain) {
    orp = readAdsVolts(adsMain, 0) * ORP_MV_PER_V + ORP_MV_OFFSET;
    tension = readAdsVolts(adsMain, 1) * TENSION_KPA_PER_V + TENSION_KPA_OFFSET;
    par = readAdsVolts(adsMain, 2) * PAR_PER_V;
    float lw = readAdsVolts(adsMain, 3);
    leafWet = constrain((lw - LEAF_WET_V_DRY) / (LEAF_WET_V_WET - LEAF_WET_V_DRY) * 100.0f, 0.0f, 100.0f);
  }
  if (haveAdsAux) o2 = readAdsVolts(adsAux, 0) * 1000.0f / O2_MV_AT_AIR * 20.95f;
  digitalWrite(PIN_SENSOR_PWR, LOW);

  // ---- canopy ----
  float airT = NAN, rh = NAN;
  if (haveSht) { airT = sht31.readTemperature(); rh = sht31.readHumidity(); }

  windPulses = 0;
  attachInterrupt(digitalPinToInterrupt(PIN_WIND), onWindPulse, FALLING);
  delay(WIND_SAMPLE_MS);
  detachInterrupt(digitalPinToInterrupt(PIN_WIND));
  float wind = (windPulses / (WIND_SAMPLE_MS / 1000.0f)) * WIND_MS_PER_HZ;

  // ---- power ----
  float battV = analogReadMilliVolts(PIN_BATT_ADC) / 1000.0f * BATT_DIVIDER_RATIO;
  float solarMa = haveIna ? ina219.getCurrent_mA() : NAN;

  // ---- network & time ----
  bool online = connectWiFi();
  time_t now = time(nullptr);
  float rainMmHr = 0.0f;
  if (now >= (time_t)MIN_VALID_EPOCH && lastReportEpoch >= (time_t)MIN_VALID_EPOCH && now > lastReportEpoch) {
    rainMmHr = rainTips * RAIN_MM_PER_TIP * 3600.0f / (float)(now - lastReportEpoch);
  }

  // ---- build the Section 6.2 payload ----
  JsonDocument doc;
  doc["schema_version"] = "1.0";
  doc["device_id"] = DEVICE_ID;
  doc["farm_id"] = FARM_ID;
  doc["zone_id"] = ZONE_ID;
  String ts = isoTimestamp();
  if (ts.length()) doc["timestamp_utc"] = ts;

  JsonObject hh = doc["hardware_health"].to<JsonObject>();
  setNum(hh, "battery_v", battV, 2);
  setNum(hh, "solar_charge_ma", solarMa, 0);
  if (online) hh["signal_rssi_dbm"] = WiFi.RSSI(); else hh["signal_rssi_dbm"] = nullptr;
  hh["firmware_version"] = FIRMWARE_VERSION;
  hh["ec_atc_applied"] = (bool)SEND_ATC_EC;
  JsonArray faults = hh["fault_flags"].to<JsonArray>();
  if (!upper.ok) faults.add("upper_probe_no_response");
  if (!lower.ok) faults.add("lower_probe_no_response");
  if (!haveSht) faults.add("sht31_not_found");
  if (!haveAdsMain) faults.add("ads1115_not_found");
  if (battV < BATTERY_LOW_V) faults.add("battery_low");

  JsonObject su = doc["soil_upper"].to<JsonObject>();
  su["depth_cm"] = UPPER_DEPTH_CM;
  setNum(su, "vwc_pct", upper.vwc, 1);
  setNum(su, "matric_potential_kpa", tension, 1);
  setNum(su, "temp_c", upper.temp, 1);
  setNum(su, "ec_bulk_ds_m", upper.ecBulk, 3);
  setNum(su, "ec_pore_ds_m", upper.ecPore, 3);
  setNum(su, "ph", upper.ph, 2);
  setNum(su, "n_ppm", upper.n, 0);
  setNum(su, "p_ppm", upper.p, 0);
  setNum(su, "k_ppm", upper.k, 0);
  setNum(su, "orp_mv", orp, 0);
  setNum(su, "o2_pct", o2, 1);

  JsonObject sl = doc["soil_lower"].to<JsonObject>();
  sl["depth_cm"] = LOWER_DEPTH_CM;
  setNum(sl, "vwc_pct", lower.vwc, 1);
  setNum(sl, "temp_c", lower.temp, 1);
  setNum(sl, "ec_pore_ds_m", lower.ecPore, 3);

  JsonObject mc = doc["microclimate"].to<JsonObject>();
  setNum(mc, "air_temp_c", airT, 1);
  setNum(mc, "rh_pct", rh, 1);
  setNum(mc, "par_umol_m2_s", par, 0);
  setNum(mc, "leaf_wetness_pct", leafWet, 0);
  setNum(mc, "wind_speed_ms", wind, 1);
  setNum(mc, "rain_mm_hr", rainMmHr, 2);
#if USE_MQTT
  doc["api_token"] = API_TOKEN;            // MQTT has no header: the subscriber reads the token here
#endif

  String json;
  serializeJson(doc, json);
  Serial.println(json);

  // ---- deliver (buffer first, newest last) ----
  if (online) {
    bufferFlush();
    if (sendPayload(json) == 0) bufferAppend(json);
  } else {
    bufferAppend(json);
  }
  rainTips = 0;
  if (now >= (time_t)MIN_VALID_EPOCH) {
    lastReportEpoch = now;
    nextReportEpoch = now + REPORT_INTERVAL_MIN * 60;
  }
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  uint32_t awakeS = (millis() - awakeSince) / 1000;
  uint32_t interval = REPORT_INTERVAL_MIN * 60;
  goToSleep(interval > awakeS ? interval - awakeS : 30);
}

void loop() {
  // Never reached: the node deep-sleeps at the end of setup().
}
