import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FileText, Eye, Download, AlertCircle, Send, CheckCircle2,
  Loader2, XCircle, AlertTriangle, Info,
} from 'lucide-react';
import { api, getErrorMessage, openDocumentBlob } from '../lib/api';
import type { DocumentListItem, SEIWriteStatus, SendToSEIStatus } from '../types';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  draft: { label: 'Rascunho', className: 'bg-gray-100 text-gray-600' },
  generated: { label: 'Gerado', className: 'bg-blue-100 text-blue-800' },
  sent_to_sei: { label: 'Enviado ao SEI', className: 'bg-green-100 text-green-800' },
  needs_update: { label: 'Atualização pendente', className: 'bg-yellow-100 text-yellow-800' },
  needs_reissue: { label: 'Reemissão necessária', className: 'bg-orange-100 text-orange-800' },
  reissued: { label: 'Reemitido', className: 'bg-purple-100 text-purple-800' },
  cancelled: { label: 'Cancelado', className: 'bg-gray-100 text-gray-600' },
  error: { label: 'Erro', className: 'bg-red-100 text-red-800' },
};

const SEI_SEND_STATUS_CONFIG: Record<SendToSEIStatus, { label: string; className: string }> = {
  not_sent: { label: 'Não enviado', className: 'bg-gray-100 text-gray-600' },
  pending: { label: 'Enviando…', className: 'bg-yellow-100 text-yellow-800' },
  file_uploaded_document_failed: { label: 'Parcialmente enviado', className: 'bg-orange-100 text-orange-800' },
  sent: { label: 'Enviado ao SEI', className: 'bg-green-100 text-green-800' },
  error: { label: 'Erro no envio', className: 'bg-red-100 text-red-800' },
};

interface ConfirmDialogProps {
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}

