import { api } from "../api.js";
import { state } from "../app.js";
import { bindReset, resetButton } from "../reset.js";
import { t, getLang } from "../i18n.js";
import { esc, fmt, options, toast } from "../ui.js";

const SOIL = [
  ["sand_pct", "Sand %", "رمل %"], ["silt_pct", "Silt %", "سلت %"], ["clay_pct", "Clay %", "طين %"],
  ["cec_meq", "CEC (meq/100g)", "السعة التبادلية (مللي مكافئ/100جم)"], ["som_pct", "Organic matter SOM %", "المادة العضوية %"],
  ["caco3_pct", "Active CaCO3 %", "الجير النشط %"], ["esp_pct", "ESP %", "الصوديوم المتبادل %"], ["sar", "SAR", "SAR"],
  ["bulk_density", "Bulk density (g/cm³)", "الكثافة الظاهرية (جم/سم³)"], ["water_table_m", "Water-table depth (m)", "عمق الماء الأرضي (م)"],
];
const WATER = [
  ["water_ec_w", "ECw (dS/m)", "ملوحة المياه ECw"], ["water_ph", "Water pH", "حموضة المياه"],
  ["water_hco3", "HCO3⁻ (meq/L)", "البيكربونات (مللي مكافئ/لتر)"], ["water_boron_ppm", "Boron (ppm)", "البورون (جزء في المليون)"],
  ["water_cl_ppm", "Chloride (mg/L)", "الكلوريد (مجم/لتر)"],
];
const NPK = [["lab_n_ppm", "Lab N (mg/kg)", "نيتروجين معملي"], ["lab_p_ppm", "Lab P (mg/kg)", "فوسفور معملي"], ["lab_k_ppm", "Lab K (mg/kg)", "بوتاسيوم معملي"]];

function inputs(list, lab) {
  const ar = getLang() === "ar";
  return list.map(([k, en, arL]) => `<label class="field"><span class="lbl">${esc(ar ? arL : en)}</span>
    <input name="${k}" type="number" step="any" value="${lab[k] ?? ""}"></label>`).join("");
}

export async function renderLab(el, ctx) {
  const d = await api(`/zones/${state.zoneId}`);
  if (!ctx.isCurrent()) return;
  const lab = d.lab || {};
  const lang = getLang();
  const textures = state.meta.textures;
  const cal = d.devices[0]?.npk_calibration || {};
  el.innerHTML = `
  <div class="section-title"><h2>${esc(t("lab_title"))}</h2><small>${esc(d.zone.name)}</small></div>
  <p class="muted">${esc(t("lab_intro"))}</p>
  <form id="labForm" class="stack">
    <fieldset><legend>${esc(t("soil_props"))}</legend>
      <div class="form-grid">
        <label class="field"><span class="lbl">${esc(t("texture"))}</span><select name="texture_class">
          ${options(textures.map((x) => ({ value: x.id, label: `${x[lang]} — FC ${x.fc}% / PWP ${x.pwp}%${x.external ? " *" : ""}` })), lab.texture_class || "loam")}</select></label>
        <label class="field"><span class="lbl">${esc(t("sample_date"))}</span><input name="sample_date" type="date" value="${esc(lab.sample_date || "")}"></label>
        ${inputs(SOIL, lab)}
      </div>
      <p class="note">${lang === "ar" ? "* قيم الطميية السلتية من مرجع خارجي (ليست في المواصفة)." : "* Silt-loam FC/PWP come from an external reference (not in the spec, Section 6.4)."}</p>
    </fieldset>
    <fieldset><legend>${esc(t("water_props"))}</legend><div class="form-grid">${inputs(WATER, lab)}</div></fieldset>
    <fieldset><legend>${esc(t("npk_lab"))}</legend><div class="form-grid">${inputs(NPK, lab)}</div>
      <p class="note">${lang === "ar" ? "عند الحفظ تُحسب معاملات المعايرة من آخر قراءة للحساس." : "On save, gain/offset are computed against the latest probe reading; with two or more lab tests the fit becomes a least-squares line."}</p>
    </fieldset>
    <div class="row"><button class="btn primary big" type="submit">${esc(t("save"))}</button>${resetButton()}
      <span class="muted">${lab.created_at ? esc(t("last_reading")) + ": " + esc(lab.created_at) : ""}</span></div>
  </form>
  <section class="card" style="margin-top:16px">
    <h3>${esc(t("current_cal"))}</h3>
    ${Object.keys(cal).length ? `<div class="table-wrap"><table><thead><tr><th>Nutrient</th><th class="num">gain</th><th class="num">offset</th><th class="num">points</th></tr></thead><tbody>
      ${Object.entries(cal).map(([n, c]) => `<tr><td>${n.toUpperCase()}</td><td class="num">${fmt(c.gain, 4)}</td><td class="num">${fmt(c.offset, 2)}</td><td class="num">${c.points?.length ?? 0}</td></tr>`).join("")}
    </tbody></table></div>` : `<p class="muted">${esc(t("unverified"))}</p>`}
  </section>`;
  bindReset(el, () => renderLab(el, ctx));
  el.querySelector("#labForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = {};
    for (const [k, v] of fd.entries()) {
      if (v === "") continue;
      body[k] = ["texture_class", "sample_date"].includes(k) ? v : Number(v);
    }
    await api(`/zones/${state.zoneId}/lab-profile`, { method: "PUT", body });
    toast(t("saved"));
    renderLab(el, ctx);
  });
}
