const SEI_PROCESSO_REGEX = /\b(\d{5}\.\d{6}\/\d{4}-\d{2})\b/;
const SEI_PROCESS_URL_PATTERNS = [
  /acao=procedimento_trabalhar/,
  /acao=arvore_visualizar/,
  /acao=procedimento_visualizar/,
  /acao=procedimento_controlar/
];
function extractSeiProcessContext() {
  const currentUrl = window.location.href;
  const pageTitle = document.title || void 0;
  const urlParams = new URLSearchParams(window.location.search);
  const idProcedimento = urlParams.get("id_procedimento") ?? void 0;
  const numeroProcesso = extractProcessNumber();
  return {
    numeroProcesso,
    idProcedimento,
    currentUrl,
    pageTitle
  };
}
function extractProcessNumber() {
  const candidateSelectors = [
    // Process header area
    "#txtNumeroProtocolo",
    "#txtNumero",
    ".protocoloNomeProcesso",
    // Tree view
    "a[href*='id_procedimento'] .titAnexo",
    "#divArvoreAcoes .protocoloArvore",
    // Page title text fallback
    "title"
  ];
  for (const selector of candidateSelectors) {
    const el = document.querySelector(selector);
    if (el) {
      const text = el.textContent ?? "";
      const match = text.match(SEI_PROCESSO_REGEX);
      if (match) return match[1];
    }
  }
  const broadSelectors = ["h1", "h2", "h3", "span", "td", "div"];
  for (const tag of broadSelectors) {
    const elements = document.querySelectorAll(tag);
    for (const el of Array.from(elements)) {
      const text = el.textContent ?? "";
      const match = text.match(SEI_PROCESSO_REGEX);
      if (match) return match[1];
    }
  }
  return void 0;
}
function isSeiProcessPage() {
  const url = window.location.href;
  return SEI_PROCESS_URL_PATTERNS.some((pattern) => pattern.test(url));
}
const BUTTON_ID = "compras-sei-btn";
const SIDEBAR_ID = "compras-sei-sidebar";
const SIDEBAR_WIDTH = "420px";
let currentContext = null;
let sidebarFrame = null;
let sidebarVisible = false;
let sidebarLoaded = false;
function init() {
  if (!isSeiProcessPage()) return;
  currentContext = extractSeiProcessContext();
  injectButton();
  observeUrlChanges();
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === "OPEN_SIDEBAR") openSidebar();
  });
}
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
  const toolbar = document.querySelector("#divInfraBarraSistemaPadraoD") ?? document.querySelector("#divArvoreAcoes") ?? document.querySelector(".barraComandos") ?? document.querySelector("#divComandos") ?? document.querySelector("body");
  if (toolbar) toolbar.prepend(btn);
}
function openSidebar() {
  if (!sidebarFrame) {
    createSidebar();
  }
  sidebarFrame.style.display = "block";
  sidebarVisible = true;
  pushSeiBodyRight(true);
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
  sidebarFrame.contentWindow.postMessage(
    { type: "SEI_CONTEXT", payload: currentContext },
    "*"
  );
}
function pushSeiBodyRight(push) {
  const mainEl = document.querySelector("#divConteudo") ?? document.querySelector("#main") ?? document.querySelector("body");
  if (mainEl) {
    mainEl.style.transition = "margin-right 0.25s ease";
    mainEl.style.marginRight = push ? SIDEBAR_WIDTH : "";
  }
}
function observeUrlChanges() {
  let lastUrl = window.location.href;
  const observer = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      handleNavigation();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
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
window.addEventListener("message", async (event) => {
  let expectedOrigin;
  try {
    expectedOrigin = chrome.runtime.getURL("").replace(/\/$/, "");
  } catch {
    return;
  }
  if (event.origin !== expectedOrigin) return;
  const { type, payload, requestId } = event.data ?? {};
  if (!type) return;
  let response;
  try {
    response = await chrome.runtime.sendMessage({ type, payload });
  } catch {
    response = {
      ok: false,
      error: "Extensão recarregada. Recarregue a página do SEI (F5)."
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
  }
});
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
//# sourceMappingURL=content.js.map
