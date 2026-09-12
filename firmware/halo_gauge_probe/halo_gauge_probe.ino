/*
 * ============================================================================
 *  HALO GAUGE PROBE
 *  Stage 0 + 1: Contrast and SNR characterization
 * ----------------------------------------------------------------------------
 *  Board       : Heltec WiFi LoRa 32 V2 (ESP32, 0.96 inch SSD1306 OLED)
 *  Sensors     : TCS34725 RGB color sensor (CJMCU clone, I2C address 0x29)
 *                2x ALS-PT19 phototransistor breakout (analog out)
 *  Light       : TCS34725 onboard white LED, switched via its LED pin
 *                optional external blue LED (~470 nm) via 220 ohm
 *  Purpose     : Quantify the optical contrast between a white gauge dial
 *                and a light-yellow needle. Decides whether a reflective
 *                sensor arc is viable before any PCB is manufactured.
 *  Method      : LED ON / LED OFF differential measurement per channel,
 *                N samples each, mean and standard deviation, then
 *                contrast = (white - yellow) / white and
 *                SNR = |white - yellow| / combined noise.
 *  Go / No-Go  : SNR >= 10 on at least one channel.
 *
 *  Link        : USB 115200 baud, and TCP port 3333 when WiFi is configured
 *  Serial      : 115200 baud, single-key commands, see 'h'. 'j' switches to
 *                JSON lines for the lab software (one object per line).
 * ============================================================================
 */

#include <WiFi.h>
#include <ArduinoOTA.h>
#include <Wire.h>
#include <Adafruit_TCS34725.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <math.h>

// ---------------------------------------------------------------------------
// Network. Fill in your own credentials. Leave WIFI_SSID empty to stay on USB
// only. With WiFi on, the board also listens on port 3333 and speaks exactly
// the same protocol there, so the USB cable can be pulled off the PC.
// ---------------------------------------------------------------------------
static const char* WIFI_SSID = "";
static const char* WIFI_PASS = "";
static const uint16_t NET_PORT = 3333;

// ---------------------------------------------------------------------------
// Pins, Heltec WiFi LoRa 32 V2
// ---------------------------------------------------------------------------
static const int PIN_I2C_SDA  = 4;    // shared: OLED + TCS34725
static const int PIN_I2C_SCL  = 15;   // shared: OLED + TCS34725
static const int PIN_OLED_RST = 16;
static const int PIN_VEXT     = 21;   // LOW enables Vext, powers the OLED
static const int PIN_TCS_LED  = 23;   // TCS34725 board pin "LED", HIGH = on
static const int PIN_BLUE_LED = 22;   // external blue LED, anode via 220 ohm
static const int PIN_PT19_A   = 36;   // ALS-PT19 board A, pin "out"
static const int PIN_PT19_B   = 37;   // ALS-PT19 board B, pin "out"

// ---------------------------------------------------------------------------
// Measurement parameters
// ---------------------------------------------------------------------------
static int            sampleCount    = 50;      // per series (on and off each), key n
static const int      ADC_OVERSAMPLE = 16;      // ADC reads averaged per sample
static const uint16_t SAT_LIMIT      = 65000;   // TCS34725 clear channel limit
static const int      SETTLE_MS      = 250;     // after switching the light
static const double   SNR_GO         = 10.0;

// ---------------------------------------------------------------------------
// Channels
// ---------------------------------------------------------------------------
enum Channel { CH_C = 0, CH_R, CH_G, CH_B, CH_PTA, CH_PTB, CH_COUNT };
static const char* CH_NAME[CH_COUNT] = { "C", "R", "G", "B", "PT-A", "PT-B" };
static const char* CH_UNIT[CH_COUNT] = { "cnt", "cnt", "cnt", "cnt", "mV", "mV" };

enum Illum  { ILLUM_WHITE = 0, ILLUM_BLUE = 1, ILLUM_COUNT };
enum Target { TGT_WHITE = 0, TGT_YELLOW = 1, TGT_COUNT = 2, TGT_POINT = 2 };
static const char* ILLUM_NAME[ILLUM_COUNT] = { "WHITE LED", "BLUE LED" };
static const char* TGT_NAME[3]            = { "WHITE (dial)", "YELLOW (needle)", "POINT" };

struct Stats {
  double mean[CH_COUNT];
  double sd[CH_COUNT];
};

struct Series {
  bool   valid;
  bool   saturated;
  Stats  on;
  Stats  off;
  double signal[CH_COUNT];   // on.mean - off.mean, ambient removed
  double noise[CH_COUNT];    // sqrt(on.sd^2 + off.sd^2)
};

static Series results[ILLUM_COUNT][TGT_COUNT];

