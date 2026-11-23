// Small UI helpers — no framework.
import { t, getLang } from "./i18n.js";

export function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function fmt(v, nd = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number(v).toLocaleString(getLang() === "ar" ? "ar-EG-u-nu-latn" : "en-US", { maximumFractionDigits: nd, minimumFractionDigits: 0 });
}

export function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(getLang() === "ar" ? "ar-EG-u-nu-latn" : "en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export function badge(sev, text) {
  return `<span class="badge ${esc(sev)}">${esc(text ?? t("status_" + sev))}</span>`;
}

export function statusWord(sev) { return t("status_" + (sev || "green")); }

export function metric(label, value, unit = "", sev = "", sub = "") {
  return `<div class="metric ${sev}"><span class="k">${esc(label)}</span><span class="v">${value}${unit ? ` <small>${esc(unit)}</small>` : ""}</span>${sub ? `<small>${sub}</small>` : ""}</div>`;
}

/** Severity of a value against a band: inside → green, within margin → amber, else red. */
export function bandSev(v, lo, hi, margin) {
  if (v === null || v === undefined) return "";
  if ((lo === null || v >= lo) && (hi === null || v <= hi)) return "green";
  const d = lo !== null && v < lo ? lo - v : v - hi;
  return d <= margin ? "amber" : "red";
}

export function gaugeSVG(value) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  const angle = Math.PI * (1 - v / 100);
  const x = 60 + 48 * Math.cos(angle), y = 66 - 48 * Math.sin(angle);
  const color = v >= 75 ? "var(--green)" : v >= 50 ? "var(--amber)" : "var(--red)";
  const large = 0;
  return `<svg class="gauge" viewBox="0 0 120 76" role="img" aria-label="${esc(t("shi"))} ${fmt(value, 0)}">
    <path d="M12 66 A48 48 0 0 1 108 66" fill="none" stroke="var(--surface-2)" stroke-width="11" stroke-linecap="round"/>
    ${value === null || value === undefined ? "" : `<path d="M12 66 A48 48 0 ${large} 1 ${x.toFixed(1)} ${y.toFixed(1)}" fill="none" stroke="${color}" stroke-width="11" stroke-linecap="round"/>`}
    <text x="60" y="62" text-anchor="middle" font-size="22" font-weight="800" fill="var(--text)">${value === null || value === undefined ? "—" : fmt(value, 0)}</text>
  </svg>`;
}

/** Multi-series sparkline. series: [{values:[...], color, label}] */
export function sparkSVG(series, { band } = {}) {
  const all = series.flatMap((s) => s.values).filter((v) => v !== null && v !== undefined);
  if (all.length < 2) return `<div class="muted" style="font-size:.8rem">—</div>`;
  let min = Math.min(...all), max = Math.max(...all);
  if (band) { min = Math.min(min, band[0]); max = Math.max(max, band[1]); }
  if (max - min < 1e-6) { max += 1; min -= 1; }
  const W = 300, H = 64, P = 4;
  const n = Math.max(...series.map((s) => s.values.length));
  const X = (i) => P + (i * (W - 2 * P)) / Math.max(1, n - 1);
  const Y = (v) => H - P - ((v - min) * (H - 2 * P)) / (max - min);
  const rtl = getLang() === "ar";
  const bandRect = band ? `<rect x="0" y="${Y(band[1]).toFixed(1)}" width="${W}" height="${(Y(band[0]) - Y(band[1])).toFixed(1)}" fill="var(--green-bg)"/>` : "";
  const paths = series.map((s) => {
    let d = "", pen = false;
    s.values.forEach((v, i) => {
      if (v === null || v === undefined) { pen = false; return; }
      d += `${pen ? "L" : "M"}${X(i).toFixed(1)} ${Y(v).toFixed(1)} `; pen = true;
    });
    return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join("");
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" ${rtl ? 'style="transform:scaleX(-1)"' : ""}>${bandRect}${paths}</svg>`;
}

export function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2600);
}

export function options(list, selected, labelFn) {
  return list.map((o) => `<option value="${esc(o.value)}" ${String(o.value) === String(selected ?? "") ? "selected" : ""}>${esc(labelFn ? labelFn(o) : o.label)}</option>`).join("");
}

export function alertCard(a, { ackable = false } = {}) {
  const isAr = getLang() === "ar";
  const msg = isAr ? a.message_ar : a.message_en;
  const act = isAr ? (a.recommended_farmer_action_ar ?? a.action_ar) : (a.recommended_farmer_action ?? a.action_en);
  return `<div class="alert ${esc(a.severity)}">
    <div class="row"><span class="light ${esc(a.severity)}"></span><span class="msg">${esc(msg)}</span></div>
    ${act ? `<div class="act">→ ${esc(act)}</div>` : ""}
    <div class="meta row">${esc(a.rule_code)} · ${esc(a.source || "")}${a.created_at ? " · " + esc(fmtTime(a.created_at)) : ""}
      ${a.active === 0 ? `<span class="badge grey">resolved</span>` : ""}
      ${ackable && a.id ? (a.acknowledged ? `<span class="badge grey">${esc(t("acked"))}</span>` : `<button class="btn small" data-ack="${a.id}">${esc(t("ack"))}</button>`) : ""}
    </div>
  </div>`;
}
