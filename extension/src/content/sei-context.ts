import type { SeiProcessContext } from "../shared/types";

// Inlined here (not imported) so content.js has no top-level import statements
// and can be loaded as a classic script by Chrome.
const SEI_PROCESSO_REGEX = /\b(\d{5}\.\d{6}\/\d{4}-\d{2})\b/;
const SEI_PROCESS_URL_PATTERNS = [
  /acao=procedimento_trabalhar/,
  /acao=arvore_visualizar/,
  /acao=procedimento_visualizar/,
  /acao=procedimento_controlar/,
];

/**
 * Extracts SEI process context from the current page.
 * Works across different SEI screen layouts.
 */
export function extractSeiProcessContext(): SeiProcessContext {
  const currentUrl = window.location.href;
  const pageTitle = document.title || undefined;

  // Extract id_procedimento from URL query string
  const urlParams = new URLSearchParams(window.location.search);
  const idProcedimento = urlParams.get("id_procedimento") ?? undefined;

  // Extract processo number from DOM — try multiple selectors used by SEI
  const numeroProcesso = extractProcessNumber();

  return {
    numeroProcesso,
    idProcedimento,
    currentUrl,
    pageTitle,
  };
}

function extractProcessNumber(): string | undefined {
  // SEI renders the process number in various places depending on the screen
  const candidateSelectors = [
    // Process header area
    "#txtNumeroProtocolo",
    "#txtNumero",
    ".protocoloNomeProcesso",
    // Tree view
    "a[href*='id_procedimento'] .titAnexo",
    "#divArvoreAcoes .protocoloArvore",
    // Page title text fallback
    "title",
  ];

  for (const selector of candidateSelectors) {
    const el = document.querySelector(selector);
    if (el) {
      const text = el.textContent ?? "";
      const match = text.match(SEI_PROCESSO_REGEX);
      if (match) return match[1];
    }
  }

  // Broader text scan of headings and spans
  const broadSelectors = ["h1", "h2", "h3", "span", "td", "div"];
  for (const tag of broadSelectors) {
    const elements = document.querySelectorAll(tag);
    for (const el of Array.from(elements)) {
      const text = el.textContent ?? "";
      const match = text.match(SEI_PROCESSO_REGEX);
      if (match) return match[1];
    }
  }

  return undefined;
}

/**
 * Returns true if the current page is a SEI process screen
 * (i.e., worth injecting the integration button).
 */
export function isSeiProcessPage(): boolean {
  const url = window.location.href;
  return SEI_PROCESS_URL_PATTERNS.some((pattern) => pattern.test(url));
}
