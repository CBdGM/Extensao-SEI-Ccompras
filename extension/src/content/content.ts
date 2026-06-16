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
  } else {
    const wrapper = document.getElementById(SIDEBAR_ID);
    if (wrapper) wrapper.style.display = "";
  }
  sidebarVisible = true;
  pushSeiBodyRight(true);
  // Only send context if the iframe has already finished loading once.
  // On first open, the load event will handle it.
  if (sidebarLoaded) updateSidebarContext();
}

function closeSidebar() {
  const wrapper = document.getElementById(SIDEBAR_ID);
  if (wrapper) wrapper.style.display = "none";
  sidebarVisible = false;
  pushSeiBodyRight(false);
}

function createSidebar() {
  let sidebarUrl: string;
  try {
    sidebarUrl = chrome.runtime.getURL("sidebar.html");
  } catch {
    // Extension was reloaded while this tab was open — context is orphaned.
    const btn = document.getElementById(BUTTON_ID);
    if (btn) {
      btn.title = "Extensão atualizada — recarregue a página (F5)";
      btn.style.opacity = "0.5";
    }
    console.warn("[ComprasSEI] Contexto da extensão inválido. Recarregue a página (F5).");
    return;
  }

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

  // Handle locally — no relay to service worker needed
  if (type === "CLOSE_SIDEBAR") {
    closeSidebar();
    return;
  }
  if (type === "REFRESH_SEI_TREE") {
    reloadSeiTree();
    return;
  }

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
// SEI tree refresh
// ──────────────────────────────────────────────

function reloadSeiTree() {
  const frames = document.querySelectorAll<HTMLIFrameElement>("iframe");
  // Log all iframes to help diagnose which one is the tree
  console.debug("[ComprasSEI] iframes na página:", Array.from(frames).map(f => ({
    name: f.name, src: f.src, id: f.id,
  })));

  for (const frame of Array.from(frames)) {
    const src = frame.src || "";
    const name = (frame.name || frame.id || "").toLowerCase();

    const isTree =
      src.includes("arvore_visualizar") ||
      src.includes("arvore_procedimento") ||
      src.includes("arvore") ||
      name.includes("arvore") ||
      name === "ifrarvore" ||
      name === "ifrtree";

    if (isTree) {
      console.debug("[ComprasSEI] Recarregando iframe da árvore:", src || name);
      // src reassignment works even cross-origin (unlike location.reload())
      frame.src = src;
      return;
    }
  }

  // Fallback: reload all iframes except our own sidebar
  // (covers SEI layouts where tree iframe has unusual naming)
  const sidebarWrapper = document.getElementById("compras-sei-sidebar");
  let reloaded = false;
  for (const frame of Array.from(frames)) {
    if (sidebarWrapper?.contains(frame)) continue; // skip our sidebar
    const src = frame.src || "";
    if (src) {
      console.debug("[ComprasSEI] Fallback — recarregando iframe:", src);
      frame.src = src;
      reloaded = true;
      break; // reload just the first non-sidebar iframe (likely the tree)
    }
  }

  if (!reloaded) {
    console.debug("[ComprasSEI] Nenhum iframe encontrado para recarregar");
  }
}

// ──────────────────────────────────────────────
// Bootstrap
// ──────────────────────────────────────────────

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
