import { api } from "../api.js";
import { state, setZone, refreshZones, go } from "../app.js";
import { bindReset, resetButton } from "../reset.js";
import { t, getLang } from "../i18n.js";
import { badge, esc, fmt, fmtTime, options, toast } from "../ui.js";

const SLIDERS = [
  ["vwc_upper", "VWC upper %", 2, 50, 0.1, 18], ["vwc_lower", "VWC lower %", 2, 50, 0.1, 16],
  ["matric_kpa", "Tension kPa", 0, 120, 1, 22], ["soil_temp_c", "Soil temp °C", 5, 45, 0.1, 22],
  ["ece", "ECe dS/m (25 °C)", 0.2, 8, 0.05, 1.2], ["ph", "pH", 4.5, 9.5, 0.1, 7.2],
  ["n", "N mg/kg", 0, 150, 1, 45], ["p", "P mg/kg", 0, 80, 1, 20], ["k", "K mg/kg", 0, 400, 1, 140],
  ["orp_mv", "ORP mV", -100, 700, 5, 380], ["o2_pct", "Soil O₂ %", 0, 21, 0.1, 16],
  ["air_temp_c", "Air °C", -2, 48, 0.1, 27], ["rh_pct", "RH %", 5, 100, 1, 55],
  ["par", "PAR µmol/m²/s", 0, 2200, 10, 1200], ["leaf_wetness_pct", "Leaf wetness %", 0, 100, 1, 0], ["wind_ms", "Wind m/s", 0, 20, 0.1, 2],
];

let lastPush = null;

