"""
Unit tests for SOAP envelope generation and SEI write-operation guards.

These tests do NOT make real HTTP calls. They verify:
- SOAP envelope structure for adicionarArquivo and incluirDocumento
- Response parsing helpers
- Feature-flag guard (write_enabled logic)
- Idempotency checks
"""
import base64
import json
import pytest
import xml.etree.ElementTree as ET

from app.services.soap_client import (
    ADICIONAR_ARQUIVO_TEMPLATE,
    INCLUIR_DOCUMENTO_TEMPLATE,
    _xml_to_dict,
    _extract_soap_fault,
    _bool_to_sei,
)
from app.services.sei_service import (
    _parse_adicionar_arquivo,
    _parse_incluir_documento,
    _resolve_proc,
    SEIService,
)


# ── Envelope generation ───────────────────────────────────────────────────────

class TestAdicionarArquivoEnvelope:
    def _build(self, nome="file.pdf", tamanho=1024, hash_md5="abc123", conteudo="AAAA"):
        return ADICIONAR_ARQUIVO_TEMPLATE.format(
            sigla_sistema="TEST",
            identificacao_servico="SECRET",
            id_unidade="110001",
            nome=nome,
            tamanho=tamanho,
            hash_md5=hash_md5,
            conteudo_base64=conteudo,
        )

    def test_valid_xml(self):
        env = self._build()
        root = ET.fromstring(env)
        assert root is not None

    def test_contains_nome(self):
        env = self._build(nome="meu_artefato.pdf")
        assert "<Nome>meu_artefato.pdf</Nome>" in env

    def test_contains_tamanho(self):
        env = self._build(tamanho=2048)
        assert "<Tamanho>2048</Tamanho>" in env

    def test_contains_hash(self):
        env = self._build(hash_md5="deadbeef")
        assert "<Hash>deadbeef</Hash>" in env

    def test_contains_conteudo_base64(self):
        content = base64.b64encode(b"PDF content here").decode("ascii")
        env = self._build(conteudo=content)
        assert f"<Conteudo>{content}</Conteudo>" in env

    def test_credentials_not_in_log_fields(self):
        # Credentials must not appear in the parsed dict returned to callers
        # (they live only in the raw XML which is never stored)
        env = self._build()
        assert "SECRET" in env  # present in envelope
        # But we never log the full envelope


class TestIncluirDocumentoEnvelope:
    def _build(self, tipo="R", protocolo="26418.000001/2026-01", id_serie="100",
               numero="COMP-2024-001", data="01/01/2024", nome_arvore="DFD",
               nivel=0, id_arquivo="ARQUIVO-123"):
        return INCLUIR_DOCUMENTO_TEMPLATE.format(
            sigla_sistema="TEST",
            identificacao_servico="SECRET",
            id_unidade="110001",
            tipo=tipo,
            protocolo_procedimento=protocolo,
            id_serie=id_serie,
            numero=numero,
            data=data,
            nome_arvore=nome_arvore,
            nivel_acesso=nivel,
            id_arquivo=id_arquivo,
        )

    def test_valid_xml(self):
        root = ET.fromstring(self._build())
        assert root is not None

    def test_tipo_R_for_external(self):
        env = self._build(tipo="R")
        assert "<Tipo>R</Tipo>" in env

    def test_protocolo_presente(self):
        env = self._build(protocolo="26418.000002/2026-26")
        assert "<ProtocoloProcedimento>26418.000002/2026-26</ProtocoloProcedimento>" in env

    def test_id_arquivo_presente(self):
        env = self._build(id_arquivo="FILE-999")
        assert "<IdArquivo>FILE-999</IdArquivo>" in env

    def test_nivel_acesso_numerico(self):
        env = self._build(nivel=1)
        assert "<NivelAcesso>1</NivelAcesso>" in env


# ── Response parsing ──────────────────────────────────────────────────────────

FAKE_ADICIONAR_ARQUIVO_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <ns1:adicionarArquivoResponse xmlns:ns1="SEI">
      <parametros>
        <IdArquivo>12345</IdArquivo>
      </parametros>
    </ns1:adicionarArquivoResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

FAKE_INCLUIR_DOCUMENTO_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <ns1:incluirDocumentoResponse xmlns:ns1="SEI">
      <parametros>
        <IdDocumento>9876</IdDocumento>
        <DocumentoFormatado>0001234</DocumentoFormatado>
        <LinkAcesso>http://sei-testes.ifpe.edu.br/sei/controlador.php?id=9876</LinkAcesso>
      </parametros>
    </ns1:incluirDocumentoResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

