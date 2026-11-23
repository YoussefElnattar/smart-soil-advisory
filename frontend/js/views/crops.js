import { api } from "../api.js";
import { state, go } from "../app.js";
import { t, getLang } from "../i18n.js";
import { badge, esc, fmt } from "../ui.js";

const TIER_SEV = { ready: "green", minor: "amber", reclaim: "red" };
let selected = new Set();

export async function renderCrops(el, ctx) {
  const lang = getLang();
  const [kb, match] = await Promise.all([
    api("/crops"),
    api("/optimize/match-crops", { method: "POST", body: { zone_id: state.zoneId } }).catch((e) => ({ error: e.message })),
  ]);
  if (!ctx.isCurrent()) return;
  const cropsBySlug = Object.fromEntries(kb.crops.map((c) => [c.slug, c]));
  el.innerHTML = `
  <div class="section-title"><h2>${esc(t("match_title"))}</h2>
    ${match.ranking ? `<small>${esc((match.seasons_active || []).join(" + "))}${match.greenhouse ? " · " + esc(t("greenhouse")) : ""} · Salinity 25 · pH/CaCO3 20 · Climate 20 · Texture 15 · Moisture 10 · Water 10</small>` : ""}</div>
  <div class="card row no-print">
    <label class="field" style="flex:2;min-width:180px"><span class="lbl">${esc(t("search"))}</span><input id="fq" type="search" placeholder="tomato / طماطم"></label>
    <label class="field" style="flex:1;min-width:160px"><span class="lbl">${esc(t("season"))}</span><select id="fs"><option value="">${esc(t("all_seasons"))}</option>
      ${state.meta.seasons.map((s) => `<option value="${s.id}">${esc(s[lang])}</option>`).join("")}</select></label>
    <label class="field" style="flex:1;min-width:160px"><span class="lbl">${esc(t("salt_filter"))}</span><select id="ft">
      <option value="">${esc(t("any"))}</option><option value="high">${esc(t("tol_high"))}</option><option value="mid">${esc(t("tol_mid"))}</option><option value="low">${esc(t("tol_low"))}</option></select></label>
    <button class="btn" id="cmpBtn" style="align-self:end">${esc(t("compare"))}</button>
  </div>
  <section class="card" style="margin-top:16px" id="rankCard">
    ${match.error ? `<div class="empty">${esc(match.error)}<br><br><a class="btn primary" href="#/simulator">${esc(t("open_sim"))}</a></div>` : ""}
    <div id="rankList"></div>
  </section>
  <section class="card" style="margin-top:16px" id="cmp" hidden></section>
  <div class="section-title"><h2>${esc(t("explorer"))}</h2></div>
  <div class="grid g2" id="explorer"></div>`;

  const apply = () => {
    const q = el.querySelector("#fq").value.trim().toLowerCase();
    const season = el.querySelector("#fs").value;
    const tol = el.querySelector("#ft").value;
    const keep = (slug) => {
      const c = cropsBySlug[slug];
      const text = `${c.name_en} ${c.name_ar} ${c.scientific} ${c.slug}`.toLowerCase();
      if (q && !text.includes(q)) return false;
      if (season && !(c.perennial || (c.season_scores[season] ?? 0) >= 0.8)) return false;
      if (tol === "high" && c.ec_limit < 2.5) return false;
      if (tol === "mid" && (c.ec_limit < 1.5 || c.ec_limit >= 2.5)) return false;
      if (tol === "low" && c.ec_limit >= 1.5) return false;
      return true;
    };
    if (match.ranking) el.querySelector("#rankList").innerHTML = match.ranking.filter((r) => keep(r.slug)).map((r) => rankRow(r, match.dimension_names)).join("") || `<p class="muted">—</p>`;
    el.querySelector("#explorer").innerHTML = kb.crops.filter((c) => keep(c.slug)).map(cropCard).join("");
  };
  ["#fq", "#fs", "#ft"].forEach((s) => el.querySelector(s).addEventListener("input", apply));
  apply();

  el.onclick = (e) => {
    const opt = e.target.closest("[data-optimize]");
    if (opt) go("prescription", { crop: opt.dataset.optimize, stage: "establishment" });
  };
  el.onchange = (e) => {
    if (e.target.matches("[data-pick]")) {
      e.target.checked ? selected.add(e.target.dataset.pick) : selected.delete(e.target.dataset.pick);
    }
  };
  el.querySelector("#cmpBtn").addEventListener("click", () => {
    const box = el.querySelector("#cmp");
    box.hidden = false;
    const rows = (match.ranking || []).filter((r) => selected.has(r.slug));
    if (rows.length < 2) { box.innerHTML = `<p class="muted">${esc(t("pick_two"))}</p>`; return; }
    const dims = Object.keys(rows[0].dimensions);
    box.innerHTML = `<h3>${esc(t("compare_title"))}</h3><div class="table-wrap"><table>
      <thead><tr><th></th>${rows.map((r) => `<th class="num">${esc(lang === "ar" ? r.name_ar : r.name_en)}</th>`).join("")}</tr></thead>
      <tbody><tr><td><b>${esc(t("score"))}</b></td>${rows.map((r) => `<td class="num"><b>${fmt(r.score, 1)}</b></td>`).join("")}</tr>
      ${dims.map((d) => `<tr><td>${esc(match.dimension_names[d][lang])}</td>${rows.map((r) => `<td class="num">${fmt(r.dimensions[d], 0)}</td>`).join("")}</tr>`).join("")}
      <tr><td>${esc(t("limiting"))}</td>${rows.map((r) => `<td><ul class="limits">${r.limiting_factors.map((l) => `<li>${esc(lang === "ar" ? l.ar : l.en)}</li>`).join("")}</ul></td>`).join("")}</tr>
      </tbody></table></div>`;
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function rankRow(r, dimNames) {
  const lang = getLang();
  return `<div class="rank-row">
    <div class="rank-num">${r.rank}</div>
    <div><label class="row" style="gap:6px"><input type="checkbox" data-pick="${r.slug}" ${selected.has(r.slug) ? "checked" : ""}>
      <b>${esc(lang === "ar" ? r.name_ar : r.name_en)}</b></label>
      ${badge(TIER_SEV[r.tier], lang === "ar" ? r.tier_ar : r.tier_en)} ${r.disqualified ? badge("red", lang === "ar" ? "مستبعد" : "Disqualified") : ""}</div>
    <div>
      <div class="score-bar"><i style="width:${r.score}%"></i><b>${fmt(r.score, 1)}%</b></div>
      <div class="dims" title="${Object.entries(r.dimensions).map(([k, v]) => `${dimNames[k][lang]}: ${fmt(v, 0)}`).join(" · ")}">
        ${Object.entries(r.dimensions).map(([k, v]) => `<span title="${esc(dimNames[k][lang])} ${fmt(v, 0)}"><i style="width:${v}%;${v < 50 ? "background:var(--red)" : v < 80 ? "background:var(--amber)" : ""}"></i></span>`).join("")}
      </div>
      ${r.limiting_factors.length ? `<ul class="limits">${r.limiting_factors.slice(0, 4).map((l) => `<li>${esc(lang === "ar" ? l.ar : l.en)}</li>`).join("")}</ul>` : ""}
    </div>
    <div><button class="btn small" data-optimize="${r.slug}" title="${esc(t("optimize_crop"))}">${esc(t("optimize_short"))}</button></div>
  </div>`;
}

function cropCard(c) {
  const lang = getLang();
  const ar = lang === "ar";
  return `<details class="card crop-card">
    <summary><span>${c.order}. ${esc(ar ? c.name_ar : c.name_en)} <small class="muted"><i>${esc(c.scientific)}</i></small></span>
      <span>${badge(c.ec_limit >= 2.5 ? "green" : c.ec_limit >= 1.5 ? "amber" : "red", `ECe ≤ ${c.ec_limit}`)}</span></summary>
    <dl class="kv" style="margin-top:10px">
      <dt>${ar ? "التربة المفضلة" : "Preferred soil"}</dt><dd>${esc(ar ? c.preferred_soil_ar : c.preferred_soil_en)}</dd>
      <dt>pH</dt><dd>${c.ph_min}–${c.ph_max}</dd>
      <dt>${ar ? "أعماق الحساسات" : "Sensor depths"}</dt><dd>${c.upper_depth_cm} / ${c.lower_depth_cm} cm</dd>
      <dt>${ar ? "الرطوبة/الشد" : "Moisture / tension"}</dt><dd>${c.awc_min}–${c.awc_max}% AWC (${c.tension_min}–${c.tension_max} kPa). ${esc(ar ? c.moisture_note_ar : c.moisture_note_en)}</dd>
      <dt>${ar ? "المواسم" : "Seasons"}</dt><dd>${esc(ar ? c.seasons_ar : c.seasons_en)}</dd>
      <dt>${ar ? "الحرارة نهار/ليل" : "Temp day / night"}</dt><dd>${c.day_temp.join("–")} / ${c.night_temp.join("–")} °C</dd>
      <dt>${ar ? "الرطوبة النسبية" : "RH"}</dt><dd>${c.rh.join("–")}%</dd>
      ${c.chill_hours ? `<dt>${ar ? "ساعات البرودة" : "Chill hours"}</dt><dd>${c.chill_hours.join("–")} h (&lt; 7.2 °C)</dd>` : ""}
      <dt>${ar ? "المناخ والمخاطر" : "Climate & hazards"}</dt><dd>${esc(ar ? c.climate_note_ar : c.climate_note_en)}</dd>
      <dt>NPK</dt><dd>${esc(ar ? c.npk_focus_ar : c.npk_focus_en)}</dd>
      <dt>${ar ? "العناصر الصغرى" : "Micros & biostim."}</dt><dd>${esc(ar ? c.micro_focus_ar : c.micro_focus_en)}</dd>
      <dt>${ar ? "قاعدة الحساس" : "Sensor rule"}</dt><dd>${esc(ar ? c.sensor_rule_ar : c.sensor_rule_en)}</dd>
    </dl>
    <div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>${esc(t("stage"))}</th><th class="num">Kc <span class="badge ext">${esc(t("external"))}</span></th><th class="num">VPD kPa</th></tr></thead>
      <tbody>${c.stages.map((s) => `<tr><td>${esc(s[lang])}</td><td class="num">${fmt(s.kc_ext, 2)}</td><td class="num">${s.vpd_target.join("–")}</td></tr>`).join("")}</tbody></table></div>
    <p class="note">Kc: ${esc(c.kc_source)}</p>
    <button class="btn small" data-optimize="${c.slug}">${esc(t("optimize_crop"))}</button>
  </details>`;
}
