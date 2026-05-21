import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, Upload, FileText, ExternalLink, Shield, Clock,
  Building2, Hash, AlertCircle, Plus, Send, CheckCircle2,
  Loader2, XCircle, AlertTriangle, Trash2,
} from 'lucide-react';
import { useState } from 'react';
import { api, getErrorMessage, openDocumentBlob } from '../lib/api';
import type { SEIProcess, Artifact, DocumentListItem, SendToSEIStatus } from '../types';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

const TYPE_LABELS: Record<string, string> = {
  DFD: 'DFD', ETP: 'ETP', TR: 'Termo de Referência', MATRIZ_RISCOS: 'Matriz de Riscos',
};

const SEI_STATUS_CONFIG: Record<SendToSEIStatus, { label: string; className: string }> = {
  not_sent: { label: 'Não enviado ao SEI', className: 'bg-gray-100 text-gray-600' },
  pending: { label: 'Enviando…', className: 'bg-yellow-100 text-yellow-800' },
  file_uploaded_document_failed: { label: 'Arquivo enviado / Documento falhou', className: 'bg-orange-100 text-orange-800' },
  sent: { label: 'Enviado ao SEI', className: 'bg-green-100 text-green-800' },
  error: { label: 'Erro no envio', className: 'bg-red-100 text-red-800' },
};

const DOC_STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  draft: { label: 'Rascunho', className: 'bg-gray-100 text-gray-600' },
  generated: { label: 'Gerado', className: 'bg-blue-100 text-blue-800' },
  sent_to_sei: { label: 'Enviado ao SEI', className: 'bg-green-100 text-green-800' },
  needs_update: { label: 'Atualização pendente', className: 'bg-yellow-100 text-yellow-800' },
  needs_reissue: { label: 'Reemissão necessária', className: 'bg-orange-100 text-orange-800' },
  reissued: { label: 'Reemitido', className: 'bg-purple-100 text-purple-800' },
  cancelled: { label: 'Cancelado', className: 'bg-gray-100 text-gray-500' },
  error: { label: 'Erro', className: 'bg-red-100 text-red-800' },
};

