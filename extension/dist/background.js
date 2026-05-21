import { b as STORAGE_KEYS, a as DEFAULT_MIDDLEWARE_URL, D as DEFAULT_FRONTEND_URL } from "./chunks/constants.js";
async function getSettings() {
  const result = await chrome.storage.local.get([
    STORAGE_KEYS.MIDDLEWARE_URL,
    STORAGE_KEYS.FRONTEND_URL,
    STORAGE_KEYS.SEI_EXTERNAL_SERIES_ID,
    STORAGE_KEYS.JWT_TOKEN,
    STORAGE_KEYS.TOKEN_EXPIRES_AT
  ]);
  return {
    middlewareUrl: result[STORAGE_KEYS.MIDDLEWARE_URL] ?? DEFAULT_MIDDLEWARE_URL,
    frontendUrl: result[STORAGE_KEYS.FRONTEND_URL] ?? DEFAULT_FRONTEND_URL,
    seiExternalSeriesId: result[STORAGE_KEYS.SEI_EXTERNAL_SERIES_ID] ?? "",
    jwtToken: result[STORAGE_KEYS.JWT_TOKEN],
    tokenExpiresAt: result[STORAGE_KEYS.TOKEN_EXPIRES_AT]
  };
}
async function saveSettings(partial) {
  const toSave = {};
  if (partial.middlewareUrl !== void 0)
    toSave[STORAGE_KEYS.MIDDLEWARE_URL] = partial.middlewareUrl;
  if (partial.frontendUrl !== void 0)
    toSave[STORAGE_KEYS.FRONTEND_URL] = partial.frontendUrl;
  if (partial.seiExternalSeriesId !== void 0)
    toSave[STORAGE_KEYS.SEI_EXTERNAL_SERIES_ID] = partial.seiExternalSeriesId;
  if (partial.jwtToken !== void 0)
    toSave[STORAGE_KEYS.JWT_TOKEN] = partial.jwtToken;
  if (partial.tokenExpiresAt !== void 0)
    toSave[STORAGE_KEYS.TOKEN_EXPIRES_AT] = partial.tokenExpiresAt;
  await chrome.storage.local.set(toSave);
}
async function clearToken() {
  await chrome.storage.local.remove([
    STORAGE_KEYS.JWT_TOKEN,
    STORAGE_KEYS.TOKEN_EXPIRES_AT
  ]);
}
function isTokenExpired(expiresAt) {
  if (!expiresAt) return true;
  return Date.now() >= expiresAt - 3e4;
}
function isArtifactUpload(body) {
  return typeof body === "object" && body !== null && "file_base64" in body;
}
function buildFormData(b) {
  const bytes = atob(b.file_base64);
  const buf = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i);
  const blob = new Blob([buf], { type: b.mime_type || "application/octet-stream" });
  const fd = new FormData();
  fd.append("file", blob, b.filename);
  fd.append("sei_process_id", b.sei_process_id);
  fd.append("tipo_artefato", b.tipo_artefato);
  fd.append("identificador_compras", b.identificador_compras);
  fd.append("nivel_acesso", b.nivel_acesso);
  if (b.observacao) fd.append("observacao", b.observacao);
  return fd;
}
async function callMiddleware(middlewareUrl, token, method, path, body) {
  const url = `${middlewareUrl.replace(/\/$/, "")}${path}`;
  const headers = { Accept: "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let fetchBody;
  if (isArtifactUpload(body)) {
    fetchBody = buildFormData(body);
  } else if (body !== void 0) {
    headers["Content-Type"] = "application/json";
    fetchBody = JSON.stringify(body);
  }
  try {
    const response = await fetch(url, { method, headers, body: fetchBody });
    if (response.ok) {
      const data = await response.json().catch(() => void 0);
      return { ok: true, status: response.status, data };
    }
    const raw = await response.text().catch(() => "Erro desconhecido");
    let errorMsg = raw;
    try {
      const j = JSON.parse(raw);
      if (typeof j.detail === "string") errorMsg = j.detail;
      else if (Array.isArray(j.detail))
        errorMsg = j.detail.map((e) => e.msg ?? JSON.stringify(e)).join("; ");
    } catch {
    }
    return { ok: false, status: response.status, error: errorMsg };
  } catch (err) {
    return { ok: false, status: 0, error: err instanceof Error ? err.message : "Erro de rede" };
  }
}
chrome.runtime.onMessage.addListener(
  (message, _sender, sendResponse) => {
    handleMessage(message).then(sendResponse).catch(
      (err) => sendResponse({ ok: false, error: String(err) })
    );
    return true;
  }
);
async function handleMessage(message) {
  const { type, payload } = message;
  switch (type) {
    case "GET_SETTINGS": {
      const settings = await getSettings();
      return {
        middlewareUrl: settings.middlewareUrl,
        frontendUrl: settings.frontendUrl,
        seiExternalSeriesId: settings.seiExternalSeriesId,
        isAuthenticated: !!settings.jwtToken && !isTokenExpired(settings.tokenExpiresAt)
      };
    }
    case "SAVE_SETTINGS": {
      await saveSettings(payload);
      return { ok: true };
    }
    case "SET_TOKEN": {
      const { access_token, expires_in } = payload;
      const expiresAt = expires_in ? Date.now() + expires_in * 1e3 : Date.now() + 8 * 60 * 60 * 1e3;
      await saveSettings({ jwtToken: access_token, tokenExpiresAt: expiresAt });
      return { ok: true };
    }
    case "CLEAR_TOKEN": {
      await clearToken();
      return { ok: true };
    }
    case "CACHE_PROCESS": {
      const { numeroProcesso, processData } = payload;
      const stored = await chrome.storage.local.get("processCache");
      const cache = stored["processCache"] ?? {};
      cache[numeroProcesso] = processData;
      await chrome.storage.local.set({ processCache: cache });
      return { ok: true };
    }
    case "GET_CACHED_PROCESS": {
      const { numeroProcesso } = payload;
      const stored = await chrome.storage.local.get("processCache");
      const cache = stored["processCache"] ?? {};
      return { ok: true, data: cache[numeroProcesso] ?? null };
    }
    case "GET_HTML": {
      const { path } = payload;
      const settings = await getSettings();
      if (isTokenExpired(settings.tokenExpiresAt)) {
        return { ok: false, error: "Token expirado. Faça login novamente." };
      }
      try {
        const url = `${settings.middlewareUrl.replace(/\/$/, "")}${path}`;
        const response = await fetch(url, {
          headers: { Authorization: `Bearer ${settings.jwtToken}` }
        });
        if (response.ok) {
          const html = await response.text();
          return { ok: true, data: html };
        }
        return { ok: false, error: "Erro ao carregar documento." };
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : "Erro de rede" };
      }
    }
    case "API_REQUEST": {
      const { method, path, body } = payload;
      const settings = await getSettings();
      if (!path.endsWith("/auth/login") && isTokenExpired(settings.tokenExpiresAt)) {
        return { ok: false, status: 401, error: "Token expirado. Faça login novamente." };
      }
      const result = await callMiddleware(
        settings.middlewareUrl,
        settings.jwtToken,
        method,
        path,
        body
      );
      if (result.status === 401) {
        await clearToken();
      }
      return result;
    }
    case "OPEN_SIDEBAR": {
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true
      });
      if (tab?.id) {
        await chrome.tabs.sendMessage(tab.id, { type: "OPEN_SIDEBAR" });
      }
      return { ok: true };
    }
    default:
      return { ok: false, error: `Tipo de mensagem desconhecido: ${type}` };
  }
}
chrome.runtime.onInstalled.addListener(async () => {
  const existing = await chrome.storage.local.get(STORAGE_KEYS.MIDDLEWARE_URL);
  if (!existing[STORAGE_KEYS.MIDDLEWARE_URL]) {
    await chrome.storage.local.set({
      [STORAGE_KEYS.MIDDLEWARE_URL]: DEFAULT_MIDDLEWARE_URL
    });
  }
});
//# sourceMappingURL=background.js.map
