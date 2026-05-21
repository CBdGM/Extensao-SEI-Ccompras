"""
SEI Service — orchestrates all SEI integration operations.

Read operations:  consultar_procedimento — always available.
Write operations: adicionar_arquivo, incluir_documento_externo,
                  incluir_documento_comprovacao — require
                  SEI_ENABLE_WRITE_OPERATIONS=true OR config.enable_write_operations=true.
"""
import base64
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.sei_config import SEIConfig
from app.services.soap_client import SOAPClient
from app.core.crypto import decrypt_value

logger = logging.getLogger(__name__)

# Nivel de acesso: SEI uses 0=público, 1=restrito, 2=sigiloso
_ACCESS_MAP = {"publico": 0, "restrito": 1, "sigiloso": 2}


# ── Response parsers ──────────────────────────────────────────────────────────

def _extract_text(data: dict, *keys: str) -> Optional[str]:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if isinstance(current, str):
        return current or None
    if isinstance(current, dict):
        return json.dumps(current)
    return None


def _resolve_proc(raw: dict) -> dict:
    """Navigate SOAP envelope to the procedure payload.
    SEI versions may wrap data in 'Procedimento' or 'parametros'.
    """
    body = raw.get("Body", raw)
    resp = body.get("consultarProcedimentoResponse", body)
    return resp.get("Procedimento") or resp.get("parametros") or resp


def _extract_ultimo_andamento(raw: dict) -> Optional[dict]:
    try:
        proc = _resolve_proc(raw)
        ua = proc.get("UltimoAndamento")
        if not ua or not isinstance(ua, dict):
            return None
        unidade = ua.get("Unidade", {})
        return {
            "data_hora": ua.get("DataHora"),
            "unidade_sigla": unidade.get("Sigla") if isinstance(unidade, dict) else None,
            "descricao": ua.get("Descricao"),
        }
    except Exception:
        return None


def _parse_procedimento(raw: dict) -> Dict[str, Any]:
    try:
        proc = _resolve_proc(raw)
        if not proc:
            return {}

        tipo = proc.get("TipoProcedimento", {})
        if not isinstance(tipo, dict):
            tipo = {}

        unidade = proc.get("UnidadeGeradora")
        if not isinstance(unidade, dict):
            ua = proc.get("UltimoAndamento", {})
            unidade = ua.get("Unidade", {}) if isinstance(ua, dict) else {}
        if not isinstance(unidade, dict):
            unidade = {}

        return {
            "id_procedimento": _extract_text(proc, "IdProcedimento"),
            "numero_processo": (
                _extract_text(proc, "ProcedimentoFormatado")
                or _extract_text(proc, "ProtocoloProcedimento")
            ),
            "especificacao": _extract_text(proc, "Especificacao"),
            "data_autuacao": _extract_text(proc, "DataAutuacao"),
            "link_acesso": _extract_text(proc, "LinkAcesso"),
            "nivel_acesso_local": _extract_text(proc, "NivelAcessoLocal"),
            "nivel_acesso_global": _extract_text(proc, "NivelAcessoGlobal"),
            "tipo_procedimento_id": tipo.get("IdTipoProcedimento"),
            "tipo_procedimento_nome": tipo.get("Nome"),
            "unidade_sigla": unidade.get("Sigla"),
            "unidade_descricao": unidade.get("Descricao"),
            "ultimo_andamento": json.dumps(_extract_ultimo_andamento(raw)),
        }
    except Exception as e:
        logger.error("Error parsing procedimento response: %s", type(e).__name__)
        return {}


def _parse_adicionar_arquivo(raw: dict) -> str:
    """Extract IdArquivo from adicionarArquivo response."""
    body = raw.get("Body", raw)
    for key in ("adicionarArquivoResponse", "adicionarArquivoResult"):
        resp = body.get(key)
        if resp is None:
            continue
        if isinstance(resp, str) and resp:
            return resp
        if isinstance(resp, dict):
            # parametros pode ser a string direta (IFPE) ou um dict com IdArquivo
            parametros = resp.get("parametros")
            if isinstance(parametros, str) and parametros:
                return parametros
            if isinstance(parametros, dict):
                id_arquivo = parametros.get("IdArquivo")
                if id_arquivo:
                    return str(id_arquivo)
            # Algumas versões retornam IdArquivo diretamente no elemento
            id_arquivo = resp.get("IdArquivo")
            if id_arquivo:
                return str(id_arquivo)
    raise ValueError(f"IdArquivo não encontrado na resposta do SEI: {json.dumps(raw)[:200]}")


