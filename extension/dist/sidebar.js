const API_BASE = "/api/v1";
let requestCounter = 0;
const pendingRequests = /* @__PURE__ */ new Map();
function sendToBackground(type, payload) {
  return new Promise((resolve) => {
    const requestId = `req_${++requestCounter}`;
    pendingRequests.set(requestId, resolve);
    window.parent.postMessage({ type, payload, requestId }, "*");
    setTimeout(() => {
      if (pendingRequests.has(requestId)) {
        pendingRequests.delete(requestId);
        resolve({ ok: false, error: "Timeout — recarregue a página." });
      }
    }, 3e4);
  });
}
window.addEventListener("message", (event) => {
  const { type, payload, requestId } = event.data ?? {};
  if (!requestId) {
    if (type === "SEI_CONTEXT") handleSeiContext(payload);
    return;
  }
  const resolver = pendingRequests.get(requestId);
  if (resolver) {
    pendingRequests.delete(requestId);
    resolver(payload);
  }
});
async function api(method, path, body) {
  return sendToBackground("API_REQUEST", {
    method,
    path: `${API_BASE}${path}`,
    body
  });
}
const state = {
  seiContext: null,
  isAuthenticated: false,
  middlewareUrl: "http://localhost:8000",
  frontendUrl: "http://localhost:5173",
  seiExternalSeriesId: "",
  process: null,
  artifacts: [],
  document: null,
  activeTab: "processo"
};
let _authReady = false;
let _autoQueried = false;
async function tryAutoQuery() {
  if (_autoQueried || !_authReady || !state.isAuthenticated) return;
  if (!state.seiContext?.numeroProcesso) return;
  _autoQueried = true;
  const numeroProcesso = state.seiContext.numeroProcesso;
  const numInput = el("input-numero-processo");
  if (numInput) numInput.value = numeroProcesso;
  const cached = await sendToBackground(
    "GET_CACHED_PROCESS",
    { numeroProcesso }
  );
  if (cached?.data) {
    state.process = cached.data;
    renderProcess();
    const pidField = el("import-process-id");
    if (pidField) pidField.value = state.process.id;
    await Promise.all([loadArtifacts(), loadDocument()]);
    consultarProcesso().catch(() => {
    });
    return;
  }
  const dbRes = await api(
    "GET",
    `/sei-processes/?numero_processo=${encodeURIComponent(numeroProcesso)}&limit=1`
  );
  if (dbRes.ok && dbRes.data && dbRes.data.length > 0) {
    state.process = dbRes.data[0];
    renderProcess();
    const pidField = el("import-process-id");
    if (pidField) pidField.value = state.process.id;
    sendToBackground("CACHE_PROCESS", {
      numeroProcesso,
      processData: state.process
    });
    await Promise.all([loadArtifacts(), loadDocument()]);
  }
  consultarProcesso().catch(() => {
  });
}
function el(id) {
  return document.getElementById(id);
}
function showSection(id) {
  document.querySelectorAll(".tab-panel").forEach((p) => p.style.display = "none");
  const panel = el(id);
  if (panel) panel.style.display = "block";
}
function setLoading(on) {
  const s = el("spinner");
  if (s) s.style.display = on ? "flex" : "none";
}
function showError(msg) {
  const b = el("error-banner");
  if (!b) return;
  if (msg) {
    b.textContent = msg;
    b.style.display = "block";
  } else b.style.display = "none";
}
async function checkAuth() {
  const result = await sendToBackground("GET_SETTINGS");
  state.isAuthenticated = result.isAuthenticated ?? false;
  state.middlewareUrl = result.middlewareUrl ?? "http://localhost:8000";
  state.frontendUrl = result.frontendUrl ?? "http://localhost:5173";
  state.seiExternalSeriesId = result.seiExternalSeriesId ?? "";
  _authReady = true;
  renderAuthStatus();
  await tryAutoQuery();
}
function renderAuthStatus() {
  const badge = el("auth-badge");
  const loginSec = el("login-section");
  const logoutBtn = el("btn-logout");
  if (badge) {
    badge.textContent = state.isAuthenticated ? "Autenticado" : "Desconectado";
    badge.className = `auth-badge ${state.isAuthenticated ? "auth-ok" : "auth-off"}`;
  }
  if (loginSec) loginSec.style.display = state.isAuthenticated ? "none" : "block";
  if (logoutBtn) logoutBtn.style.display = state.isAuthenticated ? "inline-flex" : "none";
}
async function handleLogin(e) {
  e.preventDefault();
  const email = el("input-email").value.trim();
  const password = el("input-password").value;
  if (!email || !password) return;
  setLoading(true);
  showError(null);
  const res = await api(
    "POST",
    "/auth/login",
    { email, password }
  );
  setLoading(false);
  if (!res.ok || !res.data?.access_token) {
    showError(res.error ?? "E-mail ou senha incorretos");
    return;
  }
  await sendToBackground("SET_TOKEN", res.data);
  state.isAuthenticated = true;
  renderAuthStatus();
}
async function handleLogout() {
  await sendToBackground("CLEAR_TOKEN");
  state.isAuthenticated = false;
  state.process = null;
  state.artifacts = [];
  state.document = null;
  renderAuthStatus();
  renderProcess();
  renderArtifacts();
  renderDocument();
}
function handleSeiContext(ctx) {
  state.seiContext = ctx;
  el("sei-numero").textContent = ctx.numeroProcesso ?? "Não identificado";
  el("sei-url").textContent = ctx.idProcedimento ? `ID: ${ctx.idProcedimento}` : "";
  if (ctx.numeroProcesso) {
    const numInput = el("input-numero-processo");
    if (numInput && !numInput.value) numInput.value = ctx.numeroProcesso;
  }
  tryAutoQuery();
}
async function consultarProcesso() {
  if (!state.isAuthenticated) {
    showError("Faça login primeiro.");
    return;
  }
  const numInput = el("input-numero-processo");
  const numeroProcesso = numInput?.value.trim();
  if (!numeroProcesso) {
    showError("Informe o número do processo.");
    return;
  }
  setLoading(true);
  showError(null);
  const res = await api(
    "POST",
    "/sei-processes/query",
    { numero_processo: numeroProcesso }
  );
  setLoading(false);
  if (!res.ok || !res.data?.process) {
    showError(res.error ?? "Erro ao consultar processo no SEI.");
    return;
  }
  state.process = res.data.process;
  renderProcess();
  const pidField = el("import-process-id");
  if (pidField) pidField.value = state.process.id;
  sendToBackground("CACHE_PROCESS", {
    numeroProcesso: state.process.numero_processo,
    processData: state.process
  });
  if (numeroProcesso !== state.process.numero_processo) {
    sendToBackground("CACHE_PROCESS", {
      numeroProcesso,
      processData: state.process
    });
  }
  loadArtifacts();
  loadDocument();
}
function renderProcess() {
  const c = el("processo-info");
  if (!c) return;
  if (!state.process) {
    c.innerHTML = `<p class="empty-state">Informe o número do processo e clique em "Consultar".</p>`;
    return;
  }
  const p = state.process;
  c.innerHTML = `
    <dl class="info-list">
      <dt>Número</dt><dd>${p.numero_processo}</dd>
      <dt>Tipo</dt><dd>${p.tipo_procedimento_nome ?? "—"}</dd>
      <dt>Especificação</dt><dd>${p.especificacao ?? "—"}</dd>
      <dt>Unidade</dt><dd>${p.unidade_sigla ?? "—"}</dd>
      <dt>Autuação</dt><dd>${p.data_autuacao ?? "—"}</dd>
      <dt>ID SEI</dt><dd>${p.id_procedimento ?? "—"}</dd>
    </dl>
  `;
}
async function handleImportSubmit(e) {
  e.preventDefault();
  if (!state.isAuthenticated) {
    showError("Faça login primeiro.");
    return;
  }
  if (!state.process) {
    showError("Consulte o processo primeiro (aba Processo).");
    return;
  }
  const fileInput = el("import-file");
  const tipoInput = el("import-tipo");
  const comprasInput = el("import-compras-id");
  const nivelInput = el("import-nivel");
  const obsInput = el("import-obs");
  const file = fileInput?.files?.[0];
  if (!file) {
    showError("Selecione um arquivo.");
    return;
  }
  if (!comprasInput?.value.trim()) {
    showError("Informe o identificador do Compras.gov.br.");
    return;
  }
  setLoading(true);
  showError(null);
  const base64 = await fileToBase64(file);
  const res = await api("POST", "/artifacts/", {
    sei_process_id: state.process.id,
    tipo_artefato: tipoInput?.value,
    identificador_compras: comprasInput?.value.trim(),
    nivel_acesso: nivelInput?.value,
    observacao: obsInput?.value || null,
    filename: file.name,
    mime_type: file.type || "application/octet-stream",
    file_base64: base64
  });
  setLoading(false);
  if (!res.ok || !res.data) {
    showError(res.error ?? "Erro ao enviar artefato.");
    return;
  }
  state.artifacts = [res.data, ...state.artifacts];
  renderArtifacts();
  if (fileInput) fileInput.value = "";
}
function showConfirm(message, onConfirm) {
  const existing = document.getElementById("confirm-overlay");
  if (existing) existing.remove();
  const overlay = document.createElement("div");
  overlay.id = "confirm-overlay";
  overlay.className = "confirm-overlay";
  overlay.innerHTML = `
    <div class="confirm-box">
      <p class="confirm-msg">${message}</p>
      <div class="confirm-actions">
        <button class="btn btn-danger btn-sm" id="confirm-ok">Confirmar</button>
        <button class="btn btn-secondary btn-sm" id="confirm-cancel">Cancelar</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  document.getElementById("confirm-ok").addEventListener("click", () => {
    overlay.remove();
    onConfirm();
  });
  document.getElementById("confirm-cancel").addEventListener("click", () => overlay.remove());
}
async function deleteArtifact(artifactId) {
  if (!state.isAuthenticated) return;
  showConfirm("Remover este artefato? A exclusão é lógica e a trilha de auditoria é mantida.", async () => {
    setLoading(true);
    const res = await api("DELETE", `/artifacts/${artifactId}`);
    setLoading(false);
    if (!res.ok) {
      showError(res.error ?? "Erro ao remover artefato.");
      return;
    }
    await loadArtifacts();
  });
}
async function sendArtifactToSei(artifactId) {
  if (!state.isAuthenticated) return;
  setLoading(true);
  const body = state.seiExternalSeriesId ? { id_serie_override: state.seiExternalSeriesId } : {};
  const res = await api("POST", `/artifacts/${artifactId}/send-to-sei`, body);
  setLoading(false);
  if (!res.ok) {
    showError(res.error ?? "Erro ao enviar ao SEI.");
    return;
  }
  await loadArtifacts();
}
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
async function loadArtifacts() {
  if (!state.process) return;
  const res = await api(
    "GET",
    `/artifacts/?sei_process_id=${state.process.id}`
  );
  if (res.ok && res.data) {
    state.artifacts = res.data;
    renderArtifacts();
  }
}
function renderArtifacts() {
  const c = el("artefatos-list");
  if (!c) return;
  if (!state.artifacts.length) {
    c.innerHTML = `<p class="empty-state">Nenhum artefato importado para este processo.</p>`;
    return;
  }
  const seiLabel = {
    not_sent: "Não enviado ao SEI",
    pending: "Pendente",
    file_uploaded_document_failed: "Erro parcial",
    sent: "Enviado ao SEI",
    error: "Erro no envio"
  };
  c.innerHTML = state.artifacts.map((a) => `
    <div class="artefato-item">
      <div class="artefato-nome">${a.original_filename}</div>
      <div class="artefato-meta">
        <span class="tipo-pill">${a.tipo_artefato}</span>
        <span class="status-pill status-${a.send_to_sei_status}">${seiLabel[a.send_to_sei_status] ?? a.send_to_sei_status}</span>
        ${a.sei_document_number ? `<span class="doc-sei">Doc SEI: ${a.sei_document_number}</span>` : ""}
      </div>
      ${a.send_to_sei_error ? `<div class="artefato-erro">${a.send_to_sei_error}</div>` : ""}
      <div class="artefato-actions">
        ${a.send_to_sei_status === "not_sent" || a.send_to_sei_status === "error" || a.send_to_sei_status === "file_uploaded_document_failed" ? `<button class="btn btn-primary btn-sm" data-action="send-to-sei" data-artifact-id="${a.id}">Enviar ao SEI</button>` : ""}
        <button class="btn btn-icon btn-sm btn-danger" data-action="delete-artifact" data-artifact-id="${a.id}" title="Excluir artefato">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="pointer-events:none">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
          </svg>
        </button>
      </div>
    </div>
  `).join("");
  c.querySelectorAll('[data-action="send-to-sei"]').forEach((btn) => {
    btn.addEventListener("click", () => sendArtifactToSei(btn.dataset.artifactId));
  });
  c.querySelectorAll('[data-action="delete-artifact"]').forEach((btn) => {
    btn.addEventListener("click", () => deleteArtifact(btn.dataset.artifactId));
  });
}
async function loadDocument() {
  if (!state.process) return;
  const res = await api(
    "GET",
    `/documents/?sei_process_id=${state.process.id}`
  );
  if (res.ok && res.data && res.data.length > 0) {
    state.document = res.data[0];
    renderDocument();
  } else {
    state.document = null;
    renderDocument();
  }
}
async function viewDocument() {
  if (!state.document) return;
  setLoading(true);
  const res = await sendToBackground(
    "GET_HTML",
    { path: `${API_BASE}/documents/${state.document.id}/html` }
  );
  setLoading(false);
  if (!res.ok || !res.data) {
    showError(res.error ?? "Erro ao carregar comprovação.");
    return;
  }
  const blob = new Blob([res.data], { type: "text/html; charset=utf-8" });
  const blobUrl = URL.createObjectURL(blob);
  const win = window.open(blobUrl, "_blank");
  if (win) {
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1e4);
  } else {
    URL.revokeObjectURL(blobUrl);
    showError("O navegador bloqueou a janela. Permita pop-ups para esta extensao.");
  }
}
async function gerarComprovacao() {
  if (!state.process) {
    showError("Consulte o processo primeiro.");
    return;
  }
  setLoading(true);
  showError(null);
  const res = await api("POST", "/documents/generate", {
    sei_process_id: state.process.id
  });
  setLoading(false);
  if (!res.ok || !res.data) {
    showError(res.error ?? "Erro ao gerar comprovação.");
    return;
  }
  state.document = res.data;
  renderDocument();
}
async function enviarComprovacaoSei() {
  if (!state.document) return;
  setLoading(true);
  const res = await api("POST", `/documents/${state.document.id}/send-to-sei`, {});
  setLoading(false);
  if (!res.ok) {
    showError(res.error ?? "Erro ao enviar ao SEI.");
    return;
  }
  if (res.data) {
    state.document = res.data;
    renderDocument();
  }
}
function renderDocument() {
  const c = el("comprovacao-info");
  if (!c) return;
  if (!state.process) {
    c.innerHTML = `<p class="empty-state">Consulte o processo primeiro.</p>`;
    return;
  }
  if (!state.document) {
    c.innerHTML = `
      <p class="empty-state">Nenhum Documento de Comprovação gerado.</p>
      <button class="btn btn-primary btn-sm" id="btn-gerar">Gerar Comprovação</button>
    `;
    el("btn-gerar")?.addEventListener("click", gerarComprovacao);
    return;
  }
  const d = state.document;
  const docLabel = {
    not_generated: "Não gerado",
    generating: "Gerando",
    generated: "Gerado",
    error: "Erro",
    needs_reissue: "Reemissão necessária"
  };
  const seiLabel = {
    not_sent: "Não enviado",
    pending: "Pendente",
    sent: "Enviado ao SEI",
    error: "Erro",
    file_uploaded_document_failed: "Erro parcial"
  };
  c.innerHTML = `
    <dl class="info-list">
      <dt>Status doc</dt><dd><span class="status-pill status-${d.status}">${docLabel[d.status] ?? d.status}</span></dd>
      <dt>SEI</dt><dd><span class="status-pill status-${d.send_to_sei_status}">${seiLabel[d.send_to_sei_status] ?? d.send_to_sei_status}</span></dd>
      ${d.sei_document_number ? `<dt>Número doc</dt><dd>${d.sei_document_number}</dd>` : ""}
      <dt>Versão</dt><dd>${d.version_number}</dd>
    </dl>
    <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
      <button class="btn btn-secondary btn-sm" id="btn-regenerar">Regerar</button>
      <button class="btn btn-secondary btn-sm" id="btn-visualizar-comprov">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:4px">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
        </svg>
        Visualizar
      </button>
      ${d.send_to_sei_status === "not_sent" || d.send_to_sei_status === "error" || d.send_to_sei_status === "file_uploaded_document_failed" || d.status === "needs_reissue" ? `<button class="btn btn-primary btn-sm" id="btn-enviar-comprov">${d.status === "needs_reissue" ? "Reenviar ao SEI" : "Enviar ao SEI"}</button>` : ""}
    </div>
  `;
  el("btn-regenerar")?.addEventListener("click", gerarComprovacao);
  el("btn-visualizar-comprov")?.addEventListener("click", viewDocument);
  el("btn-enviar-comprov")?.addEventListener("click", enviarComprovacaoSei);
}
async function loadAuditLog() {
  if (!state.process) {
    renderAuditLog([]);
    return;
  }
  const res = await api("GET", `/audit/process/${state.process.id}`);
  if (res.ok && res.data) renderAuditLog(res.data);
}
const ACTION_LABELS = {
  ARTIFACT_UPLOADED: "Artefato importado",
  ARTIFACT_SENT_TO_SEI: "Artefato enviado ao SEI",
  ARTIFACT_DELETED: "Artefato excluído",
  ARTIFACT_DOWNLOADED: "Artefato baixado",
  DOCUMENT_GENERATED: "Comprovação gerada",
  DOCUMENT_REBUILT: "Comprovação reconstruída",
  DOCUMENT_SENT_TO_SEI: "Comprovação enviada ao SEI",
  DOCUMENT_DELETED: "Comprovação excluída",
  DOCUMENT_VIEWED: "Comprovação visualizada",
  DOCUMENT_PDF_DOWNLOADED: "PDF baixado",
  SEI_PROCESS_QUERIED: "Processo consultado no SEI",
  LOGIN_SUCCESS: "Login realizado",
  LOGOUT: "Logout"
};
function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  } catch {
    return iso;
  }
}
function renderAuditLog(entries) {
  const c = el("historico-list");
  if (!c) return;
  if (!state.process) {
    c.innerHTML = `<p class="empty-state">Consulte o processo primeiro.</p>`;
    return;
  }
  if (!entries.length) {
    c.innerHTML = `<p class="empty-state">Nenhuma ação registrada para este processo.</p>`;
    return;
  }
  c.innerHTML = entries.map((e) => `
    <div class="audit-item">
      <div class="audit-action">${ACTION_LABELS[e.action] ?? e.action}</div>
      <div class="audit-meta">
        <span class="audit-user">${e.user_name ?? "—"}</span>
        <span class="audit-date">${formatDate(e.created_at)}</span>
      </div>
      ${e.metadata_json?.original_filename ? `<div class="audit-detail">${e.metadata_json.original_filename}</div>` : e.metadata_json?.numero_processo ? `<div class="audit-detail">${e.metadata_json.numero_processo}</div>` : ""}
    </div>
  `).join("");
}
async function saveConfig(e) {
  e.preventDefault();
  const middlewareUrl = el("config-middleware-url").value.trim();
  const frontendUrl = el("config-frontend-url").value.trim();
  const seiExternalSeriesId = el("config-sei-series-id").value.trim();
  await sendToBackground("SAVE_SETTINGS", { middlewareUrl, frontendUrl, seiExternalSeriesId });
  state.middlewareUrl = middlewareUrl;
  state.frontendUrl = frontendUrl;
  state.seiExternalSeriesId = seiExternalSeriesId;
  const saved = el("config-saved");
  if (saved) {
    saved.style.display = "inline";
    setTimeout(() => saved.style.display = "none", 2e3);
  }
}
function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll(".tab-btn").forEach(
    (btn) => btn.classList.toggle("active", btn.dataset.tab === tab)
  );
  showSection(`panel-${tab}`);
  if (tab === "importar" && state.process) loadArtifacts();
  if (tab === "comprovacao") {
    if (state.process) loadDocument();
    else renderDocument();
  }
  if (tab === "historico") loadAuditLog();
  if (tab === "config") {
    const mu = el("config-middleware-url");
    if (mu) mu.value = state.middlewareUrl;
    const fu = el("config-frontend-url");
    if (fu) fu.value = state.frontendUrl;
    const su = el("config-sei-series-id");
    if (su) su.value = state.seiExternalSeriesId;
  }
}
document.addEventListener("DOMContentLoaded", async () => {
  await checkAuth();
  document.querySelectorAll(".tab-btn").forEach(
    (btn) => btn.addEventListener("click", () => switchTab(btn.dataset.tab))
  );
  el("btn-consultar")?.addEventListener("click", consultarProcesso);
  el("login-form")?.addEventListener("submit", handleLogin);
  el("btn-logout")?.addEventListener("click", handleLogout);
  el("import-form")?.addEventListener("submit", handleImportSubmit);
  el("config-form")?.addEventListener("submit", saveConfig);
  el("btn-open-full")?.addEventListener(
    "click",
    () => window.open(state.frontendUrl, "_blank")
  );
  switchTab("processo");
});
//# sourceMappingURL=sidebar.js.map
