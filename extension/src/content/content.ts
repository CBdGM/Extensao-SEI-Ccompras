import { extractSeiProcessContext, isSeiProcessPage } from "./sei-context";
import type { SeiProcessContext } from "../shared/types";

// Inlined to keep content.js free of top-level import statements.
const BUTTON_ID = "compras-sei-btn";
const SIDEBAR_ID = "compras-sei-sidebar";
const SIDEBAR_WIDTH = "420px";

let currentContext: SeiProcessContext | null = null;
let sidebarFrame: HTMLIFrameElement | null = null;
let sidebarVisible = false;
let sidebarLoaded = false;

// ──────────────────────────────────────────────
// Entry point
// ──────────────────────────────────────────────

function init() {
  if (!isSeiProcessPage()) return;

  currentContext = extractSeiProcessContext();
  injectButton();
  observeUrlChanges();

  // Listen for messages from the service worker or sidebar
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === "OPEN_SIDEBAR") openSidebar();
  });
}

// ──────────────────────────────────────────────
// Button injection
// ──────────────────────────────────────────────

function injectButton() {
  if (document.getElementById(BUTTON_ID)) return;

  const btn = document.createElement("button");
  btn.id = BUTTON_ID;
  btn.className = "compras-sei-inject-btn";
  btn.title = "Integração Compras-SEI";
  btn.innerHTML = `
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
    </svg>
    <span>Compras-SEI</span>
  `;

  btn.addEventListener("click", () => {
    if (sidebarVisible) {
      closeSidebar();
    } else {
      openSidebar();
    }
  });

  // The outer SEI frame (procedimento_trabalhar) has the navbar but not
  // #divArvoreAcoes (that lives in an inner iframe). Use the navbar right side,
  // falling back to body. The button is fixed-position so placement doesn't
  // affect the visual result.
  const toolbar =
    document.querySelector("#divInfraBarraSistemaPadraoD") ??
    document.querySelector("#divArvoreAcoes") ??
    document.querySelector(".barraComandos") ??
    document.querySelector("#divComandos") ??
    document.querySelector("body");

  if (toolbar) toolbar.prepend(btn);
}

// ──────────────────────────────────────────────
// Sidebar (iframe) management
// ──────────────────────────────────────────────

function openSidebar() {
  if (!sidebarFrame) {
    createSidebar(); // updateSidebarContext() is called by the load event
  }
  sidebarFrame!.style.display = "block";
  sidebarVisible = true;
  pushSeiBodyRight(true);
  // Only send context if the iframe has already finished loading once.
  // On first open, the load event will handle it.
  if (sidebarLoaded) updateSidebarContext();
}

function closeSidebar() {
  if (sidebarFrame) sidebarFrame.style.display = "none";
  sidebarVisible = false;
  pushSeiBodyRight(false);
}

function createSidebar() {
  const sidebarUrl = chrome.runtime.getURL("sidebar.html");

  const wrapper = document.createElement("div");
  wrapper.id = SIDEBAR_ID;
  wrapper.className = "compras-sei-sidebar-wrapper";

  const closeBtn = document.createElement("button");
  closeBtn.className = "compras-sei-sidebar-close";
  closeBtn.innerHTML = "✕";
  closeBtn.title = "Fechar painel";
  closeBtn.addEventListener("click", closeSidebar);

  sidebarFrame = document.createElement("iframe");
  sidebarFrame.src = sidebarUrl;
  sidebarFrame.className = "compras-sei-sidebar-frame";
  // No sandbox: the extension page is already sandboxed by Chrome's extension
  // security model. Adding sandbox="allow-same-origin" was causing the iframe to
  // resolve scripts relative to the SEI origin instead of chrome-extension://,
  // and making postMessage origin checks fail.

  wrapper.appendChild(closeBtn);
  wrapper.appendChild(sidebarFrame);
  document.body.appendChild(wrapper);

  sidebarFrame.addEventListener("load", () => {
    sidebarLoaded = true;
    updateSidebarContext();
  });
}

function updateSidebarContext() {
  if (!sidebarFrame?.contentWindow) return;
  // Use "*" because the iframe is our own extension page (trusted) and the
  // SEI context data is not sensitive. This avoids origin-mismatch errors.
  sidebarFrame.contentWindow.postMessage(
    { type: "SEI_CONTEXT", payload: currentContext },
    "*"
  );
}

function pushSeiBodyRight(push: boolean) {
  // Avoid breaking SEI layout — shift the main wrapper instead of body
  const mainEl =
    document.querySelector<HTMLElement>("#divConteudo") ??
    document.querySelector<HTMLElement>("#main") ??
    document.querySelector<HTMLElement>("body");
  if (mainEl) {
    mainEl.style.transition = "margin-right 0.25s ease";
    mainEl.style.marginRight = push ? SIDEBAR_WIDTH : "";
  }
}

// ──────────────────────────────────────────────
// React to SEI navigation (SPA-like behaviour inside iframes)
// ──────────────────────────────────────────────

function observeUrlChanges() {
  let lastUrl = window.location.href;

  const observer = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      handleNavigation();
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

  // Also handle popstate for regular navigation
  window.addEventListener("popstate", handleNavigation);
}

function handleNavigation() {
  if (!isSeiProcessPage()) {
    closeSidebar();
    return;
  }
  currentContext = extractSeiProcessContext();
  if (!document.getElementById(BUTTON_ID)) injectButton();
  if (sidebarVisible) updateSidebarContext();
}

// ──────────────────────────────────────────────
// Message relay: sidebar → service worker → sidebar
// The sidebar (extension page) can send messages via window.postMessage
// which the content script relays to chrome.runtime (service worker).
// ──────────────────────────────────────────────

window.addEventListener("message", async (event) => {
  // chrome.runtime.getURL throws when the extension is reloaded; guard everything
  let expectedOrigin: string;
  try {
    expectedOrigin = chrome.runtime.getURL("").replace(/\/$/, "");
  } catch {
    return; // extension context gone, nothing we can do
  }
  if (event.origin !== expectedOrigin) return;

  const { type, payload, requestId } = event.data ?? {};
  if (!type) return;

  let response: unknown;
  try {
    response = await chrome.runtime.sendMessage({ type, payload });
  } catch {
    // Extension context invalidated — extension reloaded while SEI tab was open
    response = {
      ok: false,
      error: "Extensão recarregada. Recarregue a página do SEI (F5).",
    };
  }

  try {
    if (sidebarFrame?.contentWindow) {
      sidebarFrame.contentWindow.postMessage(
        { type: `${type}_RESPONSE`, payload: response, requestId },
        "*"
      );
    }
  } catch {
    // frame gone after context invalidation, ignore
  }
});

// ──────────────────────────────────────────────
// Bootstrap
// ──────────────────────────────────────────────

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
