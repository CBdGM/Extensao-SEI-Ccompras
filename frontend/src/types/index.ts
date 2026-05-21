export type UserRole = 'admin' | 'user';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface SEIConfig {
  id: string;
  soap_url: string;
  sigla_sistema: string;
  id_unidade_default: string;
  sin_retornar_assuntos: boolean;
  sin_retornar_interessados: boolean;
  sin_retornar_observacoes: boolean;
  sin_retornar_ultimo_andamento: boolean;
  sin_retornar_unidades: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UltimoAndamento {
  data_hora?: string;
  unidade_sigla?: string;
  descricao?: string;
}

export interface SEIProcess {
  id: string;
  query_id: string;
  id_procedimento?: string;
  numero_processo: string;
  especificacao?: string;
  data_autuacao?: string;
  link_acesso?: string;
  nivel_acesso_local?: string;
  nivel_acesso_global?: string;
  tipo_procedimento_id?: string;
  tipo_procedimento_nome?: string;
  unidade_sigla?: string;
  unidade_descricao?: string;
  ultimo_andamento?: UltimoAndamento;
  created_at: string;
  artifacts_count: number;
  documents_count: number;
}

export interface SEIProcessListItem {
  id: string;
  numero_processo: string;
  especificacao?: string;
  tipo_procedimento_nome?: string;
  unidade_sigla?: string;
  data_autuacao?: string;
  created_at: string;
  artifacts_count: number;
}

export interface SEIQueryResponse {
  id: string;
  user_id: string;
  numero_processo: string;
  status: 'success' | 'error' | 'pending';
  response_summary?: string;
  error_message?: string;
  created_at: string;
  process?: SEIProcess;
}

export type ArtifactType = 'DFD' | 'ETP' | 'TR' | 'MATRIZ_RISCOS';
export type AccessLevel = 'publico' | 'restrito' | 'sigiloso';
export type ArtifactStatus = 'active' | 'deleted';
export type SendToSEIStatus =
  | 'not_sent'
  | 'pending'
  | 'file_uploaded_document_failed'
  | 'sent'
  | 'error';

export interface Artifact {
  id: string;
  sei_process_id: string;
  user_id: string;
  tipo_artefato: ArtifactType;
  identificador_compras: string;
  nivel_acesso: AccessLevel;
  original_filename: string;
  mime_type: string;
  file_size: number;
  sha256_hash: string;
  md5_hash: string;
  status: ArtifactStatus;
  observacao?: string;
  document_locked: boolean;
  created_at: string;
  // SEI send tracking
  send_to_sei_status: SendToSEIStatus;
  sei_file_id?: string;
  sei_document_id?: string;
  sei_document_number?: string;
  sei_document_link?: string;
  sent_to_sei_at?: string;
  send_to_sei_error?: string;
}

export type DocumentStatus =
  | 'draft'
  | 'generated'
  | 'sent_to_sei'
  | 'needs_update'
  | 'needs_reissue'
  | 'reissued'
  | 'cancelled'
  | 'error';

export interface ImportDocument {
  id: string;
  sei_process_id: string;
  user_id: string;
  status: DocumentStatus;
  sei_protocol?: string;
  created_at: string;
  document_html?: string;
  // SEI send tracking
  send_to_sei_status: SendToSEIStatus;
  sei_document_number?: string;
  sei_document_link?: string;
  sent_to_sei_at?: string;
  send_to_sei_error?: string;
  // Content tracking
  last_rebuilt_at?: string;
  last_content_hash?: string;
  version_number: number;
}

export interface DocumentListItem {
  id: string;
  sei_process_id: string;
  numero_processo?: string;
  user_id: string;
  user_name?: string;
  status: DocumentStatus;
  created_at: string;
  send_to_sei_status: SendToSEIStatus;
  sei_document_number?: string;
  last_rebuilt_at?: string;
  version_number: number;
}

export interface SEIWriteStatus {
  write_enabled: boolean;
  source: 'env' | 'db_config' | 'disabled';
  external_series_configured: boolean;
  confirmation_series_configured: boolean;
}

export interface AuditLog {
  id: string;
  user_id?: string;
  user_name?: string;
  action: string;
  entity_type?: string;
  entity_id?: string;
  ip_address?: string;
  metadata_json?: Record<string, unknown>;
  created_at: string;
}

export interface ApiError {
  detail: string | Array<{ field: string; message: string }>;
}
