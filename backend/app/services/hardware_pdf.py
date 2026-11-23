"""Hardware Components (BOM), Wiring & Ready-to-Flash Firmware Code PDF.

Spec Sections 6.3 and 9 (deliverable 7). Generated with ReportLab; the
firmware listing is read from firmware/esp32_soil_node/ and pre-filled with the
device ID and live ingestion URL.
"""

from __future__ import annotations

import io
import os
from xml.sax.saxutils import escape
import re
from datetime import datetime, timezone
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from ..knowledge.crops import CROPS

ROOT = Path(__file__).resolve().parents[3]
FW_DIR = ROOT / "firmware" / "esp32_soil_node"
DOCS_DIR = ROOT / "docs"

GREEN = colors.HexColor("#1f5a3a")
LIGHT = colors.HexColor("#eef3ea")
AMBER = colors.HexColor("#a8641c")


def _fonts() -> tuple[str, str, str]:
    """Register TTF fonts with wide glyph coverage when available (µ, Ω, →, ≈ …)."""
    candidates = [
        ("SoilSans", ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]),
        ("SoilSans-Bold", ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]),
        ("SoilMono", ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]),
    ]
    found = {}
    for name, paths in candidates:
        for p in paths:
            if os.path.exists(p):
                try:
                    pdfmetrics.registerFont(TTFont(name, p))
                    found[name] = True
                    break
                except Exception:  # noqa: BLE001
                    pass
    sans = "SoilSans" if found.get("SoilSans") else "Helvetica"
    bold = "SoilSans-Bold" if found.get("SoilSans-Bold") else "Helvetica-Bold"
    mono = "SoilMono" if found.get("SoilMono") else "Courier"
    return sans, bold, mono


def _ascii_safe(text: str, ttf: bool) -> str:
    if ttf:
        return text
    repl = {"→": "->", "≈": "~", "Ω": "Ohm", "—": "-", "–": "-", "…": "...", "≥": ">=", "≤": "<=", "×": "x", "³": "3"}
    return "".join(repl.get(ch, ch if ord(ch) < 256 else "?") for ch in text)


def _styles(sans, bold, mono):
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=ss["Title"], fontName=bold, fontSize=20, leading=24, textColor=GREEN, alignment=TA_LEFT),
        "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName=bold, fontSize=14, leading=18, textColor=GREEN, spaceBefore=10, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName=bold, fontSize=11.5, leading=15, textColor=GREEN, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("b", parent=ss["BodyText"], fontName=sans, fontSize=9, leading=12.5),
        "small": ParagraphStyle("s", parent=ss["BodyText"], fontName=sans, fontSize=7.6, leading=10),
        "cell": ParagraphStyle("c", parent=ss["BodyText"], fontName=sans, fontSize=7.6, leading=9.6),
        "cellb": ParagraphStyle("cb", parent=ss["BodyText"], fontName=bold, fontSize=7.6, leading=9.6),
        "note": ParagraphStyle("n", parent=ss["BodyText"], fontName=sans, fontSize=8.4, leading=11.5, textColor=AMBER),
        "code": ParagraphStyle("code", fontName=mono, fontSize=6.4, leading=7.6),
    }


def _table(rows, widths, st, header=True):
    data = [[Paragraph(escape(str(c)), st["cellb"] if (header and i == 0) else st["cell"]) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d3c4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), LIGHT)]
    t.setStyle(TableStyle(style))
    return t


