# Documento de Arquitetura — Integração Compras-SEI MVP

## Decisões de Design

### Stack tecnológica

| Componente | Tecnologia | Justificativa |
|-----------|-----------|--------------|
| Backend | Python + FastAPI | Async nativo, type hints, OpenAPI automático |
| ORM | SQLAlchemy 2.0 async | Queries async, pool de conexões, migrations via Alembic |
| Auth | JWT (python-jose) + bcrypt | Stateless, refresh tokens, bcrypt rounds=12 |
| Criptografia | Fernet (cryptography) | AES-128-CBC autenticado, resistente a tampering |
| SOAP | httpx async | Sem dependência de biblioteca SOAP pesada |
| PDF | ReportLab | Sem dependências de sistema (ex: weasyprint requer libcairo) |
| Rate limit | slowapi | Integração nativa com FastAPI |
| Frontend | React + Vite + TypeScript | Tipagem estrita, build rápido |
| Estado | Zustand | Minimal, sem boilerplate Redux |
| Queries | TanStack React Query | Cache, retry, invalidação declarativa |
| CSS | Tailwind CSS | Utilitário, sem CSS-in-JS overhead |

---

## Modelo de Segurança

### Credenciais SEI
```
Usuário Admin → Painel → identificacao_servico (plaintext)
                                    ↓
                        encrypt_value() — Fernet AES-128-CBC
                                    ↓
                        sei_config.identificacao_servico_encrypted
                                    ↓ (decrypt apenas no momento da chamada SOAP)
                        SOAPClient._identificacao_servico (memória)
                                    ↓ (descartado após request)
                        SOAP Envelope → SEI
```

A chave **nunca**:
- É retornada por qualquer endpoint de API
- É registrada em logs
- É exposta no frontend

### Fluxo de autenticação
```
POST /auth/login
    ↓ verify_password (bcrypt)
    ↓ create_access_token (JWT, 30min)
    ↓ create_refresh_token (JWT, 7 dias)
    → { access_token, refresh_token }

Requests subsequentes:
    Authorization: Bearer <access_token>
    ↓ HTTPBearer → verify_access_token → get_current_user
    ↓ User injetado via Depends()

Token expirado:
    POST /auth/refresh com { refresh_token }
    → novo par de tokens
```

---

## Validação de Arquivos

Camadas de validação (em ordem):

1. **Tamanho** — rejeita antes de ler o arquivo completo
2. **Extensão** — aceita apenas `.pdf`
3. **Magic bytes** — verifica `%PDF` nos primeiros 4 bytes
4. **MIME type** — checagem advisory (não confiável isoladamente)
5. **Executáveis** — bloqueia `MZ` (PE Windows), `\x7fELF` (Linux), extensões perigosas

Hash calculado após todas as validações:
- **SHA-256**: integridade long-term, incluído no documento de comprovação
- **MD5**: compatibilidade futura com `adicionarArquivo` do SEI (exige MD5)

---

## Auditoria

Todas as operações relevantes geram um `AuditLog`:

| Ação | Quando |
|------|--------|
| `LOGIN_SUCCESS/FAILED` | Tentativa de login |
| `LOGOUT` | Logout explícito |
| `SEI_PROCESS_QUERIED` | Consulta bem-sucedida ao SEI |
| `SEI_QUERY_FAILED` | Falha na consulta |
| `ARTIFACT_UPLOADED` | Upload de artefato (inclui SHA-256) |
| `ARTIFACT_DELETED` | Exclusão lógica |
| `ARTIFACT_DOWNLOADED` | Download de arquivo |
| `DOCUMENT_GENERATED` | Geração de documento de comprovação |
| `DOCUMENT_VIEWED` | Visualização de documento |
| `SEI_CONFIG_CREATED/UPDATED` | Alteração de configuração |
| `USER_CREATED/UPDATED` | Gestão de usuários |
| `PASSWORD_CHANGED` | Troca de senha |

O `audit_service.py` aplica sanitização para garantir que nenhuma credencial chegue ao JSON de metadados.

---

## Integridade de Documentos

Após a geração do documento de comprovação:
- `ImportedArtifact.document_locked = True`
- Tentativa de deletar artefato bloqueado retorna HTTP 409
- Para nova versão: gerar um novo documento (os anteriores ficam imutáveis)

---

## Estrutura do Banco de Dados

```
users ──────────────────┐
    id (PK)             │
    name                │
    email (UNIQUE)      │
    password_hash       │
    role (admin|user)   │
    is_active           │
    created_at          │
    updated_at          │
                        │
sei_config              │
    id (PK)             │
    soap_url            │
    sigla_sistema       │
    identificacao_servico_encrypted  ← Fernet
    id_unidade_default  │
    sin_* flags         │
    is_active           │
                        │
sei_process_queries ────┤  user_id → users.id
    id (PK)             │
    user_id (FK)        │
    numero_processo     │
    status              │
    response_summary    │
    error_message       │
                        │
sei_processes           │
    id (PK)             │
    query_id (FK)       │
    id_procedimento     │
    numero_processo     │
    ... dados do SEI    │
    raw_response_json   │
                        │
imported_artifacts ─────┤  sei_process_id → sei_processes.id
    id (PK)             │  user_id → users.id
    sei_process_id (FK) │
    user_id (FK)        │
    tipo_artefato       │
    identificador_compras│
    nivel_acesso        │
    original_filename   │
    stored_filename     │
    sha256_hash         │
    md5_hash            │
    storage_path        │
    status              │
    document_locked     │
    deleted_at          │  ← Soft delete
                        │
import_documents ───────┤  sei_process_id → sei_processes.id
    id (PK)             │  user_id → users.id
    sei_process_id (FK) │
    user_id (FK)        │
    document_html       │
    pdf_path            │
    status              │
    sei_protocol        │  ← Uso futuro após incluirDocumento
                        │
audit_logs ─────────────┘  user_id → users.id (nullable)
    id (PK)
    user_id (FK nullable)
    action
    entity_type
    entity_id
    ip_address
    metadata_json       ← JSON sanitizado sem credenciais
    created_at
```

---

## Roadmap para Integração Completa

### Fase 2 — Operações de escrita

1. **Obter credenciais** de escrita junto à equipe SEI/IFPE
2. **Implementar** `adicionar_arquivo()` em `sei_service.py`
   - Converter PDF para Base64
   - Enviar envelope `adicionarArquivo` com MD5 hash
3. **Implementar** `incluir_documento()` em `sei_service.py`
   - Converter HTML do documento para Base64
   - Enviar envelope `incluirDocumento`
   - Salvar `sei_protocol` e `sei_document_id` no banco
4. **Feature flag**: `SEI_ENABLE_WRITE_OPERATIONS=true`
5. **Testes** em ambiente de homologação antes de produção

### Fase 3 — Enriquecimentos

- Busca por interessados e assuntos no processo
- Notificações por e-mail ao gerar documento
- Exportação de relatórios de importação
- Suporte a múltiplas unidades SEI
- Integração com LDAP/SSO institucional
