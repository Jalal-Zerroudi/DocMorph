"use strict";

const FORMAT_LABELS = {
  pdf: "PDF", doc: "Word 97 (.doc)", docx: "Word (.docx)", xls: "Excel 97 (.xls)", xlsx: "Excel (.xlsx)",
  ppt: "PowerPoint 97 (.ppt)", pptx: "PowerPoint (.pptx)", odt: "ODT", ods: "ODS", odp: "ODP",
  txt: "Texte (.txt)", rtf: "RTF", jpg: "JPEG", png: "PNG",
};
const MODE_LABELS = { layout: "fidèle", structure: "structure", standard: "" };
const STATUS_LABELS = { queued: "En attente", running: "En cours…", done: "Terminé", failed: "Échec" };
const POLL_MS = 1500;

const $ = (sel) => document.querySelector(sel);
const dropzone = $("#dropzone");
const fileInput = $("#file-input");
const targetSelect = $("#target");
const modeField = $("#mode-field");
const modeSelect = $("#mode");
const modeHint = $("#mode-hint");
const convertBtn = $("#convert");
const tbody = $("#files tbody");

/** @type {{file: File, detection: any, error: string|null, job: any, row: HTMLTableRowElement}[]} */
let entries = [];
let pollTimer = null;
let currentBatch = null;

dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("over"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("over");
  addFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => { addFiles(fileInput.files); fileInput.value = ""; });
targetSelect.addEventListener("change", refreshControls);
modeSelect.addEventListener("change", refreshControls);
convertBtn.addEventListener("click", convert);
$("#clear").addEventListener("click", reset);

loadEngines();

async function addFiles(fileList) {
  if (currentBatch) reset();
  const added = [...fileList].map((file) => {
    const entry = { file, detection: null, error: null, job: null, row: document.createElement("tr") };
    entries.push(entry);
    tbody.appendChild(entry.row);
    render(entry);
    return entry;
  });
  $("#files").hidden = false;
  $("#controls").hidden = false;
  await Promise.all(added.map(detectEntry));
  refreshTargets();
}

async function detectEntry(entry) {
  const body = new FormData();
  body.append("file", entry.file);
  try {
    entry.detection = await api("/api/detect", { method: "POST", body });
  } catch (err) {
    entry.error = err.message;
  }
  render(entry);
}

function refreshTargets() {
  const previous = targetSelect.value;
  const targets = new Set();
  for (const e of entries) for (const t of e.detection?.targets ?? []) targets.add(t.target);
  targetSelect.replaceChildren(
    ...Object.keys(FORMAT_LABELS).filter((f) => targets.has(f)).map((f) => new Option(FORMAT_LABELS[f], f)),
  );
  if (targets.has(previous)) targetSelect.value = previous;
  refreshControls();
}

function targetInfo(entry) {
  return entry.detection?.targets.find((t) => t.target === targetSelect.value) ?? null;
}

function refreshControls() {
  const eligible = entries.filter((e) => targetInfo(e));
  const multiMode = eligible.some((e) => targetInfo(e).modes.length > 1);
  const scanned = eligible.some((e) => e.detection.pdf_kind === "scanned" && ["docx", "doc"].includes(targetSelect.value));
  modeField.hidden = !multiMode;
  modeHint.hidden = !(multiMode || scanned);
  modeHint.textContent = [
    multiMode && modeSelect.value === "layout"
      ? "Fidèle : conserve la mise en page ; les équations deviennent des images ou du texte approximatif."
      : multiMode ? "Structure : texte, titres, tableaux et équations Word modifiables ; la mise en page d'origine n'est pas reproduite. Plus lent (IA locale)." : "",
    scanned ? "Les PDF scannés passent par l'OCR (français, anglais, arabe) en mode structure." : "",
  ].filter(Boolean).join(" ");
  convertBtn.disabled = eligible.length === 0 || !!currentBatch;
  entries.forEach(render);
}