BOM = [
    # (component, example part, qty, supply, interface, purpose)
    ("Microcontroller", "ESP32-S3-DevKitC-1 (N8R8) — or ESP32-DevKitC (classic)", "1", "5 V in / 3.3 V logic", "—", "Polls sensors, ATC, JSON build, Wi-Fi uplink, deep sleep"),
    ("RS485 transceiver", "SP3485 / MAX3485 module (3.3 V; MAX485 only with level shifting)", "1", "3.3 V", "UART1 + DE/RE", "Modbus RTU master for both soil probes"),
    ("Upper soil probe — Sensor A", "RS485 7-in-1 probe: VWC / Temp / EC / pH / N-P-K, titanium or 316L electrodes, IP68", "1", "12 V (5–30 V)", "RS485 Modbus addr 1", "Feeder-root zone (10–25 cm): irrigation trigger, salinity, pH, NPK"),
    ("Lower soil probe — Sensor B", "RS485 3-in-1 probe: VWC / Temp / EC, 316L, IP68", "1", "12 V (5–30 V)", "RS485 Modbus addr 2", "Bottom of root zone (20–60 cm): deep-percolation & leaching check"),
    ("Granular-matrix tensiometer", "Watermark 200SS + voltage interface (0–2.8 V ≈ 0–239 kPa)", "1", "3.3–5 V", "Analog → ADS1115 A1", "Soil matric potential (kPa), texture-independent"),
    ("ORP probe + transmitter", "Platinum ORP electrode + isolated ORP transmitter (0–2 V)", "1", "5 V / 12 V", "Analog → ADS1115 A0", "Redox: waterlogging / hypoxia (< +200 mV)"),
    ("16-bit ADC", "ADS1115 breakout (0x48 main, 0x49 auxiliary)", "2", "3.3 V", "I2C", "High-resolution analog front-end"),
    ("Air temperature / RH", "SHT31-D in a radiation shield (BME280 alternative)", "1", "3.3 V", "I2C 0x44", "VPD, dew point, chilling hours"),
    ("PAR quantum sensor", "Analog quantum sensor 0–2.5 V (0–2500 µmol/m²/s)", "1", "5–24 V", "Analog → ADS1115 A2", "Light / ET driver"),
    ("Leaf-wetness sensor (optional)", "Dielectric leaf-wetness sensor, analog", "0–1", "3.3–5 V", "Analog → ADS1115 A3", "Fungal infection windows"),
    ("Soil O2 sensor (optional)", "Galvanic soil-oxygen cell (mV output)", "0–1", "self-powered", "Analog → ADS1115#2 A0", "Root oxygen in heavy clays / substrates"),
    ("Rain gauge (optional)", "Tipping bucket, reed switch, 0.2794 mm/tip", "0–1", "—", "GPIO (RTC wake)", "Rain-aware advisories"),
    ("Anemometer (optional)", "Cup anemometer, reed pulse, 2.4 km/h per Hz", "0–1", "—", "GPIO interrupt", "Khamsin wind detection"),
    ("12 V step-up converter", "XL6009 / MT3608 boost module set to 12.0 V", "1", "in 10–14.6 V", "—", "Stable 12 V for RS485 probes"),
    ("Probe power switch", "Logic-level N-MOSFET (AO3400 / IRLZ44N) + 10 kΩ gate pull-down", "1", "—", "GPIO", "Powers probes only while reading (energy saving) — not an actuator"),
    ("5 V buck converter", "MP1584 / LM2596 module set to 5.0 V", "1", "in 12.8 V", "—", "Feeds the ESP32 board"),
    ("Battery", "LiFePO4 12.8 V, 6–12 Ah (survives 50 °C enclosure heat)", "1", "12.8 V", "—", "Night / cloudy-day autonomy"),
    ("Solar panel", "12 V nominal, 20–30 W (Vmp ≈ 18 V)", "1", "—", "—", "Energy harvesting"),
    ("MPPT charger", "MPPT controller with LiFePO4 14.4 V profile", "1", "panel → battery", "—", "Safe LiFePO4 charging"),
    ("Solar current monitor", "INA219 breakout", "1", "3.3 V", "I2C 0x40", "solar_charge_ma in hardware_health"),
    ("Battery sense divider", "100 kΩ + 22 kΩ 1 % resistors + 100 nF", "1 set", "—", "ADC", "battery_v telemetry"),
    ("RS485 protection", "120 Ω termination ×2, SM712 TVS diode", "1 set", "—", "—", "Line termination & surge protection"),
    ("Enclosure", "IP67 UV-stabilised ABS/PC box ≈ 200×150×100 mm + desiccant", "1", "—", "—", "Weather protection"),
    ("Cable glands", "Waterproof PG7 / PG9 nylon glands", "6–8", "—", "—", "Sealed cable entries"),
    ("Cable", "Shielded twisted-pair RS485 cable (4-core)", "10–20 m", "—", "—", "Probe runs to the enclosure"),
    ("Mounting", "Galvanised / stainless mast + radiation shield", "1", "—", "—", "Canopy-height sensor mounting"),
]

