const MAX_FILE_SIZE = 30 * 1024 * 1024;
const POLL_INTERVAL = 700;

const elements = {
  fileInput: document.querySelector("#file-input"),
  dropZone: document.querySelector("#drop-zone"),
  selectButton: document.querySelector("#select-button"),
  fileCard: document.querySelector("#file-card"),
  fileName: document.querySelector("#file-name"),
  fileMeta: document.querySelector("#file-meta"),
  removeButton: document.querySelector("#remove-button"),
  convertButton: document.querySelector("#convert-button"),
  formError: document.querySelector("#form-error"),
  statusBadge: document.querySelector("#status-badge"),
  statusMessage: document.querySelector("#status-message"),
  progressTrack: document.querySelector("[role='progressbar']"),
  progressBar: document.querySelector("#progress-bar"),
  progressText: document.querySelector("#progress-text"),
  pageText: document.querySelector("#page-text"),
  successPanel: document.querySelector("#success-panel"),
  downloadLink: document.querySelector("#download-link"),
  errorPanel: document.querySelector("#error-panel"),
  errorMessage: document.querySelector("#error-message"),
  retryButton: document.querySelector("#retry-button"),
};

let selectedFile = null;
let busy = false;

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function setFormError(message = "") {
  elements.formError.textContent = message;
  elements.formError.hidden = !message;
}

function setStatus(badge, title, detail, kind = "") {
  elements.statusBadge.textContent = badge;
  elements.statusMessage.className = `status-message ${kind}`.trim();
  elements.statusMessage.innerHTML = "";
  const strong = document.createElement("strong");
  const span = document.createElement("span");
  strong.textContent = title;
  span.textContent = detail;
  elements.statusMessage.append(strong, span);
}

function setProgress(value, current = 0, total = 0) {
  const safeValue = Math.max(0, Math.min(100, Number(value) || 0));
  elements.progressBar.style.width = `${safeValue}%`;
  elements.progressTrack.setAttribute("aria-valuenow", String(safeValue));
  elements.progressText.textContent = `${safeValue}%`;
  elements.pageText.textContent = total ? `${current} / ${total} 页` : "— / — 页";
}

function clearResults() {
  elements.successPanel.hidden = true;
  elements.errorPanel.hidden = true;
  elements.downloadLink.removeAttribute("href");
}

function selectFile(file) {
  selectedFile = null;
  elements.fileInput.value = "";
  elements.fileCard.hidden = true;
  elements.convertButton.disabled = true;
  setFormError();
  clearResults();
  if (!file || !file.name.toLowerCase().endsWith(".pdf")) {
    setFormError("请选择 PDF 文件");
    return;
  }
  if (file.size > MAX_FILE_SIZE) {
    setFormError("PDF 文件不能超过 30 MB");
    return;
  }
  selectedFile = file;
  elements.fileName.textContent = file.name;
  elements.fileMeta.textContent = `${formatBytes(file.size)} · 已准备`;
  elements.fileCard.hidden = false;
  elements.convertButton.disabled = false;
  setStatus("READY", "文件已准备", "点击“开始转换”后自动识别文档", "ready");
  setProgress(0);
}

function resetFile() {
  selectedFile = null;
  elements.fileInput.value = "";
  elements.fileCard.hidden = true;
  elements.convertButton.disabled = true;
  setFormError();
  clearResults();
  setStatus("IDLE", "等待选择文件", "选择一个 PDF 后即可开始");
  setProgress(0);
}

function setBusy(value) {
  busy = value;
  elements.convertButton.disabled = value || !selectedFile;
  elements.removeButton.disabled = value;
  elements.dropZone.classList.toggle("busy", value);
  elements.convertButton.querySelector("span").textContent = value ? "正在转换…" : "开始转换";
}

async function readError(response) {
  try {
    const body = await response.json();
    return body.detail || body.error || "请求失败，请稍后重试";
  } catch (_) {
    return "请求失败，请稍后重试";
  }
}

function redirectIfUnauthorized(response) {
  if (response.status === 401) {
    window.location.assign("/login");
    return true;
  }
  return false;
}

async function pollTask(taskId) {
  while (busy) {
    const response = await fetch(`/api/tasks/${taskId}`, { cache: "no-store" });
    if (redirectIfUnauthorized(response)) return;
    if (response.status === 404) {
      throw new Error("任务已过期或服务刚刚重启，请重新上传文件");
    }
    if (!response.ok) throw new Error(await readError(response));
    const task = await response.json();
    setProgress(task.progress, task.current_page, task.total_pages);

    if (task.state === "completed") {
      setBusy(false);
      setStatus("DONE", "转换完成", "Word 文档已经生成，可以下载", "done");
      elements.downloadLink.href = `/api/tasks/${taskId}/download`;
      elements.successPanel.hidden = false;
      return;
    }
    if (task.state === "failed") {
      throw new Error(task.error || "转换失败，请检查 PDF 文件");
    }

    const pageDetail = task.total_pages
      ? `正在处理第 ${task.current_page || 1} / ${task.total_pages} 页`
      : "正在分析 PDF 页面";
    setStatus("RUNNING", "正在转换", pageDetail);
    await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL));
  }
}

async function convert() {
  if (!selectedFile || busy) return;
  setFormError();
  clearResults();
  setBusy(true);
  setProgress(0);
  setStatus("UPLOADING", "正在上传到转换服务", "文件只在本次任务中临时处理");

  const form = new FormData();
  form.append("file", selectedFile);
  try {
    const response = await fetch("/api/convert", { method: "POST", body: form });
    if (redirectIfUnauthorized(response)) return;
    if (!response.ok) throw new Error(await readError(response));
    const task = await response.json();
    setStatus("RUNNING", "正在转换", "正在读取 PDF 页面");
    await pollTask(task.task_id);
  } catch (error) {
    setBusy(false);
    setStatus("ERROR", "转换没有完成", "请查看下方错误信息");
    elements.errorMessage.textContent = error.message || "转换失败，请稍后重试";
    elements.errorPanel.hidden = false;
  }
}

elements.selectButton.addEventListener("click", (event) => {
  event.stopPropagation();
  elements.fileInput.click();
});
elements.dropZone.addEventListener("click", () => !busy && elements.fileInput.click());
elements.dropZone.addEventListener("keydown", (event) => {
  if (!busy && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    elements.fileInput.click();
  }
});
elements.fileInput.addEventListener("change", () => selectFile(elements.fileInput.files[0]));
elements.removeButton.addEventListener("click", resetFile);
elements.convertButton.addEventListener("click", convert);
elements.retryButton.addEventListener("click", convert);

for (const eventName of ["dragenter", "dragover"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    if (!busy) elements.dropZone.classList.add("dragging");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  elements.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.dropZone.classList.remove("dragging");
  });
}
elements.dropZone.addEventListener("drop", (event) => {
  if (!busy) selectFile(event.dataTransfer.files[0]);
});