// ---------------------------------------------------------------------------
// Gain table for the TCS34725
// ---------------------------------------------------------------------------
static const tcs34725Gain_t GAIN_VALUE[4] = {
  TCS34725_GAIN_1X, TCS34725_GAIN_4X, TCS34725_GAIN_16X, TCS34725_GAIN_60X
};
static const char* GAIN_NAME[4] = { "1x", "4x", "16x", "60x" };
static int gainIndex = 2;   // start at 16x

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------
// Everything the probe prints goes to USB and, when connected, to the network
// client as well, so both look identical.
class Tee : public Print {
public:
  WiFiClient client;
  size_t write(uint8_t c) override {
    Serial.write(c);
    if (client && client.connected()) client.write(c);
    return 1;
  }
  size_t write(const uint8_t* buf, size_t n) override {
    Serial.write(buf, n);
    if (client && client.connected()) client.write(buf, n);
    return n;
  }
};
static Tee out;
static WiFiServer netServer(NET_PORT);
static bool netUp = false;

Adafruit_TCS34725 tcs(TCS34725_INTEGRATIONTIME_154MS, TCS34725_GAIN_16X);
Adafruit_SSD1306  oled(128, 64, &Wire, PIN_OLED_RST);

static Illum         illum   = ILLUM_BLUE;   // start with the blue LED, white is optional
static bool          liveOn  = true;
static bool          oledOk  = false;
static bool          tcsOk   = false;   // colour sensor is optional, phototransistors alone are fine
static bool          jsonOn  = false;   // machine readable output for the lab software, toggled with j
static const char*   FW_VERSION = "probe-0.5";
static unsigned long lastLive = 0;

// ---------------------------------------------------------------------------
// Forward declarations for the display helpers used inside the sampling loop
// ---------------------------------------------------------------------------
static void centeredText(const char* txt, int size, int y);
static void oledArming();
static void oledCountdown();
static void oledRun(Target tgt, bool ledOn, int n, double value, const char* name,
                    const char* unit);

// ---------------------------------------------------------------------------
// Light control
// ---------------------------------------------------------------------------
static void setLight(Illum which, bool on) {
  digitalWrite(PIN_TCS_LED,  (on && which == ILLUM_WHITE) ? HIGH : LOW);
  digitalWrite(PIN_BLUE_LED, (on && which == ILLUM_BLUE)  ? HIGH : LOW);
}

static void lightsOff() {
  digitalWrite(PIN_TCS_LED,  LOW);
  digitalWrite(PIN_BLUE_LED, LOW);
}

// ---------------------------------------------------------------------------
// One raw sample across all channels. Returns true if the clear channel
// is saturated.
// ---------------------------------------------------------------------------
static bool readSample(double out[CH_COUNT]) {
  uint16_t r = 0, g = 0, b = 0, c = 0;
  if (tcsOk) {
    tcs.getRawData(&r, &g, &b, &c);   // blocks for one integration time
  } else {
    delay(154);                       // keep the sample timing without the sensor
  }

  uint32_t accA = 0, accB = 0;
  for (int i = 0; i < ADC_OVERSAMPLE; i++) {
    accA += analogReadMilliVolts(PIN_PT19_A);
    accB += analogReadMilliVolts(PIN_PT19_B);
  }

  out[CH_C]   = c;
  out[CH_R]   = r;
  out[CH_G]   = g;
  out[CH_B]   = b;
  out[CH_PTA] = (double)accA / ADC_OVERSAMPLE;
  out[CH_PTB] = (double)accB / ADC_OVERSAMPLE;

  return c >= SAT_LIMIT;
}

// ---------------------------------------------------------------------------
// Collect one series of sampleCount with the light in the given state.
// ---------------------------------------------------------------------------
static bool collect(Stats& st, bool lightOn, Target tgt) {
  double sum[CH_COUNT]   = {0};
  double sumSq[CH_COUNT] = {0};
  bool   saturated = false;

  setLight(illum, lightOn);
  delay(SETTLE_MS);

  for (int n = 0; n < sampleCount; n++) {
    double s[CH_COUNT];
    if (readSample(s)) saturated = true;
    if (jsonOn) jsonSample(tgt, lightOn, n, s);
    if ((n % 2) == 0) {
      bool colour = s[CH_C] > 5.0;
      oledRun(tgt, lightOn, (lightOn ? 0 : sampleCount) + n,
              colour ? s[CH_C] : s[CH_PTA], colour ? "C" : "PT-A", colour ? "cnt" : "mV");
    }
    for (int ch = 0; ch < CH_COUNT; ch++) {
      sum[ch]   += s[ch];
      sumSq[ch] += s[ch] * s[ch];
    }
    if ((n % 10) == 9 && !jsonOn) out.print('.');
  }
  lightsOff();

  for (int ch = 0; ch < CH_COUNT; ch++) {
    st.mean[ch] = sum[ch] / sampleCount;
    double var  = (sumSq[ch] - sampleCount * st.mean[ch] * st.mean[ch]) / (sampleCount - 1);
    st.sd[ch]   = var > 0 ? sqrt(var) : 0.0;
  }
  return saturated;
}