PINS = [
    ("RS485 RO → ESP32 RX", "GPIO 18", "GPIO 16", "UART1 RX (Modbus)"),
    ("RS485 DI ← ESP32 TX", "GPIO 17", "GPIO 17", "UART1 TX (Modbus)"),
    ("RS485 DE + RE (tied)", "GPIO 16", "GPIO 4", "Driver enable (HIGH = transmit)"),
    ("I2C SDA", "GPIO 8", "GPIO 21", "SHT31, ADS1115 ×2, INA219 (4.7 kΩ pull-ups)"),
    ("I2C SCL", "GPIO 9", "GPIO 22", "—"),
    ("Rain gauge reed", "GPIO 4 (RTC)", "GPIO 27 (RTC)", "Other side to GND; wakes node from deep sleep"),
    ("Anemometer reed", "GPIO 5", "GPIO 26", "Other side to GND; internal pull-up"),
    ("Probe power MOSFET gate", "GPIO 15", "GPIO 25", "HIGH = 12 V boost to probes ON"),
    ("Battery divider midpoint", "GPIO 1 (ADC1_CH0)", "GPIO 34 (ADC1)", "Vbatt = Vadc × 5.545"),
    ("ADS1115 #1 A0 / A1 / A2 / A3", "I2C 0x48", "I2C 0x48", "ORP / tensiometer / PAR / leaf wetness"),
    ("ADS1115 #2 A0", "I2C 0x49 (ADDR→VDD)", "I2C 0x49", "Soil O2 (optional)"),
    ("Probe A / B RS485 A+, B−", "bus", "bus", "Daisy-chained; 120 Ω at both bus ends"),
    ("Probe A / B power (brown / black)", "12 V boost out / GND", "12 V boost out / GND", "Switched by the MOSFET"),
]

POWER = [
    ("Solar panel 12 V / 20–30 W", "MPPT charger PV input", "Reverse-polarity protected"),
    ("MPPT battery output", "LiFePO4 12.8 V pack", "14.4 V absorb / 13.6 V float"),
    ("LiFePO4 12.8 V", "5 V buck → ESP32 5V pin", "≈ 40 µA deep sleep, ≈ 150 mA during Wi-Fi uplink"),
    ("LiFePO4 12.8 V", "MOSFET → 12 V boost → probes A & B", "Energised ~8 s per cycle only"),
    ("ESP32 3V3", "SHT31, ADS1115 ×2, INA219, SP3485, transmitters (low side)", "Common GND with every module"),
    ("LiFePO4 + → 100k/22k divider → GPIO", "battery_v telemetry", "Fault flag battery_low below 12.0 V"),
]


def _power_diagram(sans, bold) -> Drawing:
    d = Drawing(520, 190)

    def box(x, y, w, h, label, sub="", fill=LIGHT):
        d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=GREEN, strokeWidth=1, rx=4, ry=4))
        d.add(String(x + w / 2, y + h / 2 + (3 if sub else -3), label, fontName=bold, fontSize=7.5, textAnchor="middle"))
        if sub:
            d.add(String(x + w / 2, y + h / 2 - 8, sub, fontName=sans, fontSize=6.5, textAnchor="middle"))

    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=GREEN, strokeWidth=1.2))
        d.add(Rect(x2 - 2, y2 - 2, 4, 4, fillColor=GREEN, strokeColor=GREEN))

    box(5, 140, 90, 40, "Solar panel", "12 V / 20–30 W")
    box(120, 140, 90, 40, "MPPT charger", "LiFePO4 profile")
    box(235, 140, 90, 40, "LiFePO4", "12.8 V 6–12 Ah")
    box(360, 160, 150, 26, "5 V buck → ESP32-S3", "")
    box(360, 120, 150, 26, "MOSFET → 12 V boost", "")
    box(360, 60, 150, 44, "RS485 probes A & B", "Modbus addr 1 / 2")
    box(120, 60, 120, 44, "ESP32-S3", "Wi-Fi uplink · deep sleep")
    box(255, 60, 90, 44, "SP3485", "RS485 ↔ UART1")
    box(5, 5, 330, 40, "I2C bus: SHT31 · ADS1115 ×2 (ORP, tensiometer, PAR, leaf wet, O2) · INA219", "")
    box(360, 5, 150, 40, "GPIO: rain (RTC wake) · wind", "")
    arrow(95, 160, 120, 160)
    arrow(210, 160, 235, 160)
    arrow(325, 165, 360, 172)
    arrow(325, 152, 360, 133)
    arrow(435, 120, 435, 104)
    arrow(240, 82, 255, 82)
    arrow(345, 82, 360, 82)
    arrow(180, 60, 180, 45)
    arrow(240, 70, 360, 30)
    d.add(String(5, 115, "No relays · no valves · no pumps — sensors-only, advisory-only node", fontName=bold, fontSize=7.5, fillColor=AMBER))
    return d


