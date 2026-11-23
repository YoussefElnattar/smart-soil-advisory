import { api } from "../api.js";
import { state, go } from "../app.js";
import { t, getLang } from "../i18n.js";
import { alertCard, esc, fmt, fmtTime } from "../ui.js";

export async function renderAlerts(el, ctx) {
  const lang = getLang();
  const showAll = state.params.get("all") === "1";
  const [al, rx, kb] = await Promise.all([
    api(`/alerts?zone_id=${state.zoneId}${showAll ? "" : "&active=true"}`),
    api(`/prescriptions?zone_id=${state.zoneId}`),
    api("/knowledge"),
  ]);
  if (!ctx.isCurrent()) return;
  const cropName = (slug) => { const c = state.meta.crops.find((x) => x.slug === slug); return c ? (lang === "ar" ? c.name_ar : c.name_en) : slug; };
  el.innerHTML = `
  <div class="grid g2">
    <section class="card">
      <h3>${esc(t("alerts_title"))} <label class="row" style="font-weight:400;font-size:.85rem;gap:6px"><input type="checkbox" id="allChk" ${showAll ? "checked" : ""}>${esc(t("show_all"))}</label></h3>
      <div class="stack">${al.alerts.length ? al.alerts.map((a) => alertCard(a, { ackable: true })).join("") : `<p class="muted">${esc(t("no_alerts"))}</p>`}</div>
    </section>
    <div class="stack">
      <section class="card">
        <h3>${esc(t("hw_title"))}</h3>
        <p class="muted">${esc(t("hw_intro"))}</p>
        <a class="btn primary big" href="/api/v1/hardware-guide/export?zone_id=${state.zoneId}">⬇ ${esc(t("hw_download"))}</a>
        <p class="note" style="margin-top:10px">${lang === "ar" ? "النسخة الافتراضية محفوظة أيضاً في docs/Hardware_BOM_Wiring_Firmware.pdf، والكود في firmware/esp32_soil_node/." : "A default copy is also saved at docs/Hardware_BOM_Wiring_Firmware.pdf; the firmware source lives in firmware/esp32_soil_node/."}</p>
      </section>
      <section class="card">
        <h3>${esc(t("rx_history"))}</h3>
        ${rx.prescriptions.length ? `<div class="table-wrap"><table><thead><tr><th>#</th><th>${esc(t("crop"))}</th><th>${esc(t("stage"))}</th><th class="num">SHI</th><th>${esc(t("generated"))}</th></tr></thead><tbody>
          ${rx.prescriptions.map((p) => `<tr class="clickable" data-rx="${p.id}"><td>${p.id}</td><td>${esc(cropName(p.crop_id))}</td><td>${esc(state.meta.stages.find((s) => s.id === p.growth_stage)?.[lang] || p.growth_stage)}</td><td class="num">${fmt(p.soil_health_index, 0)}</td><td>${esc(fmtTime(p.created_at))}</td></tr>`).join("")}
        </tbody></table></div>` : `<p class="muted">—</p>`}
      </section>
    </div>
  </div>

  <div class="section-title"><h2>${esc(t("reference"))}</h2></div>
  <div class="grid g2">
    ${refTable("Table 1.1 — Real-time probe parameters", ["", "Technology", "Optimal", "Role"], kb.probe_parameters.map((p) => [p.en + (p.unit ? ` (${p.unit})` : ""), p.tech, p.optimal, p.role]))}
    ${refTable("Table 1.2 — Lab baseline traits", ["", "Optimal", "Why it matters"], kb.lab_traits.map((p) => [p.en, p.optimal, p.why]))}
    ${refTable("Table 2.1 — Macronutrients (alkaline soils)", ["", "Role", "Forms", "Deficiency"], kb.macronutrients.map((p) => [p.nutrient, p.role, p.forms, p.deficiency]))}
    ${refTable("Table 2.2 — Micronutrients & chelation", ["", "Form", "Deficiency"], kb.micronutrients.map((p) => [p.nutrient, p.form, p.deficiency]))}
    ${refTable("Section 1.3 — Microclimate", ["", "Optimal", "Why"], kb.microclimate.map((p) => [p.en, p.optimal, p.why]))}
    ${refTable("Table 2.4 — Sensor-triggered remediation rules", ["Code", "Pattern", "Diagnosis"], kb.remediation_rules.map((p) => [p.code, p.pattern, p.diagnosis]))}
  </div>`;

  el.querySelector("#allChk").addEventListener("change", (e) => go("alerts", e.target.checked ? { all: "1" } : {}));
  el.querySelectorAll("[data-ack]").forEach((b) => b.addEventListener("click", async () => {
    await api(`/alerts/${b.dataset.ack}/ack`, { method: "POST" });
    renderAlerts(el, ctx);
  }));
  el.querySelectorAll("[data-rx]").forEach((r) => r.addEventListener("click", () => go("prescription", { id: r.dataset.rx })));
}

function refTable(title, head, rows) {
  return `<details class="card"><summary><b>${esc(title)}</b></summary><div class="table-wrap" style="margin-top:8px"><table>
    <thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${r.map((c, i) => `<td>${i === 0 ? `<b>${esc(c)}</b>` : esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
}