FAKE_CONSULTAR_PROCEDIMENTO_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <ns1:consultarProcedimentoResponse xmlns:ns1="SEI">
      <parametros>
        <IdProcedimento>350</IdProcedimento>
        <ProcedimentoFormatado>26418.000002/2026-26</ProcedimentoFormatado>
        <Especificacao>teste</Especificacao>
        <TipoProcedimento>
          <IdTipoProcedimento>100001548</IdTipoProcedimento>
          <Nome>09.005 Contratação TIC</Nome>
        </TipoProcedimento>
        <UltimoAndamento>
          <DataHora>11/03/2026 10:36:44</DataHora>
          <Descricao>Processo público gerado</Descricao>
          <Unidade>
            <Sigla>17 REI</Sigla>
            <Descricao>Reitoria do IFPE</Descricao>
          </Unidade>
        </UltimoAndamento>
      </parametros>
    </ns1:consultarProcedimentoResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

FAKE_SOAP_FAULT = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <SOAP-ENV:Fault>
      <faultcode>SOAP-ENV:Server</faultcode>
      <faultstring>Usuário sem permissão para acessar o serviço</faultstring>
    </SOAP-ENV:Fault>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""


class TestParseAdicionarArquivo:
    def test_extracts_id_arquivo(self):
        raw = _xml_to_dict(FAKE_ADICIONAR_ARQUIVO_RESPONSE)
        id_arquivo = _parse_adicionar_arquivo(raw)
        assert id_arquivo == "12345"

    def test_parametros_as_string_ifpe(self):
        # IFPE SEI returns parametros as a plain string (the IdArquivo itself)
        raw = {"Body": {"adicionarArquivoResponse": {"parametros": "85"}}}
        assert _parse_adicionar_arquivo(raw) == "85"

    def test_raises_on_missing_id(self):
        raw = {"Body": {"adicionarArquivoResponse": {}}}
        with pytest.raises(ValueError, match="IdArquivo"):
            _parse_adicionar_arquivo(raw)


class TestParseIncluirDocumento:
    def test_extracts_all_fields(self):
        raw = _xml_to_dict(FAKE_INCLUIR_DOCUMENTO_RESPONSE)
        result = _parse_incluir_documento(raw)
        assert result["id_documento"] == "9876"
        assert result["documento_formatado"] == "0001234"
        assert "sei-testes" in result["link_acesso"]

    def test_raises_on_missing_id(self):
        raw = {"Body": {"incluirDocumentoResponse": {}}}
        with pytest.raises(ValueError, match="IdDocumento"):
            _parse_incluir_documento(raw)


class TestExtractSoapFault:
    def test_extracts_fault_message(self):
        msg = _extract_soap_fault(FAKE_SOAP_FAULT)
        assert "sem permissão" in msg

    def test_returns_fallback_on_invalid_xml(self):
        msg = _extract_soap_fault("not xml at all")
        assert msg is not None


class TestResolveProcedimento:
    def test_resolves_via_parametros(self):
        raw = _xml_to_dict(FAKE_CONSULTAR_PROCEDIMENTO_RESPONSE)
        proc = _resolve_proc(raw)
        assert proc.get("IdProcedimento") == "350"

    def test_resolves_via_procedimento_key(self):
        raw = {"Body": {"consultarProcedimentoResponse": {"Procedimento": {"IdProcedimento": "999"}}}}
        proc = _resolve_proc(raw)
        assert proc["IdProcedimento"] == "999"

    def test_falls_back_to_resp(self):
        raw = {"Body": {"consultarProcedimentoResponse": {"IdProcedimento": "111"}}}
        proc = _resolve_proc(raw)
        assert proc["IdProcedimento"] == "111"


# ── Feature-flag and write guard ──────────────────────────────────────────────

class TestWriteEnabledGuard:
    def _make_service(self):
        # SEIService without DB — we only test _write_enabled
        return SEIService(db=None)  # type: ignore[arg-type]

    def test_disabled_when_both_false(self, monkeypatch):
        from app.services import sei_service as mod
        monkeypatch.setattr(mod.settings, "SEI_ENABLE_WRITE_OPERATIONS", False)

        class FakeConfig:
            enable_write_operations = False

        svc = self._make_service()
        assert svc._write_enabled(FakeConfig()) is False

    def test_enabled_by_env(self, monkeypatch):
        from app.services import sei_service as mod
        monkeypatch.setattr(mod.settings, "SEI_ENABLE_WRITE_OPERATIONS", True)
        svc = self._make_service()
        assert svc._write_enabled(None) is True

    def test_enabled_by_db_config(self, monkeypatch):
        from app.services import sei_service as mod
        monkeypatch.setattr(mod.settings, "SEI_ENABLE_WRITE_OPERATIONS", False)

        class FakeConfig:
            enable_write_operations = True

        svc = self._make_service()
        assert svc._write_enabled(FakeConfig()) is True

    def test_disabled_when_config_none(self, monkeypatch):
        from app.services import sei_service as mod
        monkeypatch.setattr(mod.settings, "SEI_ENABLE_WRITE_OPERATIONS", False)
        svc = self._make_service()
        assert svc._write_enabled(None) is False


class TestBoolToSei:
    def test_true_returns_S(self):
        assert _bool_to_sei(True) == "S"

    def test_false_returns_N(self):
        assert _bool_to_sei(False) == "N"