def _prefill(text: str, device_id: str, ingest_url: str, upper: int, lower: int) -> str:
    text = re.sub(r'#define DEVICE_ID\s+"[^"]*"', f'#define DEVICE_ID        "{device_id}"', text)
    text = re.sub(r'#define INGEST_URL\s+"[^"]*"', f'#define INGEST_URL       "{ingest_url}"', text)
    text = re.sub(r"#define UPPER_DEPTH_CM\s+\d+", f"#define UPPER_DEPTH_CM       {upper}", text)
    text = re.sub(r"#define LOWER_DEPTH_CM\s+\d+", f"#define LOWER_DEPTH_CM       {lower}", text)
    return text


def _wrap_code(text: str, width: int = 128) -> str:
    out = []
    for line in text.splitlines():
        while len(line) > width:
            out.append(line[:width])
            line = "    " + line[width:]
        out.append(line)
    return "\n".join(out)


def build_pdf(*, device_id: str = "EGY-NODE-001",
              ingest_url: str = "http://<YOUR-PC-LAN-IP>:8000/api/v1/telemetry/ingest",
              zone_name: str | None = None, crop: dict | None = None) -> bytes:
    sans, bold, mono = _fonts()
    ttf = sans != "Helvetica"
    st = _styles(sans, bold, mono)
    upper = crop["upper_depth_cm"] if crop else 15
    lower = crop["lower_depth_cm"] if crop else 35
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                            title="Hardware Components (BOM), Wiring & Firmware Code", author="Smart Soil Advisory Platform")
    W = A4[0] - 32 * mm
    S = lambda s: _ascii_safe(s, ttf)  # noqa: E731
    story = []

    def P(text, style="body"):
        story.append(Paragraph(S(text), st[style]))

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont(sans, 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(16 * mm, 9 * mm, S("Smart Soil Node — Hardware BOM, Wiring & Firmware (sensors-only, advisory-only)"))
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"Page {_doc.page}")
        canvas.restoreState()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    P("Hardware Components (BOM), Wiring &amp; Ready-to-Flash Firmware Code", "title")
    P("Sensors-only smart soil node for the Advisory Smart Soil Platform (Egypt) — spec Sections 6.1–6.4, 9", "body")
    story.append(Spacer(1, 6))
    story.append(_table([
        ["Field", "Value"],
        ["Device ID", device_id],
        ["Ingestion endpoint", f"POST {ingest_url}  (header X-Device-Token)"],
        ["Zone", zone_name or "—"],
        ["Crop / probe depths", f"{crop['name_en'] if crop else 'Not set'} — Sensor A {upper} cm, Sensor B {lower} cm (Table 4.1)"],
        ["Generated", now],
    ], [38 * mm, W - 38 * mm], st))
    story.append(Spacer(1, 6))
    P("<b>Scope.</b> This node only <i>reads</i> soil and microclimate sensors and sends one-way telemetry. It contains no "
      "solenoid valves, relay boards, fertigation pumps or downlink command handling. Every irrigation, fertilizer and soil "
      "amendment decision is shown to the farmer as advice in the web application.", "body")

    P("1. System overview", "h1")
    story.append(_power_diagram(sans, bold))
    P("Each wake cycle (default every 10 min, spec 5–15 min): power the probes → poll Sensor A and Sensor B over RS485 "
      "(median of 5 samples) → read ADS1115 / SHT31 / INA219 / wind / rain → apply ATC (EC25 = EC / (1 + 0.019 (T − 25))) → "
      "build the Section 6.2 JSON → flush the LittleFS offline buffer → POST → deep sleep.", "body")

    P("2. Bill of Materials (sensors only)", "h1")
    rows = [["#", "Component", "Example part / spec", "Qty", "Supply", "Interface", "Purpose"]]
    for i, b in enumerate(BOM, 1):
        rows.append([str(i), *(S(x) for x in b)])
    story.append(_table(rows, [7 * mm, 30 * mm, 50 * mm, 10 * mm, 20 * mm, 25 * mm, W - 142 * mm], st))
    P("Verify every probe's Modbus register map, supply range and electrode material against its datasheet before ordering. "
      "Low-cost RS485 NPK probes estimate N-P-K indirectly — the web app marks them “Unverified Estimate” until a seasonal "
      "lab test calibrates them (corrected = raw × gain + offset).", "note")

    story.append(PageBreak())
    P("3. Pin-by-pin wiring", "h1")
    story.append(_table([["Signal", "ESP32-S3-DevKitC-1", "ESP32 classic", "Notes"], *[[S(x) for x in r] for r in PINS]],
                        [52 * mm, 34 * mm, 30 * mm, W - 116 * mm], st))
    P("4. Power distribution", "h2")
    story.append(_table([["Source", "Feeds", "Notes"], *[[S(x) for x in r] for r in POWER]], [52 * mm, 62 * mm, W - 114 * mm], st))

    P("5. Field installation — dual-depth burial geometry", "h1")
    P("Sensor A sits in the active feeder-root zone and drives irrigation advice; Sensor B sits at the bottom of the root "
      "zone — if B's moisture jumps after watering, the farmer is over-irrigating and leaching nitrate (spec Section 3). "
      "Depths per crop (spec Table 4.1):", "body")
    rows = [["Crop", "Sensor A (upper)", "Sensor B (lower)", "Moisture / tension target", "ECe limit"]]
    for c in CROPS:
        rows.append([S(c["name_en"]), f"{c['upper_depth_cm']} cm", f"{c['lower_depth_cm']} cm",
                     f"{c['awc_min']}–{c['awc_max']}% AWC ({c['tension_min']}–{c['tension_max']} kPa)", f"≤ {c['ec_limit']} dS/m"])
    story.append(_table([[S(x) for x in r] for r in rows], [38 * mm, 26 * mm, 26 * mm, 60 * mm, W - 150 * mm], st))
    for step in [
        "Auger a vertical hole to the Sensor B depth within the wetted bulb, 10–15 cm from a dripper, between two plants.",
        "Install Sensor B horizontally into undisturbed side-wall soil at its depth; backfill and tamp in layers. Repeat for Sensor A.",
        "Set Modbus addresses before burial: upper probe = 1, lower probe = 2 (vendor tool or Modbus write).",
        "Install the Watermark tensiometer and ORP electrode at the Sensor A depth after soaking them (tensiometer: wet/dry cycle).",
        "Leave a drip loop on every cable before the enclosure; seal glands; mount the SHT31 shield and PAR sensor at canopy height.",
        "Select the soil texture and enter the lab profile in the web app — texture sets FC/PWP for AWC (spec Section 6.4).",
    ]:
        P("• " + step, "body")

    P("6. Flashing &amp; calibration", "h1")
    for step in [
        "Install VS Code + the PlatformIO extension (or <font face='%s'>pip install platformio</font>)." % mono,
        "Open <font face='%s'>firmware/esp32_soil_node</font>; edit <font face='%s'>include/config.h</font>: Wi-Fi SSID/password, API_TOKEN (from the web app's Simulator Lab → Devices, or data/seed_device_token.txt), INGEST_URL." % (mono, mono),
        "Run the web app on the LAN: <font face='%s'>python run.py --host 0.0.0.0</font>, and use your PC's LAN IP in INGEST_URL." % mono,
        "Build and flash: <font face='%s'>pio run -e esp32-s3 -t upload</font> (use <font face='%s'>-e esp32-classic</font> for a classic ESP32). Monitor: <font face='%s'>pio device monitor</font>." % (mono, mono, mono),
        "Watch the serial log for the JSON packet and “POST -&gt; 200”. The dashboard updates live (SSE).",
        "Calibrate: EC probe in 1.413 mS/cm standard; pH probe (if supported) in pH 4/7 buffers; ORP transmitter in a ±225/475 mV ORP standard (set ORP_MV_PER_V / ORP_MV_OFFSET); O2 cell in free air (O2_MV_AT_AIR).",
        "Each season, enter lab N-P-K in the web app's Lab page — the app computes gain/offset and flags readings “Lab-Calibrated”.",
    ]:
        P("• " + step, "body")
    P("Test without hardware (PowerShell):", "h2")
    story.append(Preformatted(
        "Invoke-RestMethod -Method Post -Uri " + ingest_url + " `\n"
        "  -Headers @{ 'X-Device-Token' = '<token>' } -ContentType 'application/json' `\n"
        "  -Body (Get-Content sample_payload.json -Raw)", st["code"]))

    story.append(PageBreak())
    P("7. Firmware source code (ready to flash)", "h1")
    P("Also saved in <font face='%s'>firmware/esp32_soil_node/</font>. Pre-filled with device ID <b>%s</b>, the ingestion URL and the probe depths above." % (mono, device_id), "body")
    for rel in ["platformio.ini", "include/config.h", "src/main.cpp"]:
        path = FW_DIR / rel
        text = path.read_text(encoding="utf-8") if path.exists() else f"// {rel} not found"
        if rel.endswith("config.h"):
            text = _prefill(text, device_id, ingest_url, upper, lower)
        story.append(KeepTogether([Paragraph(S(rel), st["h2"])]))
        story.append(Preformatted(S(_wrap_code(text)), st["code"]))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def write_default_pdf() -> str:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "Hardware_BOM_Wiring_Firmware.pdf"
    out.write_bytes(build_pdf())
    return str(out)
