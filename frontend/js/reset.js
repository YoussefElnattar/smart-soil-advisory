// "Reset zone data" button + confirmation dialog, shared by several views.
import { api } from "./api.js";
import { state, refreshZones } from "./app.js";
import { t } from "./i18n.js";
import { esc, toast } from "./ui.js";

const PARTS = [
  ["readings", "reset_readings"],
  ["alerts", "reset_alerts"],
  ["prescriptions", "reset_rx"],
  ["lab", "reset_lab"],
];

export function resetButton(extraClass = "") {
  return `<button type="button" class="btn danger ${extraClass}" data-reset-zone>↺ ${esc(t("reset_btn"))}</button>`;
}

/** Wire every [data-reset-zone] button inside `root`; `onDone` runs after a successful reset. */
export function bindReset(root, onDone) {
  root.querySelectorAll("[data-reset-zone]").forEach((btn) => {
    btn.addEventListener("click", () => openDialog(onDone));
  });
}

function openDialog(onDone) {
  document.getElementById("resetDlg")?.remove();
  const zone = state.zones.find((z) => z.id === state.zoneId);
  const dlg = document.createElement("dialog");
  dlg.id = "resetDlg";
  dlg.className = "dialog";
  dlg.innerHTML = `<form method="dialog" class="stack">
      <h3>↺ ${esc(t("reset_title"))}</h3>
      <p><b>${esc(zone?.name || "")}</b></p>
      <p class="muted">${esc(t("reset_intro"))}</p>
      <div class="stack">${PARTS.map(([k, key]) => `<label class="row" style="gap:8px"><input type="checkbox" name="${k}" checked> ${esc(t(key))}</label>`).join("")}</div>
      <p class="note">${esc(t("reset_keep"))}</p>
      <div class="row" style="justify-content:flex-end">
        <button class="btn" value="cancel">${esc(t("cancel"))}</button>
        <button class="btn danger" value="confirm" id="resetGo">${esc(t("reset_confirm"))}</button>
      </div>
    </form>`;
  document.body.appendChild(dlg);
  dlg.addEventListener("close", async () => {
    const confirmed = dlg.returnValue === "confirm";
    const form = dlg.querySelector("form");
    const body = Object.fromEntries(PARTS.map(([k]) => [k, form.elements[k].checked]));
    dlg.remove();
    if (!confirmed || !Object.values(body).some(Boolean)) return;
    try {
      const r = await api(`/zones/${state.zoneId}/reset`, { method: "POST", body });
      await refreshZones();
      const n = Object.values(r.deleted).reduce((a, b) => a + b, 0);
      toast(`${t("reset_done")} (${n})`);
      onDone?.();
    } catch (err) {
      toast(err.message);
    }
  });
  dlg.showModal();
}
