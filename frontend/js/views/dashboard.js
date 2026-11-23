import { api } from "../api.js";
import { state, refreshZones, render } from "../app.js";
import { bindReset, resetButton } from "../reset.js";
import { L, t, getLang } from "../i18n.js";
import { alertCard, badge, bandSev, esc, fmt, fmtTime, gaugeSVG, metric, options, sparkSVG, statusWord, toast } from "../ui.js";

export async function renderDashboard(el, ctx) {
  const d = await api(`/zones/${state.zoneId}/dashboard?history=60`);
  if (!ctx.isCurrent()) return;
  const meta = state.meta;
  const z = d.zone;
  const crop = d.crop;
  const settings = zoneSettings(z, meta);

  if (!d.latest) {
    el.innerHTML = `<div class="card empty"><h2>${esc(t("no_readings"))}</h2><p>${esc(t("no_readings_hint"))}</p>
      <a class="btn primary" href="#/simulator">${esc(t("open_sim"))}</a></div>${settings}`;
    bindSettings(el);
    return;
  }
  const r = d.latest;
  const sev = d.status || "green";
  const isAr = getLang() === "ar";
  const cropName = crop ? (isAr ? crop.name_ar : crop.name_en) : t("none");
  const stageObj = meta.stages.find((s) => s.id === z.growth_stage);
  const regionObj = meta.regions.find((x) => x.id === z.governorate);

  // Crop-aware bands (fall back to Table 1.1 general ranges)
  const ph = crop ? [crop.ph_min, crop.ph_max] : [6.0, 7.0];
  const ecMax = crop ? crop.ec_limit : 2.0;
  const awcB = crop ? [crop.awc_min, crop.awc_max] : [60, 80];
  const tenB = crop ? [crop.tension_min, crop.tension_max] : [10, 35];
  const h = d.history;
  const series = (k) => h.map((x) => x[k]);
  const dev = d.devices[0];
  const npkCal = !!r.npk_calibrated;
  const nVal = npkCal ? r.n_cal : r.n_ppm, pVal = npkCal ? r.p_cal : r.p_ppm, kVal = npkCal ? r.k_cal : r.k_ppm;

  el.innerHTML = `
  <div class="status-banner ${sev}">
    <div class="traffic ${sev}" aria-hidden="true"><span></span><span></span><span></span></div>
    <div style="min-width:180px">
      <div style="font-size:1.3rem;font-weight:800">${esc(statusWord(sev))}</div>
      <div class="muted">${esc(z.name)} · ${esc(t("last_reading"))}: ${esc(fmtTime(r.time))}
        · ${badge(r.source === "simulator" ? "amber" : "green", r.source === "simulator" ? t("src_simulator") : t("src_hardware"))}</div>
    </div>
    <div class="row" style="gap:6px;align-items:center">${gaugeSVG(d.shi?.index)}<div><b>${esc(t("shi"))}</b><br><small>0–100</small></div></div>
    <div class="spacer"></div>
    <dl class="kv">
      <dt>${esc(t("crop"))}</dt><dd>${esc(cropName)}</dd>
      <dt>${esc(t("stage"))}</dt><dd>${esc(stageObj ? stageObj[getLang()] : "—")}</dd>
      <dt>${esc(t("season"))}</dt><dd>${esc((d.seasons_active || []).map((s) => meta.seasons.find((m) => m.id === s)?.[getLang()] || s).join(" + "))}${z.irrigation_type === "greenhouse" ? " · " + esc(t("greenhouse")) : ""}</dd>
      <dt>${esc(t("region"))}</dt><dd>${esc(regionObj ? regionObj[getLang()] : "—")}</dd>
    </dl>
  </div>

  <div class="grid g3" style="margin-top:16px">
    <section class="card" style="grid-column: span 2">
      <h3>${esc(t("soil_upper"))} <small>${fmt(r.upper_depth_cm, 0)} cm</small></h3>
      <div class="metrics">
        ${metric(t("awc"), fmt(r.awc_upper, 0), "%", bandSev(r.awc_upper, awcB[0], awcB[1], 10), `VWC ${fmt(r.vwc_upper)}%`)}
        ${metric(t("tension"), fmt(r.matric_kpa, 0), "kPa", bandSev(r.matric_kpa, tenB[0], tenB[1], 8))}
        ${metric(t("soil_temp"), fmt(r.soil_temp_upper), "°C", bandSev(r.soil_temp_upper, 18, 26, 6))}
        ${metric(t("ec25"), fmt(r.ec25_upper, 2), "dS/m", bandSev(r.ec25_upper, null, ecMax, ecMax * 0.4), `raw ${fmt(r.ec_pore_upper, 2)}`)}
        ${metric(t("ph"), fmt(r.ph, 1), "", bandSev(r.ph, ph[0], ph[1], 0.5))}
        ${metric(t("orp"), fmt(r.orp_mv, 0), "mV", r.orp_mv == null ? "" : r.orp_mv >= 300 ? "green" : r.orp_mv >= 200 ? "amber" : "red")}
        ${metric(t("o2"), fmt(r.o2_pct, 1), "%", r.o2_pct == null ? "" : r.o2_pct >= 12 ? "green" : r.o2_pct >= 8 ? "amber" : "red")}
      </div>
      <h4 style="margin-top:14px">${esc(t("dual_depth"))}</h4>
      <div class="depth-compare">
        <span>${esc(t("upper"))}</span><div class="bar"><i style="width:${Math.min(100, r.awc_upper ?? 0)}%"></i></div><span class="num">${fmt(r.awc_upper, 0)}%</span>
        <span>${esc(t("lower"))}</span><div class="bar ${r.awc_lower >= 90 ? "amber" : ""}"><i style="width:${Math.min(100, r.awc_lower ?? 0)}%"></i></div><span class="num">${fmt(r.awc_lower, 0)}%</span>
        <span>EC A / B</span><div class="muted">${fmt(r.ec25_upper, 2)} / ${fmt(r.ec25_lower, 2)} dS/m</div><span></span>
        <span>T A / B</span><div class="muted">${fmt(r.soil_temp_upper)} / ${fmt(r.soil_temp_lower)} °C</div><span></span>
      </div>
    </section>
    <section class="card">
      <h3>${esc(t("nutrients"))} ${badge(npkCal ? "green" : "amber", npkCal ? t("lab_cal") : t("unverified"))}</h3>
      <div class="metrics">
        ${metric("N", fmt(nVal, 0), "mg/kg")}${metric("P", fmt(pVal, 0), "mg/kg")}${metric("K", fmt(kVal, 0), "mg/kg")}
      </div>
      ${npkCal ? `<p class="note">raw ${fmt(r.n_ppm, 0)} / ${fmt(r.p_ppm, 0)} / ${fmt(r.k_ppm, 0)} → corrected = raw × gain + offset</p>`
               : `<p class="note">${isAr ? "قراءات حساس NPK منخفض التكلفة تقديرية حتى تُدخل تحليل معمل." : "Low-cost RS485 NPK probe values are indirect estimates until a lab profile calibrates the node."}</p>`}
    </section>
    <section class="card">
      <h3>${esc(t("microclimate"))}</h3>
      <div class="metrics">
        ${metric(t("air_temp"), fmt(r.air_temp_c), "°C")}
        ${metric(t("rh"), fmt(r.rh_pct, 0), "%", r.rh_pct == null ? "" : r.rh_pct > 80 ? "red" : r.rh_pct > 70 ? "amber" : "green")}
        ${metric(t("vpd"), fmt(r.vpd_kpa, 2), "kPa", bandSev(r.vpd_kpa, 0.8, 1.5, 0.3))}
        ${metric(t("par"), fmt(r.par, 0), "µmol/m²/s")}
        ${metric(t("dew_spread"), fmt(r.dew_point_spread), "°C", r.dew_point_spread == null ? "" : r.dew_point_spread < 2 ? "red" : "green")}
        ${metric(t("leaf_wet"), fmt(r.leaf_wetness, 0), "%")}
        ${metric(t("wind"), fmt(r.wind_ms, 1), "m/s")}
        ${metric(t("rain"), fmt(r.rain_mm, 1), "mm/h")}
      </div>
    </section>
    <section class="card">
      <h3>${esc(t("hardware"))} ${dev ? badge(dev.status === "online" ? "green" : dev.status === "fault" ? "red" : "grey", dev.status) : ""}</h3>
      ${dev ? `<div class="metrics">
        ${metric(t("battery"), fmt(dev.battery_v, 2), "V", dev.battery_v == null ? "" : dev.battery_v >= 12.4 ? "green" : dev.battery_v >= 12 ? "amber" : "red")}
        ${metric(t("rssi"), fmt(dev.rssi_dbm, 0), "dBm")}
        ${metric(t("firmware"), esc(dev.firmware_version || "—"))}
      </div><p class="note">${esc(dev.device_id)} · ${esc(fmtTime(dev.last_seen_at))}</p>` : `<p class="muted">—</p>`}
      ${(r.fault_flags || []).length ? `<div class="alert amber"><b>Fault flags:</b> ${esc(r.fault_flags.join(", "))}</div>` : ""}
    </section>
    <section class="card">
      <h3>${esc(t("active_alerts"))} <span class="badge ${sev}">${d.alerts.length}</span></h3>
      <div class="stack">${d.alerts.length ? d.alerts.map((a) => alertCard(a)).join("") : `<p class="muted">${esc(t("no_alerts"))}</p>`}</div>
    </section>
  </div>

  <div class="section-title"><h2>${esc(t("trends"))}</h2><small>${h.length} readings</small></div>
  <div class="grid g3">
    ${trend(t("awc") + " %", [{ values: series("awc_upper"), color: "var(--chart-1)", label: t("upper") }, { values: series("awc_lower"), color: "var(--chart-2)", label: t("lower") }], awcB)}
    ${trend(t("ec25") + " dS/m", [{ values: series("ec25_upper"), color: "var(--chart-1)", label: t("upper") }, { values: series("ec25_lower"), color: "var(--chart-2)", label: t("lower") }], [0, ecMax])}
    ${trend(t("ph"), [{ values: series("ph"), color: "var(--chart-1)", label: "pH" }], ph)}
    ${trend(t("soil_temp") + " °C", [{ values: series("soil_temp_upper"), color: "var(--chart-1)", label: t("upper") }, { values: series("soil_temp_lower"), color: "var(--chart-2)", label: t("lower") }], [18, 26])}
    ${trend(t("vpd") + " kPa", [{ values: series("vpd_kpa"), color: "var(--chart-1)", label: "VPD" }], [0.8, 1.5])}
    ${trend(t("shi"), [{ values: series("shi"), color: "var(--chart-1)", label: "SHI" }], [75, 100])}
  </div>
  ${settings}
  <p class="note" style="margin-top:16px">${esc(t("advisory_only"))}</p>`;
  bindSettings(el);
}

