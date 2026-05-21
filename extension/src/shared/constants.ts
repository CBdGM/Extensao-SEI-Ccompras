export const DEFAULT_MIDDLEWARE_URL = "http://localhost:8000";
export const DEFAULT_FRONTEND_URL = "http://localhost:5173";

export const STORAGE_KEYS = {
  MIDDLEWARE_URL: "middlewareUrl",
  FRONTEND_URL: "frontendUrl",
  SEI_EXTERNAL_SERIES_ID: "seiExternalSeriesId",
  JWT_TOKEN: "jwtToken",
  TOKEN_EXPIRES_AT: "tokenExpiresAt",
} as const;

export const SEI_PROCESS_URL_PATTERNS = [
  /acao=procedimento_trabalhar/,
  /acao=arvore_visualizar/,
  /acao=procedimento_visualizar/,
];

export const SEI_PROCESSO_REGEX =
  /\b(\d{5}\.\d{6}\/\d{4}-\d{2})\b/;

export const SIDEBAR_WIDTH = "420px";
export const SIDEBAR_ID = "compras-sei-sidebar";
export const BUTTON_ID = "compras-sei-btn";
