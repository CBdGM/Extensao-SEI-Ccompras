// SEI process context extracted from the page
export interface SeiProcessContext {
  numeroProcesso?: string;
  idProcedimento?: string;
  currentUrl: string;
  pageTitle?: string;
}

// Extension settings stored in chrome.storage.local
export interface ExtensionSettings {
  middlewareUrl: string;
  frontendUrl: string;
  seiExternalSeriesId?: string;
  jwtToken?: string;
  tokenExpiresAt?: number;
}

// Messages between content script and service worker
export type MessageType =
  | "GET_SETTINGS"
  | "SAVE_SETTINGS"
  | "SET_TOKEN"
  | "CLEAR_TOKEN"
  | "API_REQUEST"
  | "SIDEBAR_READY"
  | "SEI_CONTEXT_UPDATED"
  | "OPEN_SIDEBAR"
  | "CACHE_PROCESS"
  | "GET_CACHED_PROCESS"
  | "GET_HTML";

export interface ExtensionMessage<T = unknown> {
  type: MessageType;
  payload?: T;
}

export interface ApiRequestPayload {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  body?: unknown;
}

export interface ApiResponse<T = unknown> {
  ok: boolean;
  status: number;
  data?: T;
  error?: string;
}

// Middleware API types (matching the existing FastAPI backend)
export interface ProcessoSei {
  id_procedimento: string;
  numero_processo: string;
  tipo_processo?: string;
  descricao?: string;
  orgao_gerador?: string;
  unidades_abertas?: string[];
  documentos?: DocumentoSei[];
}

export interface DocumentoSei {
  id_documento: string;
  numero?: string;
  tipo?: string;
  data_geracao?: string;
  descricao?: string;
}

export interface ArtifatoImportacao {
  id: string;
  nome: string;
  tipo: string;
  numero_processo_sei: string;
  status: "pendente" | "enviando" | "enviado" | "erro";
  documento_sei_id?: string;
  documento_sei_numero?: string;
  erro?: string;
  criado_em?: string;
}

export interface ImportacaoPayload {
  numero_processo: string;
  id_procedimento: string;
  arquivo_base64?: string;
  nome_arquivo?: string;
  tipo_documento?: string;
  descricao?: string;
}

export interface ComprovacaoStatus {
  processo: string;
  documento_comprovacao_id?: string;
  documento_comprovacao_numero?: string;
  status: "nao_gerado" | "gerando" | "gerado" | "erro";
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
}