function ConfirmDialog({ onConfirm, onCancel, loading }: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
        <div className="flex items-start gap-3 mb-4">
          <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-gray-900">Enviar documento de comprovação ao SEI</h3>
            <p className="text-sm text-gray-600 mt-1">
              Isso incluirá o documento de comprovação como documento externo no SEI.
              Esta ação <strong>não pode ser desfeita</strong>.
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3">
          <button onClick={onCancel} disabled={loading} className="btn-secondary text-sm py-2">
            Cancelar
          </button>
          <button onClick={onConfirm} disabled={loading} className="btn-primary text-sm py-2 flex items-center gap-2">
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Confirmar envio
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Documents() {
  const queryClient = useQueryClient();
  const [confirmDocId, setConfirmDocId] = useState<string | null>(null);
  const [sendErrors, setSendErrors] = useState<Record<string, string>>({});

  const { data: documents, isLoading } = useQuery({
    queryKey: ['documents-all'],
    queryFn: () => api.get<DocumentListItem[]>('/documents/?limit=100').then(r => r.data),
  });

  const { data: writeStatus } = useQuery({
    queryKey: ['sei-write-status'],
    queryFn: () => api.get<SEIWriteStatus>('/sei-config/write-status').then(r => r.data),
    retry: false,
  });

  const sendDocMutation = useMutation({
    mutationFn: (docId: string) =>
      api.post(`/documents/${docId}/send-to-sei`, {}).then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents-all'] });
      setConfirmDocId(null);
    },
    onError: (err, docId) => {
      setSendErrors(prev => ({ ...prev, [docId]: getErrorMessage(err) }));
      setConfirmDocId(null);
    },
  });

  const fmt = (d: string) => format(new Date(d), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR });
  const writeEnabled = writeStatus?.write_enabled ?? false;

  return (
    <div className="space-y-4">
      {confirmDocId && (
        <ConfirmDialog
          loading={sendDocMutation.isPending}
          onConfirm={() => sendDocMutation.mutate(confirmDocId)}
          onCancel={() => setConfirmDocId(null)}
        />
      )}

      {/* Write status banner */}
      {writeStatus && !writeEnabled && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3">
          <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-amber-800">
            <p className="font-medium mb-1">Envio ao SEI desabilitado</p>
            <p>
              Para habilitar, configure <code>SEI_ENABLE_WRITE_OPERATIONS=true</code> ou
              ative a opção em <strong>Configuração SEI</strong> no painel admin.
            </p>
          </div>
        </div>
      )}

      {writeStatus && writeEnabled && !writeStatus.confirmation_series_configured && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3">
          <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-amber-800">
            <p className="font-medium mb-1">IdSerie não configurado</p>
            <p>
              Defina <code>SEI_DEFAULT_CONFIRMATION_DOCUMENT_SERIES_ID</code> ou configure o campo
              "IdSérie (comprovação)" em <strong>Configuração SEI</strong>.
            </p>
          </div>
        </div>
      )}

      {writeStatus && writeEnabled && writeStatus.confirmation_series_configured && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex gap-3">
          <Info className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-green-800">
            Envio ao SEI ativado via <strong>{writeStatus.source === 'env' ? 'variável de ambiente' : 'configuração no banco'}</strong>.
            Use o botão <em>Enviar ao SEI</em> em cada documento para incluí-lo no processo SEI.
          </p>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12">
          <span className="w-8 h-8 border-2 border-gov-blue border-t-transparent rounded-full animate-spin" />
        </div>
      ) : documents?.length ? (
        <div className="space-y-3">
          {documents.map(doc => {
            const statusConf = STATUS_CONFIG[doc.status] || STATUS_CONFIG.generated;
            const seiConf = SEI_SEND_STATUS_CONFIG[doc.send_to_sei_status ?? 'not_sent'];
            const alreadySent = doc.send_to_sei_status === 'sent';
            const isSending = sendDocMutation.isPending && sendDocMutation.variables === doc.id;

            return (
              <div key={doc.id} className="card p-5 flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                    <FileText className="w-5 h-5 text-gov-blue" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-900">
                      Documento de Comprovação
                    </p>
                    <p className="text-xs text-gray-500 font-mono mt-0.5">
                      Processo: {doc.numero_processo || doc.sei_process_id}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Gerado por {doc.user_name || 'usuário'} em {fmt(doc.created_at)}
                      {doc.last_rebuilt_at && ` · Atualizado em ${fmt(doc.last_rebuilt_at)}`}
                      {` · v${doc.version_number}`}
                    </p>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${statusConf.className}`}>
                        {statusConf.label}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${seiConf.className}`}>
                        {seiConf.label}
                      </span>
                    </div>

                    {alreadySent && doc.sei_document_number && (
                      <p className="text-xs text-green-700 mt-1.5 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
                        SEI: <strong>{doc.sei_document_number}</strong>
                      </p>
                    )}

                    {sendErrors[doc.id] && (
                      <p className="text-xs text-red-600 mt-1 flex items-start gap-1">
                        <XCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                        {sendErrors[doc.id]}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0 flex-wrap justify-end">
                  <button
                    onClick={() => openDocumentBlob(doc.id, 'html')}
                    className="btn-secondary flex items-center gap-1.5 text-xs py-1.5"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Visualizar
                  </button>
                  <button
                    onClick={() => openDocumentBlob(doc.id, 'pdf')}
                    className="btn-primary flex items-center gap-1.5 text-xs py-1.5"
                  >
                    <Download className="w-3.5 h-3.5" />
                    PDF
                  </button>
                  {!alreadySent && (
                    <button
                      onClick={() => setConfirmDocId(doc.id)}
                      disabled={!writeEnabled || isSending}
                      title={!writeEnabled ? 'Habilite SEI_ENABLE_WRITE_OPERATIONS para enviar' : 'Enviar ao SEI'}
                      className="btn-secondary flex items-center gap-1.5 text-xs py-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isSending
                        ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        : <Send className="w-3.5 h-3.5" />
                      }
                      Enviar ao SEI
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="card text-center py-12">
          <FileText className="w-10 h-10 mx-auto mb-2 text-gray-300" />
          <p className="text-gray-400 text-sm">Nenhum documento gerado ainda</p>
          <p className="text-gray-400 text-xs mt-1">
            Consulte um processo, importe artefatos e clique em "Gerar Documento de Comprovação"
          </p>
        </div>
      )}
    </div>
  );
}