async function convert() {
  const eligible = entries.filter((e) => targetInfo(e));
  if (!eligible.length) return;
  const body = new FormData();
  eligible.forEach((e) => body.append("files", e.file));
  body.append("target", targetSelect.value);
  body.append("mode", modeField.hidden ? "auto" : modeSelect.value);
  convertBtn.disabled = true;
  try {
    const res = await api("/api/convert", { method: "POST", body });
    currentBatch = res.batch_id;
    res.jobs.forEach((job, i) => { eligible[i].job = job; render(eligible[i]); });
    poll();
  } catch (err) {
    alert(err.message);
    convertBtn.disabled = false;
  }
}

async function poll() {
  clearTimeout(pollTimer);
  if (!currentBatch) return;
  const batch = currentBatch;
  try {
    const res = await api(`/api/batches/${batch}`);
    if (batch !== currentBatch) return;
    for (const job of res.jobs) {
      const entry = entries.find((e) => e.job?.id === job.id);
      if (entry) { entry.job = job; render(entry); }
    }
    const pending = res.jobs.some((j) => j.status === "queued" || j.status === "running");
    const anyDone = res.jobs.some((j) => j.status === "done");
    $("#zip-row").hidden = pending || !anyDone || res.jobs.length < 2;
    $("#zip-link").href = `/api/batches/${batch}/zip`;
    if (pending) pollTimer = setTimeout(poll, POLL_MS);
  } catch (err) {
    pollTimer = setTimeout(poll, POLL_MS * 2);
  }
}

function render(entry) {
  const { file, detection, error, job, row } = entry;
  const cells = [document.createElement("td"), document.createElement("td"), document.createElement("td"), document.createElement("td")];
  cells[0].className = "name";
  cells[0].textContent = file.name;

  if (detection) {
    cells[1].textContent = FORMAT_LABELS[detection.format] ?? detection.format;
    if (detection.pdf_kind === "scanned") cells[1].append(tag("scanné"));
  } else if (!error) {
    cells[1].textContent = "Analyse…";
  }

  if (error) {
    setStatus(cells[2], "failed", error);
  } else if (job) {
    const mode = MODE_LABELS[job.mode_used ?? ""];
    setStatus(cells[2], job.status, job.error?.message, job.error?.detail);
    if (mode && job.status === "done") cells[2].append(tag(mode));
    if (job.status === "done") {
      const link = document.createElement("a");
      link.href = `/api/jobs/${job.id}/download`;
      link.textContent = "Télécharger";
      cells[3].appendChild(link);
    }
  } else if (detection && targetSelect.value && !targetInfo(entry)) {
    setStatus(cells[2], "skip", `Conversion vers ${FORMAT_LABELS[targetSelect.value]} non disponible pour ce fichier`);
  } else if (detection) {
    cells[2].textContent = "Prêt";
  }
  row.replaceChildren(...cells);
}

function setStatus(cell, status, message, detail) {
  cell.className = `status-${status}`;
  cell.textContent = message && status !== "done" ? message : STATUS_LABELS[status] ?? "";
  if (detail) {
    const d = document.createElement("span");
    d.className = "detail";
    d.textContent = detail.length > 300 ? `${detail.slice(0, 300)}…` : detail;
    cell.appendChild(d);
  }
}

function tag(text) {
  const span = document.createElement("span");
  span.className = "tag";
  span.textContent = text;
  return span;
}

function reset() {
  clearTimeout(pollTimer);
  entries = [];
  currentBatch = null;
  tbody.replaceChildren();
  $("#files").hidden = true;
  $("#controls").hidden = true;
  $("#zip-row").hidden = true;
  modeHint.hidden = true;
}

async function loadEngines() {
  try {
    const info = await api("/api/formats");
    const footer = $("#engines");
    const parts = [];
    if (info.structure_device) parts.push(`Mode structure : ${info.structure_device === "cuda" ? "GPU" : "CPU"}.`);
    parts.push(`Taille max : ${info.max_upload_mb} Mo par fichier.`);
    footer.textContent = parts.join(" ");
    if (info.unavailable.length) {
      const list = document.createElement("ul");
      for (const u of info.unavailable) {
        const li = document.createElement("li");
        li.textContent = `${u.engine} : ${u.reason}`;
        list.appendChild(li);
      }
      footer.append(" Moteurs indisponibles :", list);
    }
  } catch {
    /* footer stays empty if the server is unreachable */
  }
}

async function api(url, options) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : `Erreur ${res.status}`);
  }
  return data;
}
