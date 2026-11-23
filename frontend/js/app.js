import { api } from "./api.js";
import { applyStatic, getLang, setLang, t } from "./i18n.js";
import { esc, toast } from "./ui.js";
import { renderDashboard } from "./views/dashboard.js";
import { renderLab } from "./views/lab.js";
import { renderPrescription } from "./views/prescription.js";
import { renderCrops } from "./views/crops.js";
import { renderSimulator } from "./views/simulator.js";
import { renderAlerts } from "./views/alerts.js";

const VIEWS = { dashboard: renderDashboard, lab: renderLab, prescription: renderPrescription, crops: renderCrops, simulator: renderSimulator, alerts: renderAlerts };

export const state = {
  meta: null,
  zones: [],
  zoneId: null,
  view: "dashboard",
  params: new URLSearchParams(),
};

function storeGet(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } }
function storeSet(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } }

export function go(view, params = {}) {
  const qs = new URLSearchParams(params).toString();
  location.hash = `#/${view}${qs ? "?" + qs : ""}`;
}

export async function refreshZones() {
  const { zones } = await api("/zones");
  state.zones = zones;
  const sel = document.getElementById("zoneSelect");
  sel.innerHTML = zones.map((z) => `<option value="${z.id}" ${z.id === state.zoneId ? "selected" : ""}>${esc(z.name)}</option>`).join("");
}

export function setZone(id) {
  state.zoneId = Number(id);
  storeSet("soil.zone", String(id));
  document.getElementById("zoneSelect").value = String(id);
  connectStream();
}

let es = null;
function connectStream() {
  if (es) es.close();
  const live = document.getElementById("live");
  es = new EventSource(`/api/v1/stream?zone_id=${state.zoneId}`);
  es.addEventListener("hello", () => live.classList.add("on"));
  es.onerror = () => live.classList.remove("on");
  es.addEventListener("reading", (ev) => {
    const d = JSON.parse(ev.data);
    if (d.zone_id !== state.zoneId) return;
    if (state.view === "dashboard") render();
    else toast(t("new_reading"));
  });
  es.addEventListener("zone", () => { if (state.view === "dashboard") render(); });
}

let renderSeq = 0;
export async function render() {
  const [, rawView, rawQs] = location.hash.match(/^#\/([a-z]+)\??(.*)$/) || [null, "dashboard", ""];
  state.view = VIEWS[rawView] ? rawView : "dashboard";
  state.params = new URLSearchParams(rawQs || "");
  document.querySelectorAll("#tabs a").forEach((a) => a.classList.toggle("active", a.dataset.view === state.view));
  const el = document.getElementById("view");
  const seq = ++renderSeq;
  if (!el.dataset.view || el.dataset.view !== state.view) el.innerHTML = `<div class="empty">${esc(t("loading"))}</div>`;
  el.dataset.view = state.view;
  el.onclick = null;
  el.onchange = null;
  try {
    await VIEWS[state.view](el, { seq, isCurrent: () => seq === renderSeq });
  } catch (err) {
    if (seq === renderSeq) el.innerHTML = `<div class="card"><b>${esc(t("error"))}:</b> ${esc(err.message)}</div>`;
    console.error(err);
  }
}

async function boot() {
  applyStatic();
  const theme = storeGet("soil.theme", "");
  if (theme) document.documentElement.dataset.theme = theme;
  state.meta = await api("/meta");
  const saved = Number(storeGet("soil.zone", "0"));
  await refreshZones();
  state.zoneId = state.zones.some((z) => z.id === saved) ? saved : state.zones[0]?.id;
  setZone(state.zoneId);
  document.getElementById("zoneSelect").addEventListener("change", (e) => { setZone(e.target.value); render(); });
  document.getElementById("langBtn").addEventListener("click", () => { setLang(getLang() === "ar" ? "en" : "ar"); render(); });
  document.getElementById("themeBtn").addEventListener("click", () => {
    const dark = getComputedStyle(document.documentElement).colorScheme === "dark";
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    storeSet("soil.theme", next);
  });
  window.addEventListener("hashchange", render);
  if (!location.hash) location.hash = "#/dashboard";
  else render();
}

boot().catch((e) => {
  document.getElementById("view").innerHTML = `<div class="card">Failed to start: ${esc(e.message)}</div>`;
});