// ---------------------------------------------------------------------------
// OLED helpers
// ---------------------------------------------------------------------------
static void oledMessage(const char* line1, const char* line2) {
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.println("HALO GAUGE PROBE");
  oled.setTextSize(2);
  oled.setCursor(0, 20);
  oled.println(line1);
  oled.setTextSize(1);
  oled.setCursor(0, 50);
  oled.println(line2);
  oled.display();
}

// ---------------------------------------------------------------------------
// Display animation. The SSD1306 is 128 x 64 and one bit deep, so there is no
// fading: smoothness has to come from geometry that moves every frame. All
// sequences run at 40 frames per second off millis(), never off delay chains,
// and every screen change is a wipe rather than a cut.
// ---------------------------------------------------------------------------
static const int SCR_W = 128, SCR_H = 64;
static const uint32_t FRAME_MS = 25;

static float easeOut(float t) { return 1.0f - (1.0f - t) * (1.0f - t); }
static float easeInOut(float t) { return t < 0.5f ? 2 * t * t : 1 - 2 * (1 - t) * (1 - t); }

// Arc drawn from short segments, used as a sweeping progress ring.
static void oledArc(int cx, int cy, int r, float a0, float a1, int thickness) {
  int steps = max(3, (int)(fabsf(a1 - a0) * r / 3.0f));
  for (int i = 0; i < steps; i++) {
    float a = a0 + (a1 - a0) * i / (float)steps;
    float b = a0 + (a1 - a0) * (i + 1) / (float)steps;
    for (int t = 0; t < thickness; t++) {
      oled.drawLine(cx + cosf(a) * (r - t), cy + sinf(a) * (r - t),
                    cx + cosf(b) * (r - t), cy + sinf(b) * (r - t), SSD1306_WHITE);
    }
  }
}

static void centeredText(const char* txt, int size, int y) {
  int w = strlen(txt) * 6 * size;
  oled.setTextSize(size);
  oled.setCursor((SCR_W - w) / 2, y);
  oled.print(txt);
}

// Iris wipe: two shutters close over the current picture, then open on the next.
static void oledWipeOut(uint32_t ms) {
  if (!oledOk) return;
  uint32_t t0 = millis();
  for (;;) {
    float t = (millis() - t0) / (float)ms;
    if (t >= 1.0f) break;
    int h = (int)(easeInOut(t) * (SCR_H / 2 + 1));
    oled.fillRect(0, 0, SCR_W, h, SSD1306_BLACK);
    oled.fillRect(0, SCR_H - h, SCR_W, h, SSD1306_BLACK);
    oled.drawFastHLine(0, h, SCR_W, SSD1306_WHITE);
    oled.drawFastHLine(0, SCR_H - h - 1, SCR_W, SSD1306_WHITE);
    oled.display();
    delay(FRAME_MS);
  }
  oled.clearDisplay();
  oled.display();
}

// One boot line sliding in from the right, then settling.
static void oledSlideLine(const char* txt, int y, uint32_t ms) {
  if (!oledOk) return;
  uint32_t t0 = millis();
  for (;;) {
    float t = (millis() - t0) / (float)ms;
    if (t >= 1.0f) break;
    int x = (int)((1.0f - easeOut(t)) * SCR_W);
    oled.fillRect(0, y, SCR_W, 10, SSD1306_BLACK);
    oled.setTextSize(1);
    oled.setCursor(2 + x, y);
    oled.print(txt);
    oled.display();
    delay(FRAME_MS);
  }
  oled.fillRect(0, y, SCR_W, 10, SSD1306_BLACK);
  oled.setTextSize(1);
  oled.setCursor(2, y);
  oled.print(txt);
  oled.display();
}

// Arming sequence, shown once after boot. Every line is a real setting.
static void oledArming() {
  if (!oledOk) return;
  oled.clearDisplay();
  centeredText("HALO PROBE", 1, 0);
  oled.drawFastHLine(0, 10, SCR_W, SSD1306_WHITE);
  oled.display();
  char l1[24], l2[24];
  snprintf(l1, sizeof(l1), "BEAM 470nm ARMED");
  snprintf(l2, sizeof(l2), "INTEGRATION 154ms");
  oledSlideLine(l1, 16, 260);
  oledSlideLine("DIFFERENTIAL MODE", 28, 260);
  oledSlideLine(l2, 40, 260);
  oledSlideLine(tcsOk ? "RGBC + PT LINKED" : "PT CHANNELS LINKED", 52, 260);
  delay(500);
  oledWipeOut(220);
}

