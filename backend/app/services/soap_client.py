"""
Low-level SOAP client for SEI Web Service.

Builds XML envelopes, sends HTTP requests, parses responses.
Credentials are injected at call time and never logged.
"""
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# ── Envelope templates ────────────────────────────────────────────────────────

CONSULTAR_PROCEDIMENTO_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
  xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:sei="SEI">
  <soapenv:Header/>
  <soapenv:Body>
    <sei:consultarProcedimento>
      <SiglaSistema>{sigla_sistema}</SiglaSistema>
      <IdentificacaoServico>{identificacao_servico}</IdentificacaoServico>
      <IdUnidade>{id_unidade}</IdUnidade>
      <ProtocoloProcedimento>{protocolo}</ProtocoloProcedimento>
      <SinRetornarAssuntos>{sin_assuntos}</SinRetornarAssuntos>
      <SinRetornarInteressados>{sin_interessados}</SinRetornarInteressados>
      <SinRetornarObservacoes>{sin_observacoes}</SinRetornarObservacoes>
      <SinRetornarAndamentoGeracao>N</SinRetornarAndamentoGeracao>
      <SinRetornarAndamentoConclusao>N</SinRetornarAndamentoConclusao>
      <SinRetornarUltimoAndamento>{sin_ultimo_andamento}</SinRetornarUltimoAndamento>
      <SinRetornarUnidadesProcedimentoAberto>{sin_unidades}</SinRetornarUnidadesProcedimentoAberto>
      <SinRetornarProcedimentosRelacionados>S</SinRetornarProcedimentosRelacionados>
      <SinRetornarProcedimentosAnexados>S</SinRetornarProcedimentosAnexados>
    </sei:consultarProcedimento>
  </soapenv:Body>
</soapenv:Envelope>"""

ADICIONAR_ARQUIVO_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
  xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:sei="SEI">
  <soapenv:Header/>
  <soapenv:Body>
    <sei:adicionarArquivo>
      <SiglaSistema>{sigla_sistema}</SiglaSistema>
      <IdentificacaoServico>{identificacao_servico}</IdentificacaoServico>
      <IdUnidade>{id_unidade}</IdUnidade>
      <Nome>{nome}</Nome>
      <Tamanho>{tamanho}</Tamanho>
      <Hash>{hash_md5}</Hash>
      <Conteudo>{conteudo_base64}</Conteudo>
    </sei:adicionarArquivo>
  </soapenv:Body>
</soapenv:Envelope>"""

INCLUIR_DOCUMENTO_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
  xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:sei="SEI">
  <soapenv:Header/>
  <soapenv:Body>
    <sei:incluirDocumento>
      <SiglaSistema>{sigla_sistema}</SiglaSistema>
      <IdentificacaoServico>{identificacao_servico}</IdentificacaoServico>
      <IdUnidade>{id_unidade}</IdUnidade>
      <Documento>
        <Tipo>{tipo}</Tipo>
        <ProtocoloProcedimento>{protocolo_procedimento}</ProtocoloProcedimento>
        <IdSerie>{id_serie}</IdSerie>
        <Numero>{numero}</Numero>
        <Data>{data}</Data>
        <NomeArvore>{nome_arvore}</NomeArvore>
        <NivelAcesso>{nivel_acesso}</NivelAcesso>
        <IdArquivo>{id_arquivo}</IdArquivo>
      </Documento>
    </sei:incluirDocumento>
  </soapenv:Body>
</soapenv:Envelope>"""

LISTAR_SERIES_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
  xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:sei="SEI">
  <soapenv:Header/>
  <soapenv:Body>
    <sei:listarSeries>
      <SiglaSistema>{sigla_sistema}</SiglaSistema>
      <IdentificacaoServico>{identificacao_servico}</IdentificacaoServico>
      <IdUnidade>{id_unidade}</IdUnidade>
      <IdTipoProcedimento></IdTipoProcedimento>
    </sei:listarSeries>
  </soapenv:Body>
</soapenv:Envelope>"""

