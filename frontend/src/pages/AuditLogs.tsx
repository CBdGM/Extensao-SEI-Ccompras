import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ClipboardList, Search } from 'lucide-react';
import { api } from '../lib/api';
import type { AuditLog } from '../types';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

const ACTION_COLORS: Record<string, string> = {
  LOGIN_SUCCESS: 'bg-green-100 text-green-800',
  LOGIN_FAILED: 'bg-red-100 text-red-800',
  LOGOUT: 'bg-gray-100 text-gray-600',
  SEI_PROCESS_QUERIED: 'bg-blue-100 text-blue-800',
  SEI_QUERY_FAILED: 'bg-red-100 text-red-800',
  ARTIFACT_UPLOADED: 'bg-purple-100 text-purple-800',
  ARTIFACT_DELETED: 'bg-orange-100 text-orange-800',
  ARTIFACT_DOWNLOADED: 'bg-indigo-100 text-indigo-800',
  DOCUMENT_GENERATED: 'bg-teal-100 text-teal-800',
  DOCUMENT_VIEWED: 'bg-gray-100 text-gray-600',
  SEI_CONFIG_CREATED: 'bg-yellow-100 text-yellow-800',
  SEI_CONFIG_UPDATED: 'bg-yellow-100 text-yellow-800',
  USER_CREATED: 'bg-green-100 text-green-800',
  USER_UPDATED: 'bg-blue-100 text-blue-800',
  PASSWORD_CHANGED: 'bg-orange-100 text-orange-800',
};

export default function AuditLogs() {
  const [search, setSearch] = useState('');
  const [selectedEntity, setSelectedEntity] = useState('');

  const { data: logs, isLoading } = useQuery({
    queryKey: ['audit-logs', search, selectedEntity],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search) params.set('action', search);
      if (selectedEntity) params.set('entity_type', selectedEntity);
      params.set('limit', '200');
      return api.get<AuditLog[]>(`/audit/?${params}`).then(r => r.data);
    },
  });

  const fmt = (d: string) => format(new Date(d), "dd/MM/yyyy HH:mm:ss", { locale: ptBR });

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="card p-4 flex gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Filtrar por ação..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input-field pl-9"
          />
        </div>
        <select
          value={selectedEntity}
          onChange={e => setSelectedEntity(e.target.value)}
          className="input-field w-48"
        >
          <option value="">Todos os tipos</option>
          <option value="auth">Autenticação</option>
          <option value="sei_process">Processo SEI</option>
          <option value="artifact">Artefato</option>
          <option value="document">Documento</option>
          <option value="sei_config">Config SEI</option>
          <option value="user">Usuário</option>
        </select>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <span className="w-8 h-8 border-2 border-gov-blue border-t-transparent rounded-full animate-spin" />
        </div>
      ) : logs?.length ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left">
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Data/Hora</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Usuário</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Ação</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Tipo</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Entidade</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">IP</th>
                  <th className="px-4 py-3 text-xs font-semibold text-gray-600 uppercase">Detalhes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {logs.map(log => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{fmt(log.created_at)}</td>
                    <td className="px-4 py-3">
                      <p className="text-xs font-medium text-gray-900">{log.user_name || '—'}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                        ACTION_COLORS[log.action] || 'bg-gray-100 text-gray-600'
                      }`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">{log.entity_type || '—'}</td>
                    <td className="px-4 py-3 text-xs font-mono text-gray-400 max-w-[100px] truncate">
                      {log.entity_id ? log.entity_id.substring(0, 8) + '...' : '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">{log.ip_address || '—'}</td>
                    <td className="px-4 py-3">
                      {log.metadata_json && (
                        <details className="cursor-pointer">
                          <summary className="text-xs text-primary-600 hover:underline">ver</summary>
                          <pre className="text-xs bg-gray-50 rounded p-2 mt-1 max-w-xs overflow-auto">
                            {JSON.stringify(log.metadata_json, null, 2)}
                          </pre>
                        </details>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-3 bg-gray-50 border-t border-gray-100">
            <p className="text-xs text-gray-500">{logs.length} registro(s) encontrado(s)</p>
          </div>
        </div>
      ) : (
        <div className="card text-center py-12">
          <ClipboardList className="w-10 h-10 mx-auto mb-2 text-gray-300" />
          <p className="text-gray-400 text-sm">Nenhum registro de auditoria encontrado</p>
        </div>
      )}
    </div>
  );
}