// Countdown. The digit sits inside a ring that sweeps a full turn every second
// while the iris contracts, so nothing jumps between steps.
static void oledCountdown() {
  if (!oledOk) return;
  const int cx = SCR_W / 2, cy = 34;
  for (int i = 3; i >= 1; i--) {
    uint32_t t0 = millis();
    for (;;) {
      float t = (millis() - t0) / 1000.0f;
      if (t >= 1.0f) break;
      oled.clearDisplay();
      oled.setTextColor(SSD1306_WHITE);
      oled.setTextSize(1);
      oled.setCursor(0, 0);
      oled.print("ALIGNING");
      oled.setCursor(74, 0);
      oled.print("HOLD STILL");
      oled.drawFastHLine(0, 10, SCR_W, SSD1306_WHITE);

      int outer = 28 - (3 - i) * 2;                    // iris steps in per second
      int r = outer - (int)(easeInOut(t) * 3.0f);      // and breathes within it
      oledArc(cx, cy, r, -1.5708f, -1.5708f + 6.2832f * t, 2);
      oled.drawCircle(cx, cy, r - 6, SSD1306_WHITE);

      char d[2] = { (char)('0' + i), 0 };
      oled.setTextSize(3);
      oled.setCursor(cx - 8, cy - 11);
      oled.print(d);
      oled.display();
      delay(FRAME_MS);
    }
  }
  // the ring collapses into the word, no cut
  uint32_t t0 = millis();
  for (;;) {
    float t = (millis() - t0) / 420.0f;
    if (t >= 1.0f) break;
    oled.clearDisplay();
    oled.setTextSize(1);
    oled.setCursor(0, 0);
    oled.print("ALIGNING");
    oled.drawFastHLine(0, 10, SCR_W, SSD1306_WHITE);
    int r = (int)(24 - easeOut(t) * 22);
    oledArc(cx, cy, max(r, 2), -1.5708f, 4.7124f, 2);
    if (t > 0.45f) centeredText("MEASURING", 1, cy - 4);
    oled.display();
    delay(FRAME_MS);
  }
}

// Live screen while a series runs. The number is damped so it does not jitter,
// the bar grows continuously and a scan dot travels along it.
static void oledRun(Target tgt, bool ledOn, int n, double value, const char* name,
                    const char* unit) {
  if (!oledOk) return;
  static double shown = 0.0;
  static int lastN = -1;
  if (n < lastN) shown = value;              // new series, start where we are
  lastN = n;
  shown += (value - shown) * 0.35;           // first order damping

  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.print(tgt == TGT_WHITE ? "WHITE" : (tgt == TGT_YELLOW ? "YELLOW" : "POINT"));
  oled.setCursor(62, 0);
  oled.print(ledOn ? "BEAM ON" : "AMBIENT");
  if (ledOn) oled.fillCircle(122, 3, 3, SSD1306_WHITE);
  else       oled.drawCircle(122, 3, 3, SSD1306_WHITE);
  oled.drawFastHLine(0, 10, SCR_W, SSD1306_WHITE);

  char buf[16];
  snprintf(buf, sizeof(buf), "%ld", (long)(shown + 0.5));
  oled.setTextSize(3);
  oled.setCursor(2, 18);
  oled.print(buf);
  oled.setTextSize(1);
  oled.setCursor(2 + (int)strlen(buf) * 18 + 4, 32);
  oled.print(unit);

  oled.setTextSize(1);
  oled.setCursor(2, 44);
  oled.print(name);
  snprintf(buf, sizeof(buf), "%d/%d", n, sampleCount * 2);
  oled.setCursor(SCR_W - (int)strlen(buf) * 6 - 2, 44);
  oled.print(buf);

  int total = sampleCount * 2;
  int w = (n * (SCR_W - 4)) / max(total, 1);
  oled.drawRect(0, 54, SCR_W, 9, SSD1306_WHITE);
  oled.fillRect(2, 56, w, 5, SSD1306_WHITE);
  int dot = 2 + w;                            // scan dot rides the front edge
  if (dot < SCR_W - 3) {
    oled.drawFastVLine(dot, 55, 7, SSD1306_WHITE);
    oled.drawFastVLine(dot + 1, 55, 7, SSD1306_WHITE);
  }
  oled.display();
}

