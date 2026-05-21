# Integração Compras-SEI — MVP

> Middleware institucional + extensão de navegador para importação rastreável de artefatos do **Compras.gov.br** para o **SEI/IFPE**, com geração automática de documento de comprovação assinável.

---

## Sumário

- [O que é](#o-que-é)
- [Componentes](#componentes)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Como rodar](#como-rodar)
  - [Docker (recomendado)](#1-docker-recomendado)
  - [Desenvolvimento local](#2-desenvolvimento-local)
  - [Extensão do navegador](#3-extensão-do-navegador)
- [Configuração](#configuração)
  - [Variáveis de ambiente](#variáveis-de-ambiente)
  - [Integração SEI](#integração-sei)
- [Usuários padrão](#usuários-padrão)
- [Fluxo de uso](#fluxo-de-uso)
- [API — Endpoints](#api--endpoints)
- [Segurança](#segurança)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Banco de dados](#banco-de-dados)
- [Testes](#testes)

---

## O que é

Licitações públicas no IFPE exigem que documentos técnicos (DFD, ETP, Termo de Referência, Matriz de Riscos) sejam autuados no SEI. Esses documentos são elaborados no **Compras.gov.br** e precisam ser formalmente incorporados ao processo SEI correspondente com registro de integridade e rastreabilidade.

Este projeto resolve esse problema com dois componentes:

**Backend (middleware FastAPI)**
1. Consulta o processo SEI via SOAP e armazena os dados localmente
2. Recebe o upload dos artefatos com cálculo de **SHA-256** e **MD5**
3. Gera um **Documento de Comprovação** consolidado (HTML + PDF) com histórico completo
4. Envia os artefatos ao SEI como documentos externos (`incluirDocumento Tipo=R`)
5. Envia o comprovante ao SEI como documento gerado interno (`incluirDocumento Tipo=G`), pronto para **assinatura digital no SEI**
6. Mantém **trilha de auditoria** imutável de todas as operações

**Extensão de navegador (Chrome/Edge)**
- Painel lateral integrado diretamente no SEI
- Detecta automaticamente o processo aberto na tela
- Permite importar artefatos, enviar ao SEI e visualizar o comprovante sem sair do SEI
- Comunica-se exclusivamente com o middleware local — nunca acessa o SOAP do SEI diretamente

---

## Componentes

| Componente | Tecnologia | Descrição |
|-----------|-----------|-----------|
| **backend/** | Python 3.12 + FastAPI | API REST, lógica de negócio, integração SOAP com SEI |
| **extension/** | Chrome Extension MV3 + TypeScript | Painel lateral integrado ao SEI — interface principal do MVP |

---

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────┐
│  Navegador do Servidor (Chrome/Edge)                             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  SEI (sei-testes.ifpe.edu.br / sei.ifpe.edu.br)         │    │
│  │                                                         │    │
│  │   [Extensão — content script]                           │    │
│  │      ↕ postMessage                                      │    │
│  │   [Extensão — sidebar iframe]  ←──── chrome.storage ───│────│─── JWT
│  │      ↕ postMessage                                      │    │
│  │   [Extensão — service worker]                           │    │
│  │      ↕ fetch (JWT Bearer)                               │    │
│  └────────────────────┬────────────────────────────────────┘    │
│                       │ HTTP/JSON                               │
└───────────────────────┼─────────────────────────────────────────┘
                        │
              ┌─────────┴──────────┐
              │  FastAPI (Python)  │
              │  /api/v1/*         │
              └──────┬─────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
   PostgreSQL    Filesystem    SEI SOAP
   (dados +      (uploads +    (HTTPS)
    audit)        PDFs)
```


### Camadas do backend

```
routers/              ← HTTP, validação de entrada, controle de acesso, auditoria
services/
  sei_service.py      ← Interface com SEI (consulta SOAP + envio)
  soap_client.py      ← Cliente SOAP de baixo nível (XML, retry, timeout)
  sei_send_service.py ← Orquestração do envio (idempotência, estados intermediários)
  document_service.py ← Geração e rebuild do comprovante (HTML + PDF)
  artifact_service.py ← Upload, validação, soft delete
  audit_service.py    ← Log sanitizado de operações
models/               ← ORM SQLAlchemy (6 tabelas)
schemas/              ← Pydantic (validação + serialização)
core/
  security.py         ← JWT, bcrypt
  crypto.py           ← Fernet AES-128-CBC (credenciais SEI)
  file_validator.py   ← Validação de uploads em 5 camadas
  deps.py             ← FastAPI Depends (auth, IP, admin)
```

### Arquitetura da extensão

```
popup.ts              ← Popup do ícone: status de auth, botão para abrir painel
content.ts            ← Injetado no SEI: detecta processo, cria botão + iframe
sei-context.ts        ← Extrai numero_processo e id_procedimento da página SEI
service-worker.ts     ← Proxy de API (único acesso ao JWT e ao middleware)
sidebar.ts            ← Painel lateral completo (tabs: Processo, Importar,
                         Comprovação, Histórico, Config)
```

**Princípio de segurança da extensão:** o JWT e a URL do middleware vivem **apenas** no service worker. O content script e o sidebar nunca têm acesso direto ao token.

---

## Pré-requisitos

**Para Docker (recomendado):**
- Docker 24+ e Docker Compose v2

**Para desenvolvimento local:**
- Python 3.12+
- PostgreSQL 16 (ou Docker apenas para o banco)

**Para a extensão:**
- Chrome 102+ ou Microsoft Edge 102+

**Para recompilar a extensão (opcional):**
- Node.js 20+ (a extensão já vem pré-compilada em `extension/dist/`)

---

## Como rodar

### 1. Docker (recomendado)

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd MVP_EXTENSAO

# Configure as variáveis de ambiente
cp .env.example .env

# Gere as chaves de segurança obrigatórias
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"
python3 -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
# Cole os valores gerados no .env

# Suba o banco e o backend
docker compose up -d --build

# Execute as migrations do banco
docker exec compras_sei_backend alembic upgrade head

# Crie os usuários iniciais
docker exec compras_sei_backend python seed.py
```

Acesse:
- **Backend API:** http://localhost:8000/api/health
- **Swagger (apenas DEBUG=true):** http://localhost:8000/api/docs

---

### 2. Desenvolvimento local

#### Backend

```bash
cd backend

# Crie e ative o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Instale as dependências
pip install -r requirements.txt

# Suba apenas o banco via Docker
docker compose up -d db
# O banco ficará disponível em localhost:5433

# Configure o .env local
# (um arquivo backend/.env já existe para dev; ajuste DATABASE_URL se necessário)

# Execute as migrations
alembic upgrade head

# Crie os usuários iniciais
python seed.py

# Inicie o servidor com hot reload
uvicorn app.main:app --reload --port 8000
```

---

### 3. Extensão do navegador

A pasta `extension/dist/` já contém a extensão **pré-compilada** — não é necessário instalar Node.js para usá-la.

#### Carregar no Chrome ou Edge

1. Abra `chrome://extensions` (Chrome) ou `edge://extensions` (Edge)
2. Ative o **Modo de desenvolvedor** (canto superior direito)
3. Clique em **Carregar sem compactação** (_Load unpacked_)
4. Selecione a pasta `extension/dist/`
5. A extensão aparece na barra de ferramentas com o ícone do projeto

#### Configurar a extensão

1. Clique no ícone da extensão na barra de ferramentas
2. O popup exibe o status de autenticação
3. Acesse uma página de processo no SEI — um botão azul **"Compras-SEI"** aparece no canto inferior direito
4. Clique no botão para abrir o painel lateral
5. Na aba **Config**: verifique/ajuste a URL do middleware (padrão: `http://localhost:8000`)
6. Faça login com suas credenciais do middleware

#### Recompilar a extensão (se necessário)

```bash
cd extension
npm install
npm run build       # Gera extension/dist/
# Recarregue a extensão em chrome://extensions após o build
```

> **Importante:** Após qualquer rebuild da extensão, clique em ↺ (recarregar) na listagem de extensões e pressione F5 na aba do SEI.

#### Páginas do SEI onde a extensão ativa

A extensão só injeta o botão nas páginas de processo, identificadas pela URL:

| Padrão | Descrição |
|--------|-----------|
| `acao=procedimento_trabalhar` | Página principal do processo |
| `acao=arvore_visualizar` | Árvore de documentos |
| `acao=procedimento_visualizar` | Visualização do processo |
| `acao=procedimento_controlar` | Controle de processos |

---

## Configuração

### Variáveis de ambiente

Copie `.env.example` para `.env` e preencha. Variáveis obrigatórias:

| Variável | Descrição | Geração |
|----------|-----------|---------|
| `SECRET_KEY` | Chave de assinatura JWT | `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `ENCRYPTION_KEY` | Chave Fernet para credenciais SEI | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `POSTGRES_PASSWORD` | Senha do banco de dados | Defina livremente |
| `ALLOWED_ORIGINS` | Origens CORS permitidas (separadas por vírgula) | Ex: `http://localhost` |

Variáveis para ativar escrita no SEI:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `SEI_ENABLE_WRITE_OPERATIONS` | `false` | **Habilitar apenas após validação com equipe SEI** |
| `SEI_SOAP_URL` | — | URL do web service SOAP do SEI |
| `SEI_SIGLA_SISTEMA` | — | Sigla cadastrada no SEI para este sistema |
| `SEI_IDENTIFICACAO_SERVICO` | — | Chave de acesso fornecida pelo SEI (**nunca commitar**) |
| `SEI_ID_UNIDADE_DEFAULT` | — | ID da unidade SEI responsável |
| `SEI_DEFAULT_EXTERNAL_DOCUMENT_SERIES_ID` | — | IdSerie para artefatos (`Tipo=R`) |
| `SEI_DEFAULT_CONFIRMATION_DOCUMENT_SERIES_ID` | — | IdSerie para comprovante (`Tipo=G`) |

> **`SECRET_KEY`**: se não definida no `.env`, uma chave aleatória é gerada a cada inicialização do servidor — isso invalida todos os JWTs existentes ao reiniciar. Em produção, **defina sempre um valor fixo**.

### Integração SEI

**Via painel administrativo (recomendado):**

1. Acesse o sistema como administrador → menu **Configuração SEI**
2. Preencha URL SOAP, SiglaSistema, IdentificacaoServico (criptografada com Fernet antes de salvar), IdUnidade e os IdSeries
3. Use **Listar Séries** para ver todos os tipos documentais disponíveis na unidade e suas aplicabilidades
4. Para habilitar envio real: ative `SEI_ENABLE_WRITE_OPERATIONS=true` no `.env` e reinicie o backend

**Operações SOAP utilizadas:**

| Operação | Quando |
|----------|--------|
| `consultarProcedimento` | Ao consultar um processo pelo número |
| `listarSeries` | Ao listar tipos documentais no painel admin |
| `adicionarArquivo` | Ao enviar um artefato ao SEI (retorna IdArquivo) |
| `incluirDocumento Tipo=R` | Ao incluir artefato como documento externo recebido |
| `incluirDocumento Tipo=G` | Ao incluir comprovante como documento gerado interno |

---

## Usuários padrão

Criados pelo `seed.py`:

| E-mail | Senha | Perfil |
|--------|-------|--------|
| `admin@ifpe.edu.br` | `Admin@123456` | Administrador |
| `usuario@ifpe.edu.br` | `User@123456` | Usuário comum |

> **Troque as senhas imediatamente** após o primeiro acesso em qualquer ambiente compartilhado.

---

## Fluxo de uso

```
Login
  → Consultar Processo (número SEI)
      → Importar Artefatos (upload PDF: DFD / ETP / TR / Matriz de Riscos)
          → [Enviar Artefatos ao SEI]  — requer SEI_ENABLE_WRITE_OPERATIONS=true
      → Gerar Comprovante
          → Visualizar HTML / Baixar PDF
          → [Enviar Comprovante ao SEI]
              → Assinar digitalmente no SEI
```

**Comportamento do Documento de Comprovação:**

- **Um comprovante por processo** — unicidade garantida via constraint (`UNIQUE sei_process_id`)
- **Auto-rebuild** — ao importar ou remover um artefato, o comprovante é atualizado automaticamente
- **Controle de versão** — cada rebuild incrementa o número de versão
- **Detecção de mudanças pós-envio** — se o conteúdo mudar após envio ao SEI, o status muda para `Reemissão necessária`
- **Artefatos removidos** — aparecem no comprovante com linha riscada e data de remoção (auditoria preservada)

**Comportamento do soft delete de artefatos:**

- Exclusão é **lógica** — o arquivo permanece no storage e a entrada no banco é mantida com `status=DELETED`
- A trilha de auditoria registra a remoção com usuário, IP e timestamp
- O artefato aparece no comprovante como removido, sem sumir da trilha histórica

---

## API — Endpoints

| Método | Endpoint | Descrição | Acesso |
|--------|----------|-----------|--------|
| `POST` | `/api/v1/auth/login` | Login | Público |
| `POST` | `/api/v1/auth/refresh` | Renovar token | Público |
| `GET` | `/api/v1/auth/me` | Usuário atual | Autenticado |
| `POST` | `/api/v1/sei-processes/query` | Consultar processo no SEI | Autenticado |
| `GET` | `/api/v1/sei-processes/` | Listar processos | Autenticado |
| `GET` | `/api/v1/sei-processes/{id}` | Detalhes do processo | Autenticado |
| `DELETE` | `/api/v1/sei-processes/{id}` | Excluir processo | Autenticado |
| `GET` | `/api/v1/sei-processes/{id}/artifacts` | Artefatos do processo | Autenticado |
| `GET` | `/api/v1/sei-processes/{id}/import-document` | Comprovante do processo | Autenticado |
| `POST` | `/api/v1/artifacts/` | Importar artefato (multipart) | Autenticado |
| `GET` | `/api/v1/artifacts/` | Listar artefatos | Autenticado |
| `GET` | `/api/v1/artifacts/{id}/download` | Download do arquivo | Autenticado |
| `DELETE` | `/api/v1/artifacts/{id}` | Remover artefato (soft delete) | Autenticado |
| `POST` | `/api/v1/artifacts/{id}/send-to-sei` | Enviar artefato ao SEI | Autenticado |
| `POST` | `/api/v1/documents/generate` | Gerar/atualizar comprovante | Autenticado |
| `GET` | `/api/v1/documents/` | Listar comprovantes | Autenticado |
| `GET` | `/api/v1/documents/{id}/html` | Visualizar comprovante (HTML) | Autenticado |
| `GET` | `/api/v1/documents/{id}/pdf` | Download PDF | Autenticado |
| `POST` | `/api/v1/documents/{id}/rebuild` | Forçar rebuild | Autenticado |
| `POST` | `/api/v1/documents/{id}/send-to-sei` | Enviar comprovante ao SEI | Autenticado |
| `DELETE` | `/api/v1/documents/{id}` | Apagar comprovante | Autenticado |
| `GET` | `/api/v1/audit/` | Logs de auditoria | Admin |
| `GET` | `/api/v1/audit/process/{id}` | Auditoria de um processo | Autenticado |
| `GET` | `/api/v1/sei-config/` | Configuração SEI atual | Admin |
| `POST` | `/api/v1/sei-config/` | Criar configuração SEI | Admin |
| `PUT` | `/api/v1/sei-config/{id}` | Atualizar configuração SEI | Admin |
| `GET` | `/api/v1/sei-config/write-status` | Status das operações de escrita | Autenticado |
| `GET` | `/api/v1/sei-config/series` | Listar tipos documentais SEI | Admin |
| `GET` | `/api/v1/users/` | Listar usuários | Admin |
| `POST` | `/api/v1/users/` | Criar usuário | Admin |
| `PUT` | `/api/v1/users/{id}` | Atualizar usuário | Admin |

Documentação interativa (apenas com `DEBUG=true`): `http://localhost:8000/api/docs`

---

## Segurança

### Backend

| Categoria | Implementação |
|-----------|--------------|
| Autenticação | JWT HS256 (access 30 min + refresh 7 dias), bcrypt rounds=12 |
| Credenciais SEI | Fernet AES-128-CBC no banco; a chave `SEI_IDENTIFICACAO_SERVICO` **nunca** é retornada pela API nem gravada em logs |
| Validação de uploads | 5 camadas: tamanho → extensão → magic bytes (`%PDF`) → MIME → bloqueio de executáveis (PE/ELF) |
| Trilha de auditoria | Log sanitizado de todas as ações — credenciais nunca entram nos metadados |
| Headers HTTP | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`, `Referrer-Policy`, CSP, remoção do header `Server` |
| Rate limiting | 60 req/min geral, 10 req/min em login (slowapi) |
| CORS | Restrito às origens em `ALLOWED_ORIGINS` + regex `chrome-extension://.*` |
| Erros | Stack trace nunca exposto ao cliente; handler genérico retorna mensagem opaca |
| Arquivos | Armazenados fora da pasta pública; acesso somente via API autenticada |
| Exclusão | Soft delete para artefatos (dado permanece para auditoria) |
| Integridade | SHA-256 + MD5 calculados no servidor para cada arquivo importado |
| Docs Swagger | Desabilitados em `ENVIRONMENT=production` |

### Extensão do navegador

| Categoria | Implementação |
|-----------|--------------|
| JWT | Armazenado apenas no service worker via `chrome.storage.local`; nunca exposto ao content script |
| Comunicação | Toda chamada ao middleware passa pelo service worker (proxy); content script usa postMessage |
| Credenciais SEI | A extensão **nunca** conhece credenciais SEI, URL SOAP, IdSerie ou chave de acesso |
| Manifest V3 | CSP: `script-src 'self'; object-src 'self'` — sem inline scripts |
| Permissões | Apenas `storage` — mínimo necessário |
| host_permissions | Restrito aos domínios SEI do IFPE + localhost:8000 |
| Botões interativos | Todos usam `data-action` + `addEventListener` (sem `onclick` inline — compatível com CSP MV3) |
| Logout | Token limpo localmente a cada logout explícito e a cada resposta 401 do backend |
| Confirm/Alert | Substituídos por overlay DOM customizado (APIs bloqueadas em iframes cross-origin) |

### O que nunca é commitado

- `backend/.env` e `.env` raiz (senhas, chaves JWT, Fernet, credenciais SEI)
- `uploads/` (arquivos dos usuários)
- Quaisquer chaves privadas, tokens ou certificados

---

## Estrutura do projeto

```
MVP_EXTENSAO/
├── backend/                          # FastAPI middleware
│   ├── app/
│   │   ├── main.py                   # App FastAPI, CORS, middlewares, rate limit
│   │   ├── config.py                 # Pydantic Settings (lê .env)
│   │   ├── database.py               # SQLAlchemy async engine + sessão
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── sei_process.py        # SEIProcess + SEIProcessQuery
│   │   │   ├── artifact.py           # ImportedArtifact (soft delete)
│   │   │   ├── document.py           # ImportDocument (comprovante)
│   │   │   ├── sei_config.py         # Configuração SEI (credenciais criptografadas)
│   │   │   ├── audit.py              # AuditLog
│   │   │   └── sei_write_operation.py
│   │   ├── schemas/                  # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── sei_process.py        # Consulta + get-or-create por numero_processo
│   │   │   ├── artifacts.py
│   │   │   ├── documents.py
│   │   │   ├── sei_config.py         # CRUD config + listar séries SEI
│   │   │   └── audit.py
│   │   ├── services/
│   │   │   ├── sei_service.py        # consultarProcedimento, listarSeries
│   │   │   ├── soap_client.py        # Cliente SOAP (httpx, XML templates, retry)
│   │   │   ├── sei_send_service.py   # adicionarArquivo + incluirDocumento (idempotente)
│   │   │   ├── document_service.py   # Geração HTML+PDF, rebuild automático, versionamento
│   │   │   ├── artifact_service.py   # Upload com validação 5 camadas, soft delete
│   │   │   └── audit_service.py      # Log sanitizado
│   │   └── core/
│   │       ├── security.py           # JWT (access + refresh), bcrypt
│   │       ├── crypto.py             # Fernet encrypt/decrypt
│   │       ├── file_validator.py     # Validação de uploads
│   │       └── deps.py               # FastAPI Depends (get_current_user, require_admin)
│   ├── migrations/
│   │   └── versions/                 # Migrations Alembic
│   ├── tests/
│   ├── seed.py                       # Cria usuários iniciais
│   ├── requirements.txt
│   ├── alembic.ini
│   └── Dockerfile
│
├── extension/                        # Chrome/Edge Extension MV3
│   ├── dist/                         # Build pré-compilado — carregar direto no Chrome
│   ├── public/
│   │   ├── manifest.json             # MV3: permissions, host_permissions, CSP
│   │   └── icons/
│   └── src/
│       ├── background/
│       │   └── service-worker.ts     # Proxy JWT: GET_SETTINGS, API_REQUEST, GET_HTML,
│       │                             #   SET_TOKEN, CLEAR_TOKEN, CACHE_PROCESS,
│       │                             #   GET_CACHED_PROCESS, OPEN_SIDEBAR
│       ├── content/
│       │   ├── content.ts            # Injeta botão, cria iframe, relay de mensagens
│       │   ├── content.css           # Estilos do botão e wrapper do sidebar
│       │   └── sei-context.ts        # Extrai numero_processo e id_procedimento da página
│       ├── popup/
│       │   ├── popup.ts              # Status de auth, botão abrir painel
│       │   ├── popup.html
│       │   └── popup.css
│       ├── sidebar/
│       │   ├── sidebar.ts            # Painel completo: Processo, Importar,
│       │   │                         #   Comprovacao, Historico, Config
│       │   ├── sidebar.html
│       │   └── sidebar.css
│       └── shared/
│           ├── types.ts              # Interfaces TypeScript compartilhadas
│           └── constants.ts          # URLs padrão, storage keys, padrões de URL SEI
│
├── docs/
│   └── ARCHITECTURE.md               # Decisões de design, modelo de dados detalhado
├── docker-compose.yml
├── .env.example                      # Template de configuração (sem valores reais)
└── README.md
```

---

## Banco de dados

```
users
  └─► sei_process_queries ──► sei_processes
                                    ├─► imported_artifacts   (soft delete)
                                    └─► import_documents      (UNIQUE por processo)

audit_logs           (entity_id como string — sem FK, preservado em exclusões)
sei_config           (credenciais criptografadas com Fernet)
sei_write_operations (log de cada chamada de escrita ao SEI)
```

**Migrations com Alembic:**

```bash
# Aplicar todas as migrations (Docker)
docker exec compras_sei_backend alembic upgrade head

# Aplicar (local)
alembic upgrade head

# Ver migration atual
alembic current

# Criar nova migration após alteração nos models
alembic revision --autogenerate -m "descricao_da_mudanca"
```

---

## Testes

```bash
cd backend
source .venv/bin/activate

pytest tests/ -v
pytest tests/ -v --cov=app --cov-report=html
open htmlcov/index.html
```

---

## Stack tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.12 + FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 async + Alembic |
| Banco | PostgreSQL 16 |
| Autenticação | JWT HS256 + bcrypt rounds=12 |
| Criptografia | Fernet AES-128-CBC (cryptography) |
| SOAP | httpx async (sem lib SOAP pesada) |
| PDF | ReportLab |
| Rate limiting | slowapi |
| Extensão | Chrome Extension MV3 + TypeScript + Vite |
| Containerização | Docker + Docker Compose v2 |

---

## Licença

Uso interno IFPE. Desenvolvido como MVP para integração entre Compras.gov.br e SEI.
