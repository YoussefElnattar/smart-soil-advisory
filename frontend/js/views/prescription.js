import { api } from "../api.js";
import { state, go } from "../app.js";
import { t, getLang, L } from "../i18n.js";
import { alertCard, badge, esc, fmt, fmtTime, gaugeSVG, options } from "../ui.js";

export async function renderPrescription(el, ctx) {
  const lang = getLang();
  const zone = await api(`/zones/${state.zoneId}`);
  if (!ctx.isCurrent()) return;
  const pid = state.params.get("id");
  const crop = state.params.get("crop") || zone.zone.active_crop_id || "";
  const stage = state.params.get("stage") || zone.zone.growth_stage || "vegetative";
  el.innerHTML = `
  <div class="section-title"><h2>${esc(t("rx_title"))}</h2><small>${esc(zone.zone.name)} · ${esc(t("units_feddan"))}</small></div>
  <form id="rxForm" class="card row no-print">
    <label class="field" style="min-width:200px"><span class="lbl">${esc(t("crop"))}</span><select name="crop">
      <option value="">${lang === "ar" ? "أفضل محصول مطابق تلقائياً" : "Auto — top-ranked crop"}</option>
      ${options(state.meta.crops.map((c) => ({ value: c.slug, label: lang === "ar" ? c.name_ar : c.name_en })), crop)}</select></label>
    <label class="field" style="min-width:200px"><span class="lbl">${esc(t("stage"))}</span><select name="stage">
      ${options(state.meta.stages.map((s) => ({ value: s.id, label: s[lang] })), stage)}</select></label>
    <button class="btn primary" type="submit" style="align-self:end">${esc(t("generate"))}</button>
    <button class="btn" type="button" id="printBtn" style="align-self:end">${esc(t("print"))}</button>
  </form>
  <div id="rxOut" style="margin-top:16px"><div class="empty">${esc(t("loading"))}</div></div>`;
  el.querySelector("#printBtn").addEventListener("click", () => window.print());
  el.querySelector("#rxForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    go("prescription", Object.fromEntries([...fd.entries()].filter(([, v]) => v)));
  });
  const out = el.querySelector("#rxOut");
  try {
    const rx = pid ? await api(`/prescriptions/${pid}`)
      : await api("/optimize/prescription", { method: "POST", body: { zone_id: state.zoneId, crop_slug: crop || null, stage } });
    if (!ctx.isCurrent()) return;
    out.innerHTML = renderRx(rx);
  } catch (err) {
    out.innerHTML = `<div class="card empty">${esc(err.message)}<br><br><a class="btn primary" href="#/simulator">${esc(t("open_sim"))}</a></div>`;
  }
}

function statusBadge(s) {
  const map = { optimal: "green", deficient: "amber", excess: "red", unknown: "grey" };
  return badge(map[s] || "grey", t("st_" + s));
}

function srcTag(item) {
  return item.external ? `<span class="badge ext" title="${esc(item.source)}">${esc(t("external"))}</span>` : `<small class="muted">${esc(item.source || "")}</small>`;
}

function tankBox(name, cls, items, paused) {
  return `<div class="tank ${cls}"><h4><span>${esc(name)}</span>${paused ? badge("red", t("paused")) : ""}</h4>
    ${items.length ? `<ul>${items.map((i) => `<li><b>${fmt(i.kg, 2)} kg</b> ${esc(getLang() === "ar" ? i.ar : i.en)}</li>`).join("")}</ul>` : `<p class="muted">${esc(t("empty_tank"))}</p>`}</div>`;
}

function tanks(plan, paused) {
  if (!plan) return "";
  return `<div class="grid g3">${tankBox(t("tank_a"), "A", plan.tanks.A, paused)}${tankBox(t("tank_b"), "B", plan.tanks.B, paused)}${tankBox(t("tank_acid"), "ACID", plan.tanks.ACID, paused)}</div>`;
}

