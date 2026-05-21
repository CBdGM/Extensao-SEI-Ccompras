const DEFAULT_MIDDLEWARE_URL = "http://localhost:8000";
const DEFAULT_FRONTEND_URL = "http://localhost:5173";
const STORAGE_KEYS = {
  MIDDLEWARE_URL: "middlewareUrl",
  FRONTEND_URL: "frontendUrl",
  SEI_EXTERNAL_SERIES_ID: "seiExternalSeriesId",
  JWT_TOKEN: "jwtToken",
  TOKEN_EXPIRES_AT: "tokenExpiresAt"
};
const SEI_PROCESS_URL_PATTERNS = [
  /acao=procedimento_trabalhar/,
  /acao=arvore_visualizar/,
  /acao=procedimento_visualizar/
];
export {
  DEFAULT_FRONTEND_URL as D,
  SEI_PROCESS_URL_PATTERNS as S,
  DEFAULT_MIDDLEWARE_URL as a,
  STORAGE_KEYS as b
};
//# sourceMappingURL=constants.js.map