static void oledLive(const double s[CH_COUNT], bool sat) {
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.print("PROBE ");
  oled.print(ILLUM_NAME[illum]);
  oled.print(" ");
  oled.print(GAIN_NAME[gainIndex]);
  oled.setCursor(0, 14);
  oled.print("C "); oled.print((int)s[CH_C]);
  if (sat) oled.print(" SAT");
  oled.setCursor(0, 24);
  oled.print("R "); oled.print((int)s[CH_R]);
  oled.print("  G "); oled.print((int)s[CH_G]);
  oled.setCursor(0, 34);
  oled.print("B "); oled.print((int)s[CH_B]);
  oled.setCursor(0, 46);
  oled.print("PT-A "); oled.print((int)s[CH_PTA]); oled.print(" mV");
  oled.setCursor(0, 56);
  oled.print("PT-B "); oled.print((int)s[CH_PTB]); oled.print(" mV");
  oled.display();
}

// ---------------------------------------------------------------------------
// JSON output for the lab software (one object per line, toggled with j)
// ---------------------------------------------------------------------------
static const char* lightName(Illum il)   { return il == ILLUM_WHITE ? "white" : "blue"; }
static const char* targetName(Target t)  {
  return t == TGT_WHITE ? "white" : (t == TGT_YELLOW ? "yellow" : "point");
}

static void jsonSampleValues(char* buf, size_t len, const double s[CH_COUNT]) {
  snprintf(buf, len, "\"c\":%.0f,\"r\":%.0f,\"g\":%.0f,\"b\":%.0f,\"pta\":%.1f,\"ptb\":%.1f",
           s[CH_C], s[CH_R], s[CH_G], s[CH_B], s[CH_PTA], s[CH_PTB]);
}

static void jsonHello() {
  out.printf("{\"type\":\"hello\",\"fw\":\"%s\",\"tcs\":%d,\"oled\":%d,\"light\":\"%s\",\"gain\":\"%s\",\"samples\":%d}\n",
                FW_VERSION, tcsOk ? 1 : 0, oledOk ? 1 : 0, lightName(illum), GAIN_NAME[gainIndex], sampleCount);
}

static void jsonAck(const char* cmd) {
  out.printf("{\"type\":\"ack\",\"cmd\":\"%s\",\"light\":\"%s\",\"gain\":\"%s\",\"samples\":%d,\"live\":%d}\n",
                cmd, lightName(illum), GAIN_NAME[gainIndex], sampleCount, liveOn ? 1 : 0);
}

static void jsonLive(const double s[CH_COUNT], bool sat) {
  char v[128]; jsonSampleValues(v, sizeof(v), s);
  out.printf("{\"type\":\"live\",\"t\":%lu,%s,\"sat\":%d,\"light\":\"%s\",\"gain\":\"%s\"}\n",
                (unsigned long)millis(), v, sat ? 1 : 0, lightName(illum), GAIN_NAME[gainIndex]);
}

static void jsonSample(Target tgt, bool ledOn, int n, const double s[CH_COUNT]) {
  char v[128]; jsonSampleValues(v, sizeof(v), s);
  out.printf("{\"type\":\"sample\",\"target\":\"%s\",\"led\":%d,\"n\":%d,%s}\n",
                targetName(tgt), ledOn ? 1 : 0, n, v);
}

static void jsonStats(const char* key, const Stats& st) {
  out.printf("\"%s\":{", key);
  for (int ch = 0; ch < CH_COUNT; ch++) {
    out.printf("%s\"%s\":[%.2f,%.2f]", ch ? "," : "", CH_NAME[ch], st.mean[ch], st.sd[ch]);
  }
  out.print("}");
}

static void jsonSeries(Target tgt, const Series& res) {
  out.printf("{\"type\":\"series\",\"target\":\"%s\",\"light\":\"%s\",\"gain\":\"%s\",\"samples\":%d,\"saturated\":%d,",
                targetName(tgt), lightName(illum), GAIN_NAME[gainIndex], sampleCount, res.saturated ? 1 : 0);
  jsonStats("on", res.on); out.print(","); jsonStats("off", res.off);
  out.print(",\"signal\":{");
  for (int ch = 0; ch < CH_COUNT; ch++) out.printf("%s\"%s\":%.2f", ch ? "," : "", CH_NAME[ch], res.signal[ch]);
  out.print("},\"noise\":{");
  for (int ch = 0; ch < CH_COUNT; ch++) out.printf("%s\"%s\":%.2f", ch ? "," : "", CH_NAME[ch], res.noise[ch]);
  out.println("}}");
}