export function renderRx(rx) {
  const lang = getLang();
  const ir = rx.irrigation;
  const m = rx.macronutrients;
  const cropName = lang === "ar" ? rx.crop.name_ar : rx.crop.name_en;
  const shi = rx.soil_health_index?.index;
  return `
  <div class="print-only"><h1>${esc(t("rx_title"))}</h1></div>
  <div class="status-banner ${rx.status}">
    <div class="traffic ${rx.status}"><span></span><span></span><span></span></div>
    <div><div style="font-size:1.25rem;font-weight:800">${esc(cropName)} · ${esc(L(rx, "stage"))}</div>
      <div class="muted">${esc(rx.zone?.name || "")} · ${esc(t("generated"))}: ${esc(fmtTime(rx.generated_at))}${rx.id ? ` · #${rx.id}` : ""}</div></div>
    <div class="spacer"></div>
    <div class="row">${gaugeSVG(shi)}<b>${esc(t("shi"))}</b></div>
  </div>

  <section class="card" style="margin-top:16px">
    <h3>${esc(t("gap_table"))}</h3>
    <div class="table-wrap"><table><thead><tr><th></th><th class="num">${esc(t("measured"))}</th><th class="num">${esc(t("target"))}</th><th>${esc(t("status"))}</th></tr></thead>
    <tbody>${rx.gaps.map((g) => `<tr><td>${esc(lang === "ar" ? g.ar : g.en)}</td><td class="num">${g.value === null ? "—" : fmt(g.value, 2)} ${esc(g.unit)}</td><td class="num">${esc(g.target)} ${esc(g.unit)}</td><td>${statusBadge(g.status)}</td></tr>`).join("")}</tbody></table></div>
  </section>

  <section class="card" style="margin-top:16px">
    <h3>${esc(t("m1"))}</h3>
    ${rx.conditioning.length ? `<div class="table-wrap"><table><thead><tr><th></th><th class="num">kg · m³</th><th>${lang === "ar" ? "التوقيت" : "When"}</th><th>${lang === "ar" ? "السبب" : "Why"}</th></tr></thead><tbody>
      ${rx.conditioning.map((c) => `<tr><td><b>${esc(lang === "ar" ? c.ar : c.en)}</b><br>${srcTag(c)}</td>
        <td class="num"><b>${c.amount === null ? "—" : esc(typeof c.amount === "number" ? fmt(c.amount, 0) : c.amount)}</b> ${esc(c.unit)}</td>
        <td>${esc(L(c, "timing"))}</td><td>${esc(L(c, "reason"))}</td></tr>`).join("")}
    </tbody></table></div>` : `<p class="muted">${esc(t("nothing_needed"))}</p>`}
  </section>

  <section class="card" style="margin-top:16px">
    <h3>${esc(t("m2"))} ${ir.halt ? badge("red", lang === "ar" ? "أوقف الري" : "HALT IRRIGATION") : ""}</h3>
    ${ir.warnings.map((w) => `<div class="alert ${ir.halt ? "red" : "amber"}" style="margin-bottom:8px">${esc(lang === "ar" ? w.ar : w.en)}</div>`).join("")}
    <div class="metrics">
      <div class="metric"><span class="k">${esc(t("gross_volume"))}</span><span class="v">${fmt(ir.gross_m3_per_feddan, 1)} <small>m³/feddan</small></span></div>
      <div class="metric"><span class="k">${esc(t("net_volume"))}</span><span class="v">${fmt(ir.net_m3_per_feddan, 1)} <small>m³/feddan</small></span></div>
      <div class="metric ${ir.leaching_pct ? "amber" : ""}"><span class="k">${esc(t("leaching"))}</span><span class="v">+${fmt(ir.leaching_pct, 0)} <small>%</small></span></div>
      <div class="metric"><span class="k">${esc(t("pulses"))}</span><span class="v">${ir.pulses_per_day}</span><small>${fmt(ir.m3_per_pulse, 1)} m³ ${esc(t("per_pulse"))}</small></div>
      <div class="metric"><span class="k">${esc(t("awc"))} A / B</span><span class="v">${fmt(ir.awc_upper, 0)} / ${fmt(ir.awc_lower, 0)} <small>%</small></span><small>${esc(t("target"))} ${ir.awc_target.join("–")}%</small></div>
      <div class="metric"><span class="k">${esc(t("root_depth"))}</span><span class="v">${fmt(ir.root_depth_m, 2)} <small>m</small></span><small>FC ${ir.fc_pct}% · PWP ${ir.pwp_pct}%</small></div>
      <div class="metric"><span class="k">${esc(t("efficiency"))}</span><span class="v">${fmt(ir.efficiency * 100, 0)} <small>%</small></span></div>
      <div class="metric"><span class="k">${esc(t("kc"))} <span class="badge ext">${esc(t("external"))}</span></span><span class="v">${fmt(ir.kc_stage_ext, 2)}</span></div>
    </div>
    <p class="note" style="margin-top:10px">${esc(L(ir, "timing"))}. Gross = ((FC − VWC)/100 × root depth × 4200) / (efficiency × (1 − LF)); LF = max(+15–25% spec band, FAO-29 ECw / (5·ECe_limit − ECw)).</p>
  </section>

  <section class="card" style="margin-top:16px">
    <h3>${esc(t("m3"))} ${badge(m.npk_label === "Lab-Calibrated" ? "green" : "amber", m.npk_label === "Lab-Calibrated" ? t("lab_cal") : t("unverified"))}</h3>
    <p>${esc(L(m, "focus"))}</p>
    <div class="table-wrap"><table><thead><tr><th></th><th class="num">${esc(t("measured"))}</th><th class="num">${esc(t("target"))} <span class="badge ext">${esc(t("external"))}</span></th><th>${esc(t("status"))}</th><th class="num">kg/feddan</th></tr></thead><tbody>
      ${m.npk_rows.map((r) => `<tr><td><b>${r.nutrient}</b></td><td class="num">${fmt(r.measured_ppm, 0)} mg/kg</td><td class="num">${r.target_ppm.join("–")} mg/kg</td><td>${statusBadge(r.status)}</td><td class="num">${fmt(r.correction_kg_element, 1)}</td></tr>`).join("")}
    </tbody></table></div>
    <h4 style="margin-top:14px">${esc(t("weekly_programme"))} <small class="muted">kg/feddan/week · ${m.applications_per_week} ${esc(t("apps_week"))}</small></h4>
    ${tanks(m.weekly_plan, m.paused)}
    ${m.correction_plan ? `<h4 style="margin-top:14px">${esc(t("correction_dose"))}</h4>${tanks(m.correction_plan, m.paused)}` : ""}
    <details style="margin-top:12px"><summary>${esc(t("per_app"))}</summary>
      <div class="grid g3" style="margin-top:8px">${["A", "B", "ACID"].map((k) => `<div class="tank ${k}"><h4>${esc(t(k === "A" ? "tank_a" : k === "B" ? "tank_b" : "tank_acid"))}</h4><ul>${(m.per_application[k] || []).map((i) => `<li>${fmt(i.kg * 1000, 0)} g ${esc(lang === "ar" ? i.ar : i.en)}</li>`).join("") || `<li class="muted">${esc(t("empty_tank"))}</li>`}</ul></div>`).join("")}</div>
    </details>
    <div class="stack" style="margin-top:12px">${m.notes.map((n) => `<div class="alert amber">${esc(lang === "ar" ? n.ar : n.en)}</div>`).join("")}</div>
    <p class="note" style="margin-top:8px">${esc(m.external_note)}</p>
  </section>

  <section class="card" style="margin-top:16px">
    <h3>${esc(t("m4"))}</h3>
    <div class="table-wrap"><table><tbody>
      ${rx.biostimulants.map((b) => `<tr><td><b>${esc(lang === "ar" ? b.ar : b.en)}</b><br>${srcTag(b)}</td><td>${esc(L(b, "rate"))}</td><td>${esc(L(b, "reason"))}</td></tr>`).join("") || `<tr><td class="muted">—</td></tr>`}
    </tbody></table></div>
  </section>

  <section class="card" style="margin-top:16px">
    <h3>${esc(t("m5"))}</h3>
    <div class="stack">${rx.alerts.length ? rx.alerts.map((a) => alertCard(a)).join("") : `<p class="muted">${esc(t("no_alerts"))}</p>`}</div>
  </section>
  <p class="note" style="margin-top:16px">${esc(L(rx, "advisory_only_note"))}</p>`;
}