export async function renderSimulator(el, ctx) {
  const lang = getLang();
  const [cases, devices] = await Promise.all([api("/simulator/cases"), api("/devices")]);
  if (!ctx.isCurrent()) return;
  const sandbox = state.zones.find((z) => z.is_sandbox);
  const endpoint = `${location.origin}/api/v1/telemetry/ingest`;
  el.innerHTML = `
  <div class="section-title"><h2>${esc(t("sim_title"))}</h2></div>
  <p class="muted">${esc(t("sim_intro"))}</p>
  <div class="card row">
    <label class="field" style="min-width:240px"><span class="lbl">${esc(t("target_zone"))}</span>
      <select id="simZone">${options(state.zones.map((z) => ({ value: z.id, label: z.name })), state.zoneId)}</select></label>
    ${resetButton()}
    <span class="note" style="flex:1">${esc(t("sandbox_warn"))}${sandbox && sandbox.id !== state.zoneId ? ` <a href="#" id="useSandbox">→ ${esc(sandbox.name)}</a>` : ""}</span>
  </div>

  <div class="grid g2" style="margin-top:16px">
    <section class="card">
      <h3>${esc(t("random_gen"))}</h3>
      <div class="row">
        <label class="field" style="flex:1;min-width:200px"><span class="lbl">${esc(t("mode"))}</span>
          <select id="mode">${Object.entries(cases.modes).map(([k, v]) => `<option value="${k}">${esc(v[lang])}</option>`).join("")}</select></label>
        <button class="btn primary big" id="randomBtn" style="align-self:end">⚡ ${esc(t("random_gen"))}</button>
      </div>
      <div id="result" style="margin-top:14px">${lastPush ? lastPush : `<p class="muted">${esc(t("result"))}: —</p>`}</div>
    </section>
    <section class="card">
      <h3>${esc(t("cases"))}</h3>
      <div class="grid g2">${cases.cases.map((c) => `<button class="case-btn" data-case="${c.id}">
        <b>${c.id} · ${esc(lang === "ar" ? c.title_ar : c.title_en)}</b>
        <small class="muted">ECe ${c.sensors.ece} · pH ${c.sensors.ph} · VWC ${c.sensors.vwc_upper}% · ${c.sensors.air_temp_c} °C / ${c.sensors.rh_pct}%</small>
      </button>`).join("")}</div>
    </section>
  </div>

  <section class="card" style="margin-top:16px">
    <h3>${esc(t("manual"))}</h3>
    <form id="manual">
      <div class="form-grid">${SLIDERS.map(([k, label, min, max, step, def]) => `<div class="slider"><span class="lbl">${esc(label)}</span>
        <input type="range" name="${k}" min="${min}" max="${max}" step="${step}" value="${def}"><output>${def}</output></div>`).join("")}</div>
      <hr>
      <div class="form-grid">
        <label class="field"><span class="lbl">${esc(t("texture"))}</span><select name="texture_class">${options(state.meta.textures.map((x) => ({ value: x.id, label: x[lang] })), "sandy_loam")}</select></label>
        <label class="field"><span class="lbl">CEC</span><input name="cec_meq" type="number" step="any" value="12"></label>
        <label class="field"><span class="lbl">SOM %</span><input name="som_pct" type="number" step="any" value="1.5"></label>
        <label class="field"><span class="lbl">CaCO3 %</span><input name="caco3_pct" type="number" step="any" value="6"></label>
        <label class="field"><span class="lbl">ESP %</span><input name="esp_pct" type="number" step="any" value="6"></label>
        <label class="field"><span class="lbl">ECw dS/m</span><input name="water_ec_w" type="number" step="any" value="0.8"></label>
        <label class="field"><span class="lbl">${esc(t("region"))}</span><select name="region">${options(state.meta.regions.map((x) => ({ value: x.id, label: x[lang] })), "ismailia")}</select></label>
        <label class="field"><span class="lbl">${esc(t("season"))}</span><select name="season">${options(state.meta.seasons.map((x) => ({ value: x.id, label: x[lang] })), "shetwi")}</select></label>
        <label class="field"><span class="lbl">${esc(t("irrigation"))}</span><select name="irrigation_type">${options(["drip", "greenhouse", "pivot"].map((v) => ({ value: v, label: t(v) })), "drip")}</select></label>
      </div>
      <div class="row" style="margin-top:12px"><button class="btn primary" type="submit">${esc(t("push_manual"))}</button></div>
    </form>
  </section>

  <section class="card" style="margin-top:16px">
    <h3>${esc(t("devices"))}</h3>
    <p>${esc(t("endpoint"))}: <code>POST ${esc(endpoint)}</code> · header <code>X-Device-Token: &lt;token&gt;</code></p>
    <div class="table-wrap"><table><thead><tr><th>Device</th><th>${esc(t("zone"))}</th><th>${esc(t("device_status"))}</th><th class="num">${esc(t("battery"))}</th><th class="num">${esc(t("rssi"))}</th><th>${esc(t("last_reading"))}</th><th></th></tr></thead>
      <tbody>${devices.devices.map((d) => `<tr><td><code>${esc(d.device_id)}</code></td><td>${esc(state.zones.find((z) => z.id === d.zone_id)?.name || d.zone_id)}</td>
        <td>${badge(d.status === "online" ? "green" : d.status === "fault" ? "red" : "grey", d.status)}</td><td class="num">${fmt(d.battery_v, 2)} V</td><td class="num">${fmt(d.rssi_dbm, 0)}</td>
        <td>${esc(fmtTime(d.last_seen_at))}</td><td><button class="btn small" data-rotate="${esc(d.device_id)}">${esc(t("rotate"))}</button></td></tr>`).join("")}</tbody></table></div>
    <form id="newDev" class="row" style="margin-top:12px">
      <input name="device_id" placeholder="EGY-NODE-002" required style="max-width:220px">
      <button class="btn" type="submit">${esc(t("new_device"))}</button>
    </form>
    <div id="tokenOut" style="margin-top:10px"></div>
    <p class="note">${lang === "ar" ? "مفتاح الجهاز الأولي محفوظ في data/seed_device_token.txt." : "The seeded device's first token is saved in data/seed_device_token.txt."}</p>
  </section>`;

  bindReset(el, () => { lastPush = null; renderSimulator(el, ctx); });
  const zoneSel = el.querySelector("#simZone");
  zoneSel.addEventListener("change", () => { setZone(zoneSel.value); });
  el.querySelector("#useSandbox")?.addEventListener("click", (e) => { e.preventDefault(); setZone(sandbox.id); renderSimulator(el, ctx); });
  el.querySelectorAll(".slider input").forEach((inp) => inp.addEventListener("input", () => { inp.nextElementSibling.textContent = inp.value; }));

  const showResult = async (summary, extraHtml = "") => {
    await refreshZones();
    let top = "";
    try {
      const m = await api("/optimize/match-crops", { method: "POST", body: { zone_id: state.zoneId } });
      top = m.ranking.slice(0, 3).map((r) => `${lang === "ar" ? r.name_ar : r.name_en} <b>${fmt(r.score, 1)}%</b>`).join(" · ");
    } catch { /* no reading */ }
    lastPush = `<div class="alert ${summary.status}">
      <div class="row"><span class="light ${summary.status}"></span><b>${esc(t("status_" + summary.status))}</b> · ${esc(t("shi"))} <b>${fmt(summary.shi?.index, 0)}</b> · ${summary.alerts} alerts</div>
      <div style="margin-top:6px">${esc(t("top_matches"))}: ${top || "—"}</div>${extraHtml}
      <div class="row" style="margin-top:8px"><a class="btn small" href="#/dashboard">${esc(t("nav_dashboard"))}</a><a class="btn small" href="#/crops">${esc(t("nav_crops"))}</a><a class="btn small" href="#/prescription">${esc(t("nav_rx"))}</a></div>
    </div>`;
    el.querySelector("#result").innerHTML = lastPush;
  };

  el.querySelector("#randomBtn").addEventListener("click", async (e) => {
    const btn = e.currentTarget; btn.disabled = true;
    try {
      const r = await api("/simulator/random", { method: "POST", body: { zone_id: state.zoneId, mode: el.querySelector("#mode").value } });
      const g = r.generated;
      await showResult(r, `<div class="note" style="margin-top:6px">${esc(cases.modes[r.mode_effective]?.[lang] || r.mode_effective)} · ${esc(g.lab.texture_class)} · ${esc(g.context.region)} · ${esc(g.context.season)} · ECe ${g.sensors.ece} · pH ${g.sensors.ph} · VWC ${g.sensors.vwc_upper}% · ORP ${g.sensors.orp_mv} · ${g.sensors.air_temp_c} °C/${g.sensors.rh_pct}%</div>`);
    } catch (err) { toast(err.message); } finally { btn.disabled = false; }
  });

  el.querySelectorAll("[data-case]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    try {
      const r = await api("/simulator/push", { method: "POST", body: { zone_id: state.zoneId, case_id: b.dataset.case } });
      const c = cases.cases.find((x) => x.id === b.dataset.case);
      await showResult(r, `<div class="note" style="margin-top:6px"><b>${esc(t("expected"))} (${c.id}):</b> ${esc(c.expected_text_en)}</div>`);
      el.querySelector("#result").scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (err) { toast(err.message); } finally { b.disabled = false; }
  }));

  el.querySelector("#manual").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.target).entries());
    const sensors = {};
    SLIDERS.forEach(([k]) => { sensors[k] = Number(fd[k]); });
    const lab = { texture_class: fd.texture_class };
    ["cec_meq", "som_pct", "caco3_pct", "esp_pct", "water_ec_w"].forEach((k) => { if (fd[k] !== "") lab[k] = Number(fd[k]); });
    try {
      const r = await api("/simulator/push", { method: "POST", body: { zone_id: state.zoneId, sensors, lab, context: { region: fd.region, season: fd.season, irrigation_type: fd.irrigation_type } } });
      await showResult(r);
      el.querySelector("#result").scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (err) { toast(err.message); }
  });

  el.querySelectorAll("[data-rotate]").forEach((b) => b.addEventListener("click", async () => {
    const r = await api(`/devices/${encodeURIComponent(b.dataset.rotate)}/rotate-token`, { method: "POST" });
    el.querySelector("#tokenOut").innerHTML = `<p class="note">${esc(t("token_once"))}</p><div class="token-box">${esc(r.device_id)} → ${esc(r.token)}</div>`;
  }));
  el.querySelector("#newDev").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const r = await api("/devices", { method: "POST", body: { zone_id: state.zoneId, device_id: new FormData(e.target).get("device_id") } });
      el.querySelector("#tokenOut").innerHTML = `<p class="note">${esc(t("token_once"))}</p><div class="token-box">${esc(r.device_id)} → ${esc(r.token)}</div>`;
    } catch (err) { toast(err.message); }
  });
}
