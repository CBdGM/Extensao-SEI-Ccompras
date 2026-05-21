import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Search, FileSearch, AlertCircle, CheckCircle, ArrowRight, Trash2, Loader2, AlertTriangle } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { api, getErrorMessage } from '../lib/api';
import type { SEIQueryResponse, SEIProcessListItem } from '../types';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface FormData { numero_processo: string }

function ConfirmDeleteDialog({
  process,
  onConfirm,
  onCancel,
  loading,
  error,
}: {
  process: SEIProcessListItem;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
  error: string;
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
        <div className="flex items-start gap-3 mb-4">
          <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-gray-900">Excluir processo</h3>
            <p className="text-sm text-gray-600 mt-1">
              Isso excluirá permanentemente o processo{' '}
              <strong className="font-mono">{process.numero_processo}</strong> e{' '}
              <strong>todos os artefatos e comprovantes associados</strong>, incluindo os
              arquivos físicos. Esta ação <strong>não pode ser desfeita</strong>.
            </p>
            {process.artifacts_count > 0 && (
              <p className="text-xs text-red-600 mt-2 bg-red-50 border border-red-200 rounded px-2 py-1">
                {process.artifacts_count} artefato(s) serão excluídos junto com seus arquivos.
              </p>
            )}
            {error && (
              <p className="text-xs text-red-600 mt-2">{error}</p>
            )}
          </div>
        </div>
        <div className="flex justify-end gap-3">
          <button onClick={onCancel} disabled={loading} className="btn-secondary text-sm py-2">
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="text-sm py-2 px-4 bg-red-600 hover:bg-red-700 text-white rounded font-medium flex items-center gap-2 disabled:opacity-50"
          >
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Excluir processo
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SEIProcess() {
  const [queryResult, setQueryResult] = useState<SEIQueryResponse | null>(null);
  const [queryError, setQueryError] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState('');
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>();

  const { data: processes, isLoading } = useQuery({
    queryKey: ['processes-list'],
    queryFn: () => api.get<SEIProcessListItem[]>('/sei-processes/?limit=20').then(r => r.data),
  });

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      api.post<SEIQueryResponse>('/sei-processes/query', data).then(r => r.data),
    onSuccess: (data) => {
      setQueryResult(data);
      setQueryError('');
      queryClient.invalidateQueries({ queryKey: ['processes-list'] });
      if (data.process?.id) {
        navigate(`/processos/${data.process.id}`);
      }
    },
    onError: (err) => {
      setQueryError(getErrorMessage(err));
      setQueryResult(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (processId: string) => api.delete(`/sei-processes/${processId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['processes-list'] });
      setConfirmDeleteId(null);
      setDeleteError('');
    },
    onError: (err) => setDeleteError(getErrorMessage(err)),
  });

  const formatDate = (d: string) =>
    format(new Date(d), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR });

  const confirmingProcess = confirmDeleteId
    ? processes?.find(p => p.id === confirmDeleteId)
    : null;

  return (
    <div className="space-y-6 max-w-4xl">
      {confirmingProcess && (
        <ConfirmDeleteDialog
          process={confirmingProcess}
          loading={deleteMutation.isPending}
          error={deleteError}
          onConfirm={() => deleteMutation.mutate(confirmDeleteId!)}
          onCancel={() => { setConfirmDeleteId(null); setDeleteError(''); }}
        />
      )}

      {/* Search form */}
      <div className="card p-6">
        <h3 className="section-title mb-5">Consultar Processo no SEI</h3>
        <form onSubmit={handleSubmit((d) => mutation.mutate(d))} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Número do Processo SEI
            </label>
            <div className="flex gap-3">
              <div className="flex-1">
                <input
                  type="text"
                  className="input-field font-mono"
                  placeholder="23298.000001/2024-01"
                  {...register('numero_processo', {
                    required: 'Número do processo é obrigatório',
                    pattern: {
                      value: /^\d{5}\.\d{6}\/\d{4}-\d{2}$/,
                      message: 'Formato inválido. Exemplo: 23298.000001/2024-01',
                    },
                  })}
                />
                {errors.numero_processo && (
                  <p className="text-red-500 text-xs mt-1">{errors.numero_processo.message}</p>
                )}
              </div>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="btn-primary flex items-center gap-2 whitespace-nowrap"
              >
                {mutation.isPending ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Search className="w-4 h-4" />
                )}
                {mutation.isPending ? 'Consultando...' : 'Consultar Processo'}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Formato: NNNNN.NNNNNN/AAAA-NN — ex: 23298.000001/2024-01
            </p>
          </div>

          {queryError && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-medium">Erro ao consultar processo</p>
                <p>{queryError}</p>
              </div>
            </div>
          )}

          {queryResult?.status === 'success' && (
            <div className="flex items-start gap-2 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md text-sm">
              <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <p>Processo consultado com sucesso! Redirecionando para os detalhes...</p>
            </div>
          )}
        </form>
      </div>

      {/* Privacy notice */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
        <p className="font-medium mb-1">Transparência no uso dos dados</p>
        <p>
          Ao consultar um processo, os seguintes dados são recuperados do SEI e armazenados neste sistema:
          número do processo, especificação, tipo, unidade, data de autuação, nível de acesso e último andamento.
          Todas as consultas são registradas em log de auditoria com identificação do usuário e data/hora.
        </p>
      </div>

      {/* Process list */}
      <div className="card p-5">
        <h3 className="section-title mb-4">Processos Consultados</h3>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <span className="w-6 h-6 border-2 border-gov-blue border-t-transparent rounded-full animate-spin" />
          </div>
        ) : processes?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left">
                  <th className="px-3 py-2.5 text-xs font-semibold text-gray-600 uppercase tracking-wide">Processo</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-gray-600 uppercase tracking-wide">Especificação</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-gray-600 uppercase tracking-wide">Unidade</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-gray-600 uppercase tracking-wide">Artefatos</th>
                  <th className="px-3 py-2.5 text-xs font-semibold text-gray-600 uppercase tracking-wide">Consultado em</th>
                  <th className="px-3 py-2.5"></th>
                  <th className="px-3 py-2.5"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {processes.map(p => (
                  <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-3 py-3 font-mono font-medium text-gov-blue">{p.numero_processo}</td>
                    <td className="px-3 py-3 text-gray-600 max-w-[200px] truncate">{p.especificacao || '—'}</td>
                    <td className="px-3 py-3 text-gray-500">{p.unidade_sigla || '—'}</td>
                    <td className="px-3 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        p.artifacts_count > 0 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                      }`}>
                        {p.artifacts_count} arquivo(s)
                      </span>
                    </td>
                    <td className="px-3 py-3 text-gray-400 text-xs">{formatDate(p.created_at)}</td>
                    <td className="px-3 py-3">
                      <Link to={`/processos/${p.id}`} className="text-primary-600 hover:text-primary-800">
                        <ArrowRight className="w-4 h-4" />
                      </Link>
                    </td>
                    <td className="px-3 py-3">
                      <button
                        onClick={() => { setConfirmDeleteId(p.id); setDeleteError(''); }}
                        title="Excluir processo"
                        className="text-gray-400 hover:text-red-600 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-10 text-gray-400">
            <FileSearch className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Nenhum processo consultado ainda</p>
          </div>
        )}
      </div>
    </div>
  );
}