def _parse_incluir_documento(raw: dict) -> Dict[str, Any]:
    """Extract IdDocumento, DocumentoFormatado, LinkAcesso from incluirDocumento response."""
    body = raw.get("Body", raw)
    for key in ("incluirDocumentoResponse", "incluirDocumentoResult"):
        resp = body.get(key, {})
        if isinstance(resp, dict):
            # Response may be at top level or inside 'parametros'
            data = resp.get("parametros") if isinstance(resp.get("parametros"), dict) else resp
            id_doc = data.get("IdDocumento")
            doc_formatado = data.get("DocumentoFormatado")
            link = data.get("LinkAcesso")
            if id_doc:
                return {
                    "id_documento": str(id_doc),
                    "documento_formatado": str(doc_formatado) if doc_formatado else None,
                    "link_acesso": str(link) if link else None,
                }
    raise ValueError(f"IdDocumento não encontrado na resposta do SEI: {json.dumps(raw)[:200]}")


# ── SEIService ────────────────────────────────────────────────────────────────

class SEIService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._config_cache: Optional[SEIConfig] = None

    async def _get_config(self) -> Optional[SEIConfig]:
        if self._config_cache is None:
            result = await self.db.execute(
                select(SEIConfig).where(SEIConfig.is_active == True).limit(1)
            )
            self._config_cache = result.scalar_one_or_none()
        return self._config_cache

    async def _get_soap_client(self, use_write_timeout: bool = False) -> SOAPClient:
        config = await self._get_config()
        timeout = settings.SEI_WRITE_TIMEOUT_SECONDS if use_write_timeout else settings.SEI_REQUEST_TIMEOUT
        if config:
            try:
                key = decrypt_value(config.identificacao_servico_encrypted)
            except Exception:
                raise ValueError("Erro ao ler configuração do SEI. Reconfigure a chave de acesso.")
            return SOAPClient(
                soap_url=config.soap_url,
                sigla_sistema=config.sigla_sistema,
                identificacao_servico=key,
                id_unidade=config.id_unidade_default,
                timeout=settings.SEI_REQUEST_TIMEOUT,
                write_timeout=timeout,
                max_retries=settings.SEI_MAX_RETRIES,
            )
        if not settings.SEI_SOAP_URL or not settings.SEI_IDENTIFICACAO_SERVICO:
            raise ValueError(
                "SEI não configurado. Configure via painel administrativo ou variáveis de ambiente."
            )
        return SOAPClient(
            soap_url=settings.SEI_SOAP_URL,
            sigla_sistema=settings.SEI_SIGLA_SISTEMA or "MVP",
            identificacao_servico=settings.SEI_IDENTIFICACAO_SERVICO,
            id_unidade=settings.SEI_ID_UNIDADE_DEFAULT or "110001189",
            timeout=settings.SEI_REQUEST_TIMEOUT,
            write_timeout=timeout,
            max_retries=settings.SEI_MAX_RETRIES,
        )

    def _write_enabled(self, config: Optional[SEIConfig]) -> bool:
        """Write operations are allowed if env flag OR db config flag is set."""
        if settings.SEI_ENABLE_WRITE_OPERATIONS:
            return True
        if config and config.enable_write_operations:
            return True
        return False

    def _resolve_series_id(
        self, config: Optional[SEIConfig], kind: str, override: Optional[str] = None
    ) -> str:
        """Return the appropriate IdSerie, falling back through override → db → env."""
        if override:
            return override
        if kind == "external":
            db_val = config.external_document_series_id if config else None
            return db_val or settings.SEI_DEFAULT_EXTERNAL_DOCUMENT_SERIES_ID or ""
        if kind == "confirmation":
            db_val = config.confirmation_document_series_id if config else None
            return db_val or settings.SEI_DEFAULT_CONFIRMATION_DOCUMENT_SERIES_ID or ""
        return ""

    # ── Read ──────────────────────────────────────────────────────────────────

    async def consultar_procedimento(self, numero_processo: str) -> Dict[str, Any]:
        client = await self._get_soap_client()
        config = await self._get_config()
        flags = {
            "sin_assuntos": config.sin_retornar_assuntos if config else True,
            "sin_interessados": config.sin_retornar_interessados if config else True,
            "sin_observacoes": config.sin_retornar_observacoes if config else True,
            "sin_ultimo_andamento": config.sin_retornar_ultimo_andamento if config else True,
            "sin_unidades": config.sin_retornar_unidades if config else True,
        }
        raw = await client.consultar_procedimento(protocolo=numero_processo, **flags)
        parsed = _parse_procedimento(raw)
        parsed["raw_response_json"] = json.dumps(raw)
        return parsed

    # ── Write ─────────────────────────────────────────────────────────────────

    async def adicionar_arquivo(
        self,
        file_path: str,
        original_filename: str,
        md5_hash: str,
        file_size: int,
    ) -> str:
        """
        Upload a file to SEI repository.
        Returns IdArquivo string.
        Raises ValueError if write operations are disabled.
        """
        config = await self._get_config()
        if not self._write_enabled(config):
            raise ValueError(
                "Operações de escrita no SEI estão desabilitadas. "
                "Habilite SEI_ENABLE_WRITE_OPERATIONS=true ou configure no painel admin."
            )

        import aiofiles
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()

        conteudo_b64 = base64.b64encode(content).decode("ascii")
        client = await self._get_soap_client(use_write_timeout=True)
        raw = await client.adicionar_arquivo(
            nome=original_filename,
            tamanho=file_size,
            hash_md5=md5_hash,
            conteudo_base64=conteudo_b64,
        )
        id_arquivo = _parse_adicionar_arquivo(raw)
        logger.info("adicionarArquivo OK: IdArquivo=%s file=%s", id_arquivo, original_filename)
        return id_arquivo

    async def incluir_documento_externo(
        self,
        numero_processo: str,
        id_arquivo: str,
        original_filename: str,
        tipo_artefato: str,
        identificador_compras: str,
        nivel_acesso: str,
        data: str,
        id_serie_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Include an external document (Tipo=R) in a SEI process.
        Returns dict with id_documento, documento_formatado, link_acesso.
        """
        config = await self._get_config()
        if not self._write_enabled(config):
            raise ValueError(
                "Operações de escrita no SEI estão desabilitadas."
            )

        id_serie = self._resolve_series_id(config, "external", id_serie_override)
        if not id_serie:
            raise ValueError(
                "IdSerie para documento externo não configurado. "
                "Configure SEI_DEFAULT_EXTERNAL_DOCUMENT_SERIES_ID ou no painel admin."
            )

        nivel_numerico = _ACCESS_MAP.get(nivel_acesso, 0)
        nome_arvore = f"{tipo_artefato} — {identificador_compras}"[:200]

        client = await self._get_soap_client(use_write_timeout=True)
        raw = await client.incluir_documento(
            tipo="R",
            protocolo_procedimento=numero_processo,
            id_serie=id_serie,
            numero=identificador_compras[:50],
            data=data,
            nome_arvore=nome_arvore,
            nivel_acesso=nivel_numerico,
            id_arquivo=id_arquivo,
        )
        result = _parse_incluir_documento(raw)
        logger.info(
            "incluirDocumento OK: IdDocumento=%s processo=%s",
            result.get("id_documento"), numero_processo,
        )
        return result

    async def incluir_documento_comprovacao(
        self,
        numero_processo: str,
        html_content: str,
        nivel_acesso: str,
        id_serie_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send the comprovation document to SEI as Tipo=G (generated/internal document).

        Encodes the HTML directly as Base64 and calls incluirDocumento Tipo=G.
        No adicionarArquivo step needed. The document can be signed in SEI.
        """
        config = await self._get_config()
        if not self._write_enabled(config):
            raise ValueError("Operações de escrita no SEI estão desabilitadas.")

        id_serie = self._resolve_series_id(config, "confirmation", id_serie_override)
        if not id_serie:
            raise ValueError(
                "IdSerie para documento de comprovação não configurado. "
                "Configure SEI_DEFAULT_CONFIRMATION_DOCUMENT_SERIES_ID ou no painel admin."
            )

        conteudo_b64 = base64.b64encode(html_content.encode("utf-8")).decode("ascii")
        nivel_numerico = _ACCESS_MAP.get(nivel_acesso, 0)

        client = await self._get_soap_client(use_write_timeout=True)
        raw = await client.incluir_documento_gerado(
            protocolo_procedimento=numero_processo,
            id_serie=id_serie,
            descricao="Documento de Comprovação de Importação",
            nome_arvore="Comprovação de Importação - Compras.gov.br",
            nivel_acesso=nivel_numerico,
            conteudo_base64=conteudo_b64,
        )
        result = _parse_incluir_documento(raw)
        logger.info(
            "Comprovação (Tipo=G) enviada ao SEI: IdDocumento=%s processo=%s",
            result.get("id_documento"), numero_processo,
        )
        return result

    # ── Stubs kept for completeness (write ops handled above) ─────────────────

    async def listar_extensoes_permitidas(self) -> list:
        return ["pdf", "pdfa"]

    async def listar_series(self) -> list:
        """Return list of {id, nome, aplicabilidade} dicts from SEI listarSeries."""
        client = await self._get_soap_client()
        raw = await client.listar_series()
        body = raw.get("Body", raw)
        resp = body.get("listarSeriesResponse", body.get("listarSeriesResult", {}))
        if not isinstance(resp, dict):
            return []
        parametros = resp.get("parametros")
        if not isinstance(parametros, dict):
            return []
        # IFPE SEI wraps series in "item" key; fallback to "Serie"
        series_raw = parametros.get("item") or parametros.get("Serie")
        if series_raw is None:
            return []
        if isinstance(series_raw, dict):
            series_raw = [series_raw]
        if not isinstance(series_raw, list):
            return []
        return [
            {
                "id": s.get("IdSerie", ""),
                "nome": s.get("Nome", ""),
                "aplicabilidade": s.get("Aplicabilidade", ""),
            }
            for s in series_raw
            if isinstance(s, dict)
        ]