// ---------------------------------------------------------------------------
// Run one full series for a target under the current illumination
// ---------------------------------------------------------------------------
static Series pointSeries;   // a free measurement, not part of the white/yellow pair

static void runSeries(Target tgt) {
  Series& res = (tgt == TGT_POINT) ? pointSeries : results[illum][tgt];

  if (jsonOn) {
    out.printf("{\"type\":\"run\",\"target\":\"%s\",\"light\":\"%s\",\"gain\":\"%s\",\"samples\":%d}\n",
                  targetName(tgt), lightName(illum), GAIN_NAME[gainIndex], sampleCount);
  } else {
    out.println();
    out.print("[RUN] target=");
    out.print(TGT_NAME[tgt]);
    out.print("  light=");
    out.print(ILLUM_NAME[illum]);
    out.print("  gain=");
    out.print(GAIN_NAME[gainIndex]);
    out.print("  samples=");
    out.println(sampleCount);
  }


  if (!jsonOn) out.print("      light ON  ");
  bool satOn = collect(res.on, true, tgt);
  if (!jsonOn) out.println(" done");
  if (!jsonOn) out.print("      light OFF ");
  bool satOff = collect(res.off, false, tgt);
  if (!jsonOn) out.println(" done");

  res.saturated = satOn || satOff;
  for (int ch = 0; ch < CH_COUNT; ch++) {
    res.signal[ch] = res.on.mean[ch] - res.off.mean[ch];
    res.noise[ch]  = sqrt(res.on.sd[ch] * res.on.sd[ch] + res.off.sd[ch] * res.off.sd[ch]);
  }
  res.valid = true;

  if (jsonOn) { jsonSeries(tgt, res); oledMessage("DONE", "press r for report"); return; }

  out.println();
  out.println("      ch     on.mean   on.sd   off.mean  off.sd   signal   noise");
  for (int ch = 0; ch < CH_COUNT; ch++) {
    char line[96];
    snprintf(line, sizeof(line), "      %-5s %9.1f %7.2f %9.1f %7.2f %8.1f %7.2f %s",
             CH_NAME[ch], res.on.mean[ch], res.on.sd[ch],
             res.off.mean[ch], res.off.sd[ch],
             res.signal[ch], res.noise[ch], CH_UNIT[ch]);
    out.println(line);
  }
  if (res.saturated) {
    out.println("      WARNING: clear channel saturated, lower the gain with 'g' and repeat");
  }
  oledMessage("DONE", "press r for report");
}

// ---------------------------------------------------------------------------
// Report: contrast and SNR for every illumination with both targets measured
// ---------------------------------------------------------------------------
static void reportJson() {
  bool anything = false;
  for (int il = 0; il < ILLUM_COUNT; il++) {
    Series& w = results[il][TGT_WHITE];
    Series& y = results[il][TGT_YELLOW];
    if (!w.valid || !y.valid) continue;
    anything = true;
    double bestSnr = 0; int bestCh = -1;
    out.printf("{\"type\":\"report\",\"light\":\"%s\",\"saturated\":%d,\"channels\":[", lightName((Illum)il), (w.saturated || y.saturated) ? 1 : 0);
    for (int ch = 0; ch < CH_COUNT; ch++) {
      double sw = w.signal[ch], sy = y.signal[ch];
      double contrast = (sw != 0.0) ? (sw - sy) / sw : 0.0;
      double noise = sqrt(w.noise[ch] * w.noise[ch] + y.noise[ch] * y.noise[ch]);
      double snr = (noise > 0.0) ? fabs(sw - sy) / noise : 0.0;
      if (snr > bestSnr) { bestSnr = snr; bestCh = ch; }
      out.printf("%s{\"ch\":\"%s\",\"unit\":\"%s\",\"white\":%.2f,\"yellow\":%.2f,\"contrast\":%.4f,\"noise\":%.2f,\"snr\":%.2f,\"go\":%d}",
                    ch ? "," : "", CH_NAME[ch], CH_UNIT[ch], sw, sy, contrast, noise, snr, snr >= SNR_GO ? 1 : 0);
    }
    out.printf("],\"best\":\"%s\",\"best_snr\":%.2f,\"go\":%d}\n", bestCh >= 0 ? CH_NAME[bestCh] : "none", bestSnr, bestSnr >= SNR_GO ? 1 : 0);
  }
  if (!anything) out.println("{\"type\":\"report\",\"empty\":1}");
}

