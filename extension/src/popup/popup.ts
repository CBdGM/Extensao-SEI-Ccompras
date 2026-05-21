import { SEI_PROCESS_URL_PATTERNS } from "../shared/constants";

async function init() {
  // Check auth status from service worker
  const settings = await chrome.runtime.sendMessage({ type: "GET_SETTINGS" });
  const authBadge = document.getElementById("auth-status");
  if (authBadge) {
    authBadge.textContent = settings.isAuthenticated ? "Autenticado" : "Desconectado";
    authBadge.className = `popup-badge ${settings.isAuthenticated ? "popup-badge-ok" : "popup-badge-off"}`;
  }

  // Check if the active tab is a SEI process page.
  // Use lastFocusedWindow to avoid picking up the popup window itself.
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  const tabId = tab?.id;
  const isSei = tab?.url
    ? SEI_PROCESS_URL_PATTERNS.some((p) => p.test(tab.url!))
    : false;

  const pageStatus = document.getElementById("page-status");
  const openSidebarBtn = document.getElementById("btn-open-sidebar");

  if (isSei) {
    if (pageStatus) pageStatus.textContent = "Processo SEI detectado. Abra o painel para integrar.";
    if (openSidebarBtn) openSidebarBtn.style.display = "block";
  }

  openSidebarBtn?.addEventListener("click", () => {
    // Send directly to the content script — bypasses the service worker
    // to avoid the currentWindow ambiguity when the popup is closing.
    if (tabId) chrome.tabs.sendMessage(tabId, { type: "OPEN_SIDEBAR" });
    window.close();
  });

  document.getElementById("btn-open-middleware")?.addEventListener("click", async () => {
    window.open(settings.middlewareUrl, "_blank");
  });
}

document.addEventListener("DOMContentLoaded", init);
