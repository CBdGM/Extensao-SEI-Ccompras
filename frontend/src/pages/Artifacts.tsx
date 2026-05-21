import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Download, Trash2, FileText, Search, AlertCircle } from 'lucide-react';
import { useState } from 'react';
import { api, getErrorMessage, formatFileSize } from '../lib/api';
import type { Artifact } from '../types';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

const TYPE_LABELS: Record<string, string> = {
  DFD: 'DFD', ETP: 'ETP', TR: 'Termo de Referência', MATRIZ_RISCOS: 'Matriz de Riscos',
};

export default function Artifacts() {
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState('');
  const queryClient = useQueryClient();

  const { data: artifacts, isLoading } = useQuery({
    queryKey: ['artifacts-all'],
    queryFn: () => api.get<Artifact[]>('/artifacts/?limit=200').then(r => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/artifacts/${id}`).then(r => r.data),
    onSuccess: () => {
      setDeleteTarget(null);
      setDeleteError('');
      queryClient.invalidateQueries({ queryKey: ['artifacts-all'] });
    },
    onError: (err) => setDeleteError(getErrorMessage(err)),
  });

  const fmt = (d: string) => format(new Date(d), "dd/MM/yyyy HH:mm", { locale: ptBR });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {artifacts?.length ?? 0} artefato(s) importado(s)
        </p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <span className="w-8 h-8 border-2 border-gov-blue border-t-transparent rounded-full animate-spin" />
        </div>
      ) : artifacts?.length ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left">
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Tipo</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Arquivo</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Compras ID</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Acesso</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Hash SHA-256</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Tamanho</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Importado em</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {artifacts.map(a => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <span className="text-xs bg-gov-blue text-white px-2 py-0.5 rounded font-medium">
                        {TYPE_LABELS[a.tipo_artefato] || a.tipo_artefato}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <span className="text-gray-900 font-medium truncate max-w-[150px]">
                          {a.original_filename}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{a.identificador_compras}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                        a.nivel_acesso === 'publico' ? 'bg-green-100 text-green-800' :
                        a.nivel_acesso === 'restrito' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {a.nivel_acesso}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-gray-400" title={a.sha256_hash}>
                        {a.sha256_hash.substring(0, 16)}...
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{formatFileSize(a.file_size)}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{fmt(a.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <a
                          href={`/api/v1/artifacts/${a.id}/download`}
                          className="p-1.5 text-gray-400 hover:text-primary-600 rounded"
                          title="Download"
                        >
                          <Download className="w-4 h-4" />
                        </a>
                        {!a.document_locked && (
                          <button
                            onClick={() => setDeleteTarget(a.id)}
                            className="p-1.5 text-gray-400 hover:text-red-600 rounded"
                            title="Remover"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card text-center py-12">
          <Search className="w-10 h-10 mx-auto mb-2 text-gray-300" />
          <p className="text-gray-400">Nenhum artefato importado</p>
        </div>
      )}

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <AlertCircle className="w-6 h-6 text-red-500" />
              <h3 className="font-semibold text-gray-900">Confirmar remoção</h3>
            </div>
            <p className="text-sm text-gray-600 mb-2">
              O artefato será marcado como removido (exclusão lógica). A trilha de auditoria será mantida.
            </p>
            {deleteError && (
              <p className="text-sm text-red-600 mb-3">{deleteError}</p>
            )}
            <div className="flex justify-end gap-3">
              <button onClick={() => { setDeleteTarget(null); setDeleteError(''); }} className="btn-secondary">
                Cancelar
              </button>
              <button
                onClick={() => deleteMutation.mutate(deleteTarget)}
                disabled={deleteMutation.isPending}
                className="btn-danger flex items-center gap-2"
              >
                {deleteMutation.isPending ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : 'Confirmar remoção'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