static void report() {
  if (jsonOn) { reportJson(); return; }
  bool anything = false;

  for (int il = 0; il < ILLUM_COUNT; il++) {
    Series& w = results[il][TGT_WHITE];
    Series& y = results[il][TGT_YELLOW];
    if (!w.valid || !y.valid) continue;
    anything = true;

    out.println();
    out.println("==========================================================");
    out.print  ("  REPORT  light=");
    out.println(ILLUM_NAME[il]);
    out.println("==========================================================");
    out.println("  ch     white     yellow   contrast    noise     SNR   verdict");

    double bestSnr = 0;
    int    bestCh  = -1;

    for (int ch = 0; ch < CH_COUNT; ch++) {
      double sw = w.signal[ch];
      double sy = y.signal[ch];
      double contrast = (sw != 0.0) ? (sw - sy) / sw : 0.0;
      double noise = sqrt(w.noise[ch] * w.noise[ch] + y.noise[ch] * y.noise[ch]);
      double snr = (noise > 0.0) ? fabs(sw - sy) / noise : 0.0;
      if (snr > bestSnr) { bestSnr = snr; bestCh = ch; }

      char line[112];
      snprintf(line, sizeof(line), "  %-5s %9.1f %9.1f %8.1f %%  %7.2f %7.1f   %s",
               CH_NAME[ch], sw, sy, contrast * 100.0, noise, snr,
               snr >= SNR_GO ? "GO" : "no");
      out.println(line);
    }

    out.println("----------------------------------------------------------");
    if (w.saturated || y.saturated) {
      out.println("  WARNING: a series was saturated, this report is not trustworthy");
    }
    out.print("  best channel: ");
    out.print(bestCh >= 0 ? CH_NAME[bestCh] : "none");
    out.print("  SNR=");
    out.print(bestSnr, 1);
    out.print("  ->  ");
    out.println(bestSnr >= SNR_GO ? "GO: optical readout is viable" : "NO-GO: contrast insufficient");
    out.println("==========================================================");

    if (oledOk) {
      char l2[24];
      snprintf(l2, sizeof(l2), "%s SNR %.1f", bestCh >= 0 ? CH_NAME[bestCh] : "-", bestSnr);
      oledMessage(bestSnr >= SNR_GO ? "GO" : "NO-GO", l2);
    }
  }

  if (!anything) {
    out.println("[report] nothing to report yet, measure both targets first (w and y)");
  }
}

// ---------------------------------------------------------------------------
// Serial UI
// ---------------------------------------------------------------------------
static void printHelp() {
  out.println();
  out.println("  commands");
  out.println("    w   measure WHITE target (dial) under current light");
  out.println("    y   measure YELLOW target (needle) under current light");
  out.println("    i   toggle light source: white board LED / external blue LED");
  out.println("    g   cycle TCS34725 gain 1x / 4x / 16x / 60x");
  out.println("    r   report contrast and SNR");
  out.println("    l   toggle live readout on OLED and serial");
  out.println("    c   clear all results");
  out.println("    j   toggle JSON output for the lab software");
  out.println("    m   measure one point, the software supplies the label");
  out.println("    n   cycle samples per half series 10 / 25 / 50 / 100");
  out.println("    k   run the countdown on the display");
  out.println("    p   print status");
  out.println("    h   this help");
  out.println();
}

static void printBanner() {
  out.println();
  out.println("==========================================================");
  out.println("   HALO GAUGE PROBE");
  out.println("   stage 0+1  contrast and SNR characterization");
  out.println("   Heltec WiFi LoRa 32 V2 + TCS34725 + 2x ALS-PT19");
  out.println("==========================================================");
}