function SEIStatusBadge({ status }: { status: SendToSEIStatus }) {
  const cfg = SEI_STATUS_CONFIG[status] ?? SEI_STATUS_CONFIG.not_sent;
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${cfg.className}`}>
      {cfg.label}
    </span>
  );
}

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

function ConfirmDialog({ title, message, confirmLabel, onConfirm, onCancel, loading }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
        <div className="flex items-start gap-3 mb-4">
          <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <p className="text-sm text-gray-600 mt-1">{message}</p>
          </div>
        </div>
        <div className="flex justify-end gap-3">
          <button onClick={onCancel} disabled={loading} className="btn-secondary text-sm py-2">
            Cancelar
          </button>
          <button onClick={onConfirm} disabled={loading} className="btn-primary text-sm py-2 flex items-center gap-2">
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ProcessDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [confirmArtifactId, setConfirmArtifactId] = useState<string | null>(null);
  const [confirmDocId, setConfirmDocId] = useState<string | null>(null);
  const [confirmDeleteArtifactId, setConfirmDeleteArtifactId] = useState<string | null>(null);
  const [confirmDeleteDocId, setConfirmDeleteDocId] = useState<string | null>(null);
  const [sendErrors, setSendErrors] = useState<Record<string, string>>({});

  const { data: process, isLoading, error } = useQuery({
    queryKey: ['process', id],
    queryFn: () => api.get<SEIProcess>(`/sei-processes/${id}`).then(r => r.data),
    enabled: !!id,
  });

  const { data: artifacts } = useQuery({
    queryKey: ['artifacts', id],
    queryFn: () => api.get<Artifact[]>(`/artifacts/?sei_process_id=${id}`).then(r => r.data),
    enabled: !!id,
  });

  const { data: documents } = useQuery({
    queryKey: ['documents', id],
    queryFn: () => api.get<DocumentListItem[]>(`/documents/?sei_process_id=${id}`).then(r => r.data),
    enabled: !!id,
  });

  const generateDocMutation = useMutation({
    mutationFn: () => api.post('/documents/generate', { sei_process_id: id }).then(r => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents', id] }),
  });

  const rebuildDocMutation = useMutation({
    mutationFn: (docId: string) => api.post(`/documents/${docId}/rebuild`, {}).then(r => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents', id] }),
    onError: (err) => setSendErrors(prev => ({ ...prev, rebuild: getErrorMessage(err) })),
  });

  const sendArtifactMutation = useMutation({
    mutationFn: (artifactId: string) =>
      api.post(`/artifacts/${artifactId}/send-to-sei`, {}).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['artifacts', id] });
      setConfirmArtifactId(null);
    },
    onError: (err, artifactId) => {
      setSendErrors(prev => ({ ...prev, [artifactId]: getErrorMessage(err) }));
      setConfirmArtifactId(null);
    },
  });

  const sendDocMutation = useMutation({
    mutationFn: (docId: string) =>
      api.post(`/documents/${docId}/send-to-sei`, {}).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', id] });
      setConfirmDocId(null);
    },
    onError: (err, docId) => {
      setSendErrors(prev => ({ ...prev, [docId]: getErrorMessage(err) }));
      setConfirmDocId(null);
    },
  });

  const deleteArtifactMutation = useMutation({
    mutationFn: (artifactId: string) => api.delete(`/artifacts/${artifactId}`).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['artifacts', id] });
      queryClient.invalidateQueries({ queryKey: ['documents', id] });
      setConfirmDeleteArtifactId(null);
    },
    onError: (err) => {
      setSendErrors(prev => ({ ...prev, deleteArtifact: getErrorMessage(err) }));
      setConfirmDeleteArtifactId(null);
    },
  });

  const deleteDocMutation = useMutation({
    mutationFn: (docId: string) => api.delete(`/documents/${docId}`).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', id] });
      setConfirmDeleteDocId(null);
    },
    onError: (err) => {
      setSendErrors(prev => ({ ...prev, deleteDoc: getErrorMessage(err) }));
      setConfirmDeleteDocId(null);
    },
  });

  const fmt = (d: string) => format(new Date(d), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR });

  if (isLoading) return (
    <div className="flex justify-center items-center h-64">
      <span className="w-8 h-8 border-2 border-gov-blue border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (error || !process) return (
    <div className="card p-6 text-center">
      <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
      <p className="text-gray-600">Processo não encontrado</p>
      <Link to="/processos" className="text-primary-600 text-sm mt-2 inline-block">← Voltar</Link>
    </div>
  );

  const confirmingArtifact = confirmArtifactId
    ? artifacts?.find(a => a.id === confirmArtifactId)
    : null;

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Confirm dialogs */}
      {confirmArtifactId && confirmingArtifact && (
        <ConfirmDialog
          title="Enviar artefato ao SEI"
          message={`Isso criará um documento real no processo ${process.numero_processo} no SEI. O arquivo "${confirmingArtifact.original_filename}" será incluído como documento externo (Tipo R). Esta ação não pode ser desfeita.`}
          confirmLabel="Confirmar envio"
          loading={sendArtifactMutation.isPending}
          onConfirm={() => sendArtifactMutation.mutate(confirmArtifactId)}
          onCancel={() => setConfirmArtifactId(null)}
        />
      )}

      {confirmDocId && (
        <ConfirmDialog
          title="Enviar documento de comprovação ao SEI"
          message={`Isso incluirá o documento de comprovação como documento externo no processo ${process.numero_processo} no SEI. Esta ação não pode ser desfeita.`}
          confirmLabel="Confirmar envio"
          loading={sendDocMutation.isPending}
          onConfirm={() => sendDocMutation.mutate(confirmDocId)}
          onCancel={() => setConfirmDocId(null)}
        />
      )}

      {confirmDeleteArtifactId && (
        <ConfirmDialog
          title="Remover artefato"
          message="O artefato será removido do middleware (exclusão lógica). A trilha de auditoria é mantida e o comprovante será atualizado indicando a remoção."
          confirmLabel="Remover artefato"
          loading={deleteArtifactMutation.isPending}
          onConfirm={() => deleteArtifactMutation.mutate(confirmDeleteArtifactId)}
          onCancel={() => setConfirmDeleteArtifactId(null)}
        />
      )}

      {confirmDeleteDocId && (() => {
        const doc = documents?.find(d => d.id === confirmDeleteDocId);
        const alreadySentToSEI = doc?.send_to_sei_status === 'sent';
        return (
          <ConfirmDialog
            title="Apagar documento de comprovação"
            message={
              alreadySentToSEI
                ? `Este comprovante já foi enviado ao SEI (nº ${doc?.sei_document_number}). Apagar aqui NÃO remove o documento do SEI — ele continua no processo. Deseja apagar apenas o registro local?`
                : 'O documento de comprovação será apagado permanentemente. Você poderá gerar um novo comprovante depois.'
            }
            confirmLabel="Apagar comprovante"
            loading={deleteDocMutation.isPending}
            onConfirm={() => deleteDocMutation.mutate(confirmDeleteDocId)}
            onCancel={() => setConfirmDeleteDocId(null)}
          />
        );
      })()}

      <div className="flex items-center gap-3">
        <Link to="/processos" className="text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h2 className="text-lg font-semibold text-gray-900 font-mono">{process.numero_processo}</h2>
          <p className="text-sm text-gray-500">Detalhes do processo SEI</p>
        </div>
      </div>

      {/* Process data */}
      <div className="card p-6">
        <h3 className="section-title mb-5">Dados do Processo</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <InfoRow icon={Hash} label="ID Procedimento" value={process.id_procedimento || '—'} />
          <InfoRow icon={FileText} label="Tipo" value={process.tipo_procedimento_nome || '—'} />
          <InfoRow icon={Building2} label="Unidade" value={
            process.unidade_descricao
              ? `${process.unidade_descricao} (${process.unidade_sigla})`
              : process.unidade_sigla || '—'
          } />
          <InfoRow icon={Clock} label="Data de Autuação" value={process.data_autuacao || '—'} />
          <InfoRow icon={Shield} label="Acesso Local" value={process.nivel_acesso_local || '—'} />
          <InfoRow icon={Shield} label="Acesso Global" value={process.nivel_acesso_global || '—'} />
          {process.especificacao && (
            <div className="md:col-span-2">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Especificação</p>
              <p className="text-sm text-gray-900">{process.especificacao}</p>
            </div>
          )}
          {process.ultimo_andamento?.descricao && (
            <div className="md:col-span-2 bg-blue-50 rounded-lg p-4">
              <p className="text-xs font-medium text-blue-700 uppercase tracking-wide mb-1">Último Andamento</p>
              <p className="text-sm text-blue-900">{process.ultimo_andamento.descricao}</p>
              {process.ultimo_andamento.data_hora && (
                <p className="text-xs text-blue-600 mt-1">
                  {process.ultimo_andamento.data_hora} · {process.ultimo_andamento.unidade_sigla}
                </p>
              )}
            </div>
          )}
          {process.link_acesso && (
            <div className="md:col-span-2">
              <a href={process.link_acesso} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm text-primary-600 hover:underline">
                <ExternalLink className="w-3.5 h-3.5" />
                Acessar no SEI
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        <Link to={`/processos/${id}/importar`} className="btn-primary flex items-center gap-2">
          <Upload className="w-4 h-4" />
          Importar Artefato
        </Link>
      </div>

      {/* Artifacts */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="section-title">Artefatos Importados ({artifacts?.length ?? 0})</h3>
          <Link to={`/processos/${id}/importar`} className="btn-primary text-xs flex items-center gap-1 py-1.5">
            <Plus className="w-3.5 h-3.5" /> Adicionar
          </Link>
        </div>
        {artifacts?.length ? (
          <div className="space-y-3">
            {artifacts.map(a => (
              <div key={a.id} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="text-xs bg-gov-blue text-white px-2 py-0.5 rounded font-medium">
                        {TYPE_LABELS[a.tipo_artefato] || a.tipo_artefato}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                        a.nivel_acesso === 'publico' ? 'bg-green-100 text-green-800' :
                        a.nivel_acesso === 'restrito' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {a.nivel_acesso}
                      </span>
                      {a.document_locked && (
                        <span className="text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded font-medium">
                          Bloqueado
                        </span>
                      )}
                      <SEIStatusBadge status={a.send_to_sei_status ?? 'not_sent'} />
                    </div>
                    <p className="text-sm font-medium text-gray-900">{a.original_filename}</p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      Compras: {a.identificador_compras}
                      {a.observacao ? ` · ${a.observacao}` : ''}
                    </p>
                    <p className="text-xs font-mono text-gray-400 mt-1 break-all">
                      SHA-256: {a.sha256_hash}
                    </p>

                    {/* SEI success info */}
                    {a.send_to_sei_status === 'sent' && a.sei_document_number && (
                      <div className="mt-2 flex items-center gap-2 text-green-700 text-xs">
                        <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
                        <span>Documento SEI: <strong>{a.sei_document_number}</strong></span>
                        {a.sei_document_link && (
                          <a href={a.sei_document_link} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-0.5 hover:underline">
                            <ExternalLink className="w-3 h-3" /> Ver no SEI
                          </a>
                        )}
                      </div>
                    )}

                    {/* Error message */}
                    {(a.send_to_sei_status === 'error' || a.send_to_sei_status === 'file_uploaded_document_failed') && a.send_to_sei_error && (
                      <div className="mt-2 flex items-start gap-1.5 text-red-600 text-xs">
                        <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                        <span>{a.send_to_sei_error}</span>
                      </div>
                    )}

                    {/* Inline send error from mutation */}
                    {sendErrors[a.id] && (
                      <div className="mt-2 flex items-start gap-1.5 text-red-600 text-xs">
                        <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                        <span>{sendErrors[a.id]}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col items-end gap-2 flex-shrink-0">
                    <div className="text-xs text-gray-400 text-right">
                      <p>{fmt(a.created_at)}</p>
                      <p>{(a.file_size / 1024).toFixed(1)} KB</p>
                    </div>
                    {a.send_to_sei_status !== 'sent' && (
                      <button
                        onClick={() => setConfirmArtifactId(a.id)}
                        disabled={sendArtifactMutation.isPending && sendArtifactMutation.variables === a.id}
                        title={a.send_to_sei_status === 'pending' ? 'Envio em andamento…' : 'Enviar para o SEI'}
                        className="btn-secondary text-xs py-1.5 flex items-center gap-1.5"
                      >
                        {sendArtifactMutation.isPending && sendArtifactMutation.variables === a.id
                          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          : <Send className="w-3.5 h-3.5" />
                        }
                        Enviar ao SEI
                      </button>
                    )}
                    {a.send_to_sei_status !== 'sent' && (
                      <button
                        onClick={() => setConfirmDeleteArtifactId(a.id)}
                        disabled={deleteArtifactMutation.isPending}
                        title="Remover artefato"
                        className="text-xs py-1.5 px-2.5 flex items-center gap-1.5 text-red-600 hover:text-red-700 hover:bg-red-50 rounded border border-red-200"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        Remover
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400 text-center py-6">
            Nenhum artefato importado.{' '}
            <Link to={`/processos/${id}/importar`} className="text-primary-600 hover:underline">
              Importar agora
            </Link>
          </p>
        )}
      </div>

      {/* Consolidated comprovante — unique per process */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="section-title">Documento de Comprovação</h3>
          {!documents?.length && (
            <button
              onClick={() => generateDocMutation.mutate()}
              disabled={generateDocMutation.isPending || !artifacts?.length}
              className="btn-secondary text-xs flex items-center gap-1.5 py-1.5"
            >
              {generateDocMutation.isPending
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <FileText className="w-3.5 h-3.5" />}
              Gerar comprovante
            </button>
          )}
        </div>

        {generateDocMutation.isError && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-xs mb-3">
            {getErrorMessage(generateDocMutation.error)}
          </div>
        )}

        {documents?.length ? (() => {
          const doc = documents[0];
          const docStatusCfg = DOC_STATUS_CONFIG[doc.status] ?? DOC_STATUS_CONFIG.draft;
          const needsAttention = ['needs_update', 'needs_reissue'].includes(doc.status);
          return (
            <div className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap gap-2 mb-2">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${docStatusCfg.className}`}>
                      {docStatusCfg.label}
                    </span>
                    <SEIStatusBadge status={doc.send_to_sei_status ?? 'not_sent'} />
                    <span className="text-xs text-gray-400">v{doc.version_number}</span>
                  </div>

                  <p className="text-xs text-gray-500">
                    Criado em {fmt(doc.created_at)}
                    {doc.last_rebuilt_at && ` · Atualizado em ${fmt(doc.last_rebuilt_at)}`}
                  </p>

                  {doc.send_to_sei_status === 'sent' && doc.sei_document_number && (
                    <p className="text-xs text-green-700 mt-1.5 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      SEI: <strong>{doc.sei_document_number}</strong>
                    </p>
                  )}

                  {needsAttention && (
                    <div className="mt-2 flex items-start gap-1.5 text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5 text-xs">
                      <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                      <span>
                        {doc.status === 'needs_reissue'
                          ? 'Este comprovante já foi enviado ao SEI e teve alterações. Verifique se é necessário reemitir.'
                          : 'Conteúdo atualizado localmente. Reenvie ao SEI quando necessário.'}
                      </span>
                    </div>
                  )}

                  {sendErrors[doc.id] && (
                    <p className="text-xs text-red-600 mt-1.5 flex items-start gap-1">
                      <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />{sendErrors[doc.id]}
                    </p>
                  )}
                  {sendErrors['rebuild'] && (
                    <p className="text-xs text-red-600 mt-1.5 flex items-start gap-1">
                      <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />{sendErrors['rebuild']}
                    </p>
                  )}
                  {sendErrors['deleteArtifact'] && (
                    <p className="text-xs text-red-600 mt-1.5 flex items-start gap-1">
                      <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />{sendErrors['deleteArtifact']}
                    </p>
                  )}
                  {sendErrors['deleteDoc'] && (
                    <p className="text-xs text-red-600 mt-1.5 flex items-start gap-1">
                      <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />{sendErrors['deleteDoc']}
                    </p>
                  )}
                </div>

                <div className="flex flex-col gap-1.5 flex-shrink-0">
                  <button
                    onClick={() => openDocumentBlob(doc.id, 'html')}
                    className="btn-secondary text-xs py-1.5 text-center"
                  >
                    Visualizar
                  </button>
                  <button
                    onClick={() => openDocumentBlob(doc.id, 'pdf')}
                    className="btn-secondary text-xs py-1.5 text-center"
                  >
                    PDF
                  </button>
                  <button
                    onClick={() => rebuildDocMutation.mutate(doc.id)}
                    disabled={rebuildDocMutation.isPending}
                    className="btn-secondary text-xs py-1.5 flex items-center gap-1.5"
                    title="Atualizar conteúdo do comprovante"
                  >
                    {rebuildDocMutation.isPending
                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      : <FileText className="w-3.5 h-3.5" />}
                    Atualizar
                  </button>
                  {doc.send_to_sei_status !== 'sent' && (
                    <button
                      onClick={() => setConfirmDocId(doc.id)}
                      disabled={sendDocMutation.isPending && sendDocMutation.variables === doc.id}
                      className="btn-primary text-xs py-1.5 flex items-center gap-1.5"
                    >
                      {sendDocMutation.isPending && sendDocMutation.variables === doc.id
                        ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        : <Send className="w-3.5 h-3.5" />}
                      Enviar ao SEI
                    </button>
                  )}
                  <button
                    onClick={() => setConfirmDeleteDocId(doc.id)}
                    disabled={deleteDocMutation.isPending}
                    title="Apagar comprovante"
                    className="text-xs py-1.5 px-2 flex items-center gap-1.5 text-red-600 hover:text-red-700 hover:bg-red-50 rounded border border-red-200 mt-1"
                  >
                    {deleteDocMutation.isPending
                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      : <Trash2 className="w-3.5 h-3.5" />}
                    Apagar
                  </button>
                </div>
              </div>
            </div>
          );
        })() : (
          <p className="text-sm text-gray-400 text-center py-4">
            Nenhum comprovante gerado.{' '}
            {artifacts?.length
              ? <button onClick={() => generateDocMutation.mutate()} className="text-primary-600 hover:underline">Gerar agora</button>
              : 'Importe artefatos primeiro.'}
          </p>
        )}
      </div>
    </div>
  );
}

function InfoRow({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3">
      <Icon className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
        <p className="text-sm text-gray-900">{value}</p>
      </div>
    </div>
  );
}