# Used for Tipo=G (generated document with HTML content)
INCLUIR_DOCUMENTO_GERADO_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
  xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:sei="SEI">
  <soapenv:Header/>
  <soapenv:Body>
    <sei:incluirDocumento>
      <SiglaSistema>{sigla_sistema}</SiglaSistema>
      <IdentificacaoServico>{identificacao_servico}</IdentificacaoServico>
      <IdUnidade>{id_unidade}</IdUnidade>
      <Documento>
        <Tipo>G</Tipo>
        <ProtocoloProcedimento>{protocolo_procedimento}</ProtocoloProcedimento>
        <IdSerie>{id_serie}</IdSerie>
        <Descricao>{descricao}</Descricao>
        <NomeArvore>{nome_arvore}</NomeArvore>
        <NivelAcesso>{nivel_acesso}</NivelAcesso>
        <Conteudo>{conteudo_base64}</Conteudo>
      </Documento>
    </sei:incluirDocumento>
  </soapenv:Body>
</soapenv:Envelope>"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _bool_to_sei(value: bool) -> str:
    return "S" if value else "N"


def _parse_element(el: ET.Element) -> Any:
    """Recursively convert XML element to dict/list/str."""
    children = list(el)
    if not children:
        return el.text or ""
    result: Dict[str, Any] = {}
    for child in children:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        parsed = _parse_element(child)
        if tag in result:
            if not isinstance(result[tag], list):
                result[tag] = [result[tag]]
            result[tag].append(parsed)
        else:
            result[tag] = parsed
    return result


def _xml_to_dict(xml_string: str) -> Dict[str, Any]:
    try:
        root = ET.fromstring(xml_string)
        return _parse_element(root)
    except ET.ParseError as e:
        logger.error("XML parse error: %s", str(e))
        return {}


def _extract_soap_fault(xml_string: str) -> Optional[str]:
    """Extract faultstring from a SOAP Fault response body."""
    try:
        root = ET.fromstring(xml_string)
        for fault in root.iter():
            tag = fault.tag.split("}")[-1] if "}" in fault.tag else fault.tag
            if tag.lower() == "faultstring":
                return fault.text or "Erro SOAP sem descrição"
        preview = xml_string[:300].replace("\n", " ")
        return f"SOAP Fault: {preview}"
    except Exception:
        return "Resposta de erro do SEI não pôde ser interpretada"


# ── SOAPClient ────────────────────────────────────────────────────────────────