static void handleCommand(char c) {
  switch (c) {
    case 'w': runSeries(TGT_WHITE);  break;
    case 'm': runSeries(TGT_POINT);  break;
    case 'n':
      sampleCount = sampleCount == 10 ? 25 : sampleCount == 25 ? 50 : sampleCount == 50 ? 100 : 10;
      if (jsonOn) jsonAck("n");
      else { out.print("[samples] "); out.println(sampleCount); }
      break;
    case 'y': runSeries(TGT_YELLOW); break;
    case 'r': report(); break;
    case 'h': if (!jsonOn) printHelp(); break;
    case 'k':
      oledCountdown();
      if (jsonOn) jsonAck("k");
      break;
    case 'j':
      jsonOn = !jsonOn;
      if (jsonOn) jsonHello(); else out.println("[json] off");
      break;
    case 'p':
      if (jsonOn) jsonHello(); else { out.print("[status] light="); out.print(ILLUM_NAME[illum]); out.print(" gain="); out.println(GAIN_NAME[gainIndex]); }
      break;
    case 'i':
      illum = (illum == ILLUM_WHITE) ? ILLUM_BLUE : ILLUM_WHITE;
      if (jsonOn) jsonAck("i"); else { out.print("[light] "); out.println(ILLUM_NAME[illum]); }
      break;
    case 'g':
      gainIndex = (gainIndex + 1) % 4;
      if (tcsOk) tcs.setGain(GAIN_VALUE[gainIndex]);
      if (jsonOn) jsonAck("g"); else { out.print("[gain] "); out.println(GAIN_NAME[gainIndex]); }
      break;
    case 'l':
      liveOn = !liveOn;
      if (jsonOn) jsonAck("l"); else { out.print("[live] "); out.println(liveOn ? "on" : "off"); }
      break;
    case 'c':
      memset(results, 0, sizeof(results));
      if (jsonOn) jsonAck("c"); else out.println("[clear] all results cleared");
      break;
    case '\n':
    case '\r':
      break;
    default:
      if (jsonOn) { out.printf("{\"type\":\"error\",\"msg\":\"unknown command %c\"}\n", c); break; }
      out.print("[?] unknown command '");
      out.print(c);
      out.println("', press h for help");
      break;
  }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(PIN_TCS_LED,  OUTPUT);
  pinMode(PIN_BLUE_LED, OUTPUT);
  lightsOff();

  pinMode(PIN_VEXT, OUTPUT);
  digitalWrite(PIN_VEXT, LOW);   // power the OLED
  delay(50);

  analogSetPinAttenuation(PIN_PT19_A, ADC_11db);
  analogSetPinAttenuation(PIN_PT19_B, ADC_11db);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(400000);

  printBanner();

  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  out.print("[oled] ");
  out.println(oledOk ? "ok" : "not found, continuing without display");
  if (oledOk) {
    oled.setTextColor(SSD1306_WHITE);
    oledMessage("BOOT", "probing sensors");
  }

  tcsOk = tcs.begin();
  if (tcsOk) {
    tcs.setGain(GAIN_VALUE[gainIndex]);
    out.print("[tcs]  ok, integration 154 ms, gain ");
    out.println(GAIN_NAME[gainIndex]);
  } else {
    out.println("[tcs]  not found, running with the phototransistors only (PT-A on 36, PT-B on 37)");
  }

  if (WIFI_SSID[0]) {
    oledMessage("WIFI", "connecting");
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 12000) delay(200);
    if (WiFi.status() == WL_CONNECTED) {
      ArduinoOTA.setHostname("halo-probe");
      ArduinoOTA.onStart([]() {
        if (oledOk) { oled.clearDisplay(); centeredText("UPDATING", 1, 20); oled.display(); }
      });
      ArduinoOTA.onProgress([](unsigned int done, unsigned int total) {
        if (!oledOk) return;
        oled.clearDisplay();
        centeredText("UPDATING", 1, 16);
        int w = (int)((done * 120ULL) / (total ? total : 1));
        oled.drawRect(2, 34, 124, 10, SSD1306_WHITE);
        oled.fillRect(4, 36, w, 6, SSD1306_WHITE);
        oled.display();
      });
      ArduinoOTA.onEnd([]() {
        if (oledOk) { oled.clearDisplay(); centeredText("REBOOTING", 1, 28); oled.display(); }
      });
      ArduinoOTA.begin();
      netServer.begin();
      netServer.setNoDelay(true);
      netUp = true;
      out.print("[wifi] ");
      out.print(WiFi.localIP());
      out.print(" port ");
      out.println(NET_PORT);
      char ip[24];
      snprintf(ip, sizeof(ip), "%s", WiFi.localIP().toString().c_str());
      oledMessage("WIFI OK", ip);
      delay(1200);
    } else {
      out.println("[wifi] no connection, USB only");
      oledMessage("NO WIFI", "USB only");
      delay(900);
    }
  }

  oledArming();

  memset(results, 0, sizeof(results));
  printHelp();
  out.println("[ready] place the sensor over the WHITE target and press w");
}

// ---------------------------------------------------------------------------
// Loop
// ---------------------------------------------------------------------------
void loop() {
  if (netUp) {
    ArduinoOTA.handle();
    WiFiClient incoming = netServer.available();
    if (incoming) {
      if (out.client && out.client.connected()) out.client.stop();
      out.client = incoming;
      out.client.setNoDelay(true);
      if (jsonOn) jsonHello();
    }
  }

  while (Serial.available()) {
    handleCommand((char)Serial.read());
  }
  while (out.client && out.client.available()) {
    handleCommand((char)out.client.read());
  }

  if (liveOn && millis() - lastLive > 400) {
    lastLive = millis();
    double s[CH_COUNT];
    bool sat = readSample(s);
    oledLive(s, sat);
    if (jsonOn) jsonLive(s, sat);
  }
}