function trend(title, series, band) {
  return `<div class="card"><h3>${esc(title)}</h3>${sparkSVG(series, { band })}
    <div class="legend">${series.map((s) => `<span><i style="background:${s.color}"></i>${esc(s.label)}</span>`).join("")}<span><i style="background:var(--green-bg);height:8px"></i>${esc(t("target"))}</span></div></div>`;
}

function zoneSettings(z, meta) {
  const lang = getLang();
  return `<section class="card" style="margin-top:16px">
    <h3>${esc(t("zone_settings"))}</h3>
    <form id="zoneForm" class="form-grid">
      <label class="field"><span class="lbl">${esc(t("crop"))}</span><select name="active_crop_id">
        <option value="">${esc(t("none"))}</option>${options(meta.crops.map((c) => ({ value: c.slug, label: lang === "ar" ? c.name_ar : c.name_en })), z.active_crop_id)}</select></label>
      <label class="field"><span class="lbl">${esc(t("stage"))}</span><select name="growth_stage">${options(meta.stages.map((s) => ({ value: s.id, label: s[lang] })), z.growth_stage)}</select></label>
      <label class="field"><span class="lbl">${esc(t("season"))}</span><select name="season"><option value="auto">${esc(t("auto"))}</option>${options(meta.seasons.map((s) => ({ value: s.id, label: s[lang] })), z.season)}</select></label>
      <label class="field"><span class="lbl">${esc(t("region"))}</span><select name="governorate">${options(meta.regions.map((s) => ({ value: s.id, label: s[lang] })), z.governorate)}</select></label>
      <label class="field"><span class="lbl">${esc(t("irrigation"))}</span><select name="irrigation_type">${options(["drip", "greenhouse", "pivot"].map((v) => ({ value: v, label: t(v) })), z.irrigation_type)}</select></label>
      <label class="field"><span class="lbl">Area (feddan)</span><input name="area_feddan" type="number" step="0.1" min="0" value="${esc(z.area_feddan ?? "")}"></label>
      <div class="row" style="align-self:end"><button class="btn primary" type="submit">${esc(t("save"))}</button>${resetButton()}</div>
    </form>
  </section>`;
}

function bindSettings(el) {
  bindReset(el, render);
  const f = el.querySelector("#zoneForm");
  if (!f) return;
  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(f);
    const body = Object.fromEntries(fd.entries());
    body.area_feddan = body.area_feddan ? Number(body.area_feddan) : null;
    if (!body.active_crop_id) body.active_crop_id = "";
    await api(`/zones/${state.zoneId}`, { method: "PATCH", body });
    await refreshZones();
    toast(t("saved"));
  });
}