class SOAPClient:
    def __init__(
        self,
        soap_url: str,
        sigla_sistema: str,
        identificacao_servico: str,
        id_unidade: str,
        timeout: int = 30,
        write_timeout: int = 30,
        max_retries: int = 3,
    ):
        self.soap_url = soap_url
        self.sigla_sistema = sigla_sistema
        self._identificacao_servico = identificacao_servico
        self.id_unidade = id_unidade
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.max_retries = max_retries

    async def _post(self, envelope: str, timeout: int) -> Dict[str, Any]:
        """Send a SOAP envelope; parse and return the response dict."""
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"SeiAction"',
        }
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                    response = await client.post(
                        self.soap_url,
                        content=envelope.encode("utf-8"),
                        headers=headers,
                    )
                    if response.status_code == 500:
                        fault_msg = _extract_soap_fault(response.text)
                        logger.error("SOAP Fault (attempt %d): %s", attempt, fault_msg)
                        raise ConnectionError(f"SEI retornou erro: {fault_msg}")
                    response.raise_for_status()
                    return _xml_to_dict(response.text)
            except ConnectionError:
                raise
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning("SOAP timeout on attempt %d", attempt)
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.error("SOAP HTTP error %d on attempt %d", e.response.status_code, attempt)
                break
            except Exception as e:
                last_error = e
                logger.error("SOAP unexpected error on attempt %d: %s", attempt, type(e).__name__)
                break

        raise ConnectionError(
            f"Falha na comunicação com o SEI após {self.max_retries} tentativas"
        ) from last_error

    # ── Read operations ───────────────────────────────────────────────────────

    async def consultar_procedimento(
        self,
        protocolo: str,
        sin_assuntos: bool = True,
        sin_interessados: bool = True,
        sin_observacoes: bool = True,
        sin_ultimo_andamento: bool = True,
        sin_unidades: bool = True,
    ) -> Dict[str, Any]:
        logger.info(
            "SOAP consultarProcedimento attempt to %s for process %s",
            self.soap_url, protocolo,
        )
        envelope = CONSULTAR_PROCEDIMENTO_TEMPLATE.format(
            sigla_sistema=self.sigla_sistema,
            identificacao_servico=self._identificacao_servico,
            id_unidade=self.id_unidade,
            protocolo=protocolo,
            sin_assuntos=_bool_to_sei(sin_assuntos),
            sin_interessados=_bool_to_sei(sin_interessados),
            sin_observacoes=_bool_to_sei(sin_observacoes),
            sin_ultimo_andamento=_bool_to_sei(sin_ultimo_andamento),
            sin_unidades=_bool_to_sei(sin_unidades),
        )
        return await self._post(envelope, self.timeout)

    # ── Write operations ──────────────────────────────────────────────────────

    async def adicionar_arquivo(
        self,
        nome: str,
        tamanho: int,
        hash_md5: str,
        conteudo_base64: str,
    ) -> Dict[str, Any]:
        """Call adicionarArquivo; returns raw parsed SOAP response."""
        # Log operation intent without any credentials or file content
        logger.info(
            "SOAP adicionarArquivo: file=%s size=%d", nome, tamanho
        )
        envelope = ADICIONAR_ARQUIVO_TEMPLATE.format(
            sigla_sistema=self.sigla_sistema,
            identificacao_servico=self._identificacao_servico,
            id_unidade=self.id_unidade,
            nome=nome,
            tamanho=tamanho,
            hash_md5=hash_md5,
            conteudo_base64=conteudo_base64,
        )
        return await self._post(envelope, self.write_timeout)

    async def incluir_documento(
        self,
        tipo: str,
        protocolo_procedimento: str,
        id_serie: str,
        numero: str,
        data: str,
        nome_arvore: str,
        nivel_acesso: int,
        id_arquivo: str,
    ) -> Dict[str, Any]:
        """Call incluirDocumento with Tipo=R (external/received document)."""
        logger.info(
            "SOAP incluirDocumento: tipo=%s processo=%s serie=%s",
            tipo, protocolo_procedimento, id_serie,
        )
        envelope = INCLUIR_DOCUMENTO_TEMPLATE.format(
            sigla_sistema=self.sigla_sistema,
            identificacao_servico=self._identificacao_servico,
            id_unidade=self.id_unidade,
            tipo=tipo,
            protocolo_procedimento=protocolo_procedimento,
            id_serie=id_serie,
            numero=numero,
            data=data,
            nome_arvore=nome_arvore,
            nivel_acesso=nivel_acesso,
            id_arquivo=id_arquivo,
        )
        return await self._post(envelope, self.write_timeout)

    async def incluir_documento_gerado(
        self,
        protocolo_procedimento: str,
        id_serie: str,
        descricao: str,
        nome_arvore: str,
        nivel_acesso: int,
        conteudo_base64: str,
    ) -> Dict[str, Any]:
        """Call incluirDocumento with Tipo=G (generated document with HTML content)."""
        logger.info(
            "SOAP incluirDocumento (gerado): processo=%s serie=%s",
            protocolo_procedimento, id_serie,
        )
        envelope = INCLUIR_DOCUMENTO_GERADO_TEMPLATE.format(
            sigla_sistema=self.sigla_sistema,
            identificacao_servico=self._identificacao_servico,
            id_unidade=self.id_unidade,
            protocolo_procedimento=protocolo_procedimento,
            id_serie=id_serie,
            descricao=descricao,
            nome_arvore=nome_arvore,
            nivel_acesso=nivel_acesso,
            conteudo_base64=conteudo_base64,
        )
        return await self._post(envelope, self.write_timeout)

    async def listar_series(self) -> Dict[str, Any]:
        """Call listarSeries to retrieve all document series available in the unit."""
        logger.info("SOAP listarSeries: unidade=%s", self.id_unidade)
        envelope = LISTAR_SERIES_TEMPLATE.format(
            sigla_sistema=self.sigla_sistema,
            identificacao_servico=self._identificacao_servico,
            id_unidade=self.id_unidade,
        )
        return await self._post(envelope, self.timeout)
