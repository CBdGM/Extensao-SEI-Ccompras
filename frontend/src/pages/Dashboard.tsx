import { useQuery } from '@tanstack/react-query';
import { Search, Upload, FileText, ClipboardList, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuthStore } from '../store/authStore';
import type { SEIProcessListItem, Artifact, DocumentListItem } from '../types';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

function StatCard({ title, value, icon: Icon, color }: {
  title: string; value: number | string; icon: React.ElementType; color: string;
}) {
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${color}`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{title}</p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuthStore();

  const { data: processes } = useQuery({
    queryKey: ['processes-list'],
    queryFn: () => api.get<SEIProcessListItem[]>('/sei-processes/?limit=5').then(r => r.data),
  });

  const { data: artifacts } = useQuery({
    queryKey: ['artifacts-list'],
    queryFn: () => api.get<Artifact[]>('/artifacts/?limit=5').then(r => r.data),
  });

  const { data: documents } = useQuery({
    queryKey: ['documents-list'],
    queryFn: () => api.get<DocumentListItem[]>('/documents/?limit=5').then(r => r.data),
  });

  const formatDate = (d: string) =>
    format(new Date(d), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR });

  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div className="bg-gov-blue text-white rounded-xl p-6">
        <h2 className="text-xl font-semibold">Bem-vindo(a), {user?.name?.split(' ')[0]}</h2>
        <p className="text-primary-200 text-sm mt-1">
          Integração Compras.gov.br → SEI | MVP v1.0
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="Processos consultados" value={processes?.length ?? 0} icon={Search} color="bg-gov-blue" />
        <StatCard title="Artefatos importados" value={artifacts?.length ?? 0} icon={Upload} color="bg-gov-green" />
        <StatCard title="Documentos gerados" value={documents?.length ?? 0} icon={FileText} color="bg-purple-600" />
      </div>

      {/* Main workflow */}
      <div className="card p-6">
        <h3 className="section-title mb-5">Fluxo Principal</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            { step: '1', title: 'Consultar Processo', desc: 'Informe o número do processo SEI', to: '/processos', icon: Search },
            { step: '2', title: 'Importar Artefatos', desc: 'Faça upload dos arquivos do Compras', to: '/artefatos', icon: Upload },
            { step: '3', title: 'Gerar Documento', desc: 'Crie o documento de comprovação', to: '/documentos', icon: FileText },
            { step: '4', title: 'Auditoria', desc: 'Rastreie todas as operações', to: '/auditoria', icon: ClipboardList },
          ].map(({ step, title, desc, to, icon: Icon }) => (
            <Link key={step} to={to} className="flex flex-col items-center p-4 rounded-lg border border-gray-200 hover:border-primary-500 hover:bg-blue-50 transition-colors group text-center">
              <div className="w-10 h-10 rounded-full bg-gov-blue text-white flex items-center justify-center text-sm font-bold mb-2">
                {step}
              </div>
              <Icon className="w-5 h-5 text-gov-blue mb-1" />
              <p className="text-sm font-medium text-gray-900">{title}</p>
              <p className="text-xs text-gray-500 mt-1">{desc}</p>
            </Link>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent processes */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="section-title">Processos Recentes</h3>
            <Link to="/processos" className="text-xs text-primary-600 hover:underline flex items-center gap-1">
              Ver todos <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {processes?.length ? (
            <div className="space-y-3">
              {processes.map(p => (
                <Link key={p.id} to={`/processos/${p.id}`}
                  className="flex items-start justify-between p-3 rounded-md hover:bg-gray-50 border border-gray-100 transition-colors">
                  <div>
                    <p className="text-sm font-medium text-gray-900 font-mono">{p.numero_processo}</p>
                    <p className="text-xs text-gray-500 mt-0.5 truncate max-w-[200px]">
                      {p.especificacao || p.tipo_procedimento_nome || '—'}
                    </p>
                  </div>
                  <span className="text-xs text-gray-400">{formatDate(p.created_at)}</span>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400 text-center py-6">
              Nenhum processo consultado ainda.{' '}
              <Link to="/processos" className="text-primary-600 hover:underline">Consultar agora</Link>
            </p>
          )}
        </div>

        {/* Recent artifacts */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="section-title">Artefatos Recentes</h3>
            <Link to="/artefatos" className="text-xs text-primary-600 hover:underline flex items-center gap-1">
              Ver todos <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {artifacts?.length ? (
            <div className="space-y-3">
              {artifacts.map(a => (
                <div key={a.id} className="flex items-center justify-between p-3 rounded-md border border-gray-100">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{a.original_filename}</p>
                    <p className="text-xs text-gray-500">{a.tipo_artefato} · {a.identificador_compras}</p>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                    a.nivel_acesso === 'publico' ? 'bg-green-100 text-green-800' :
                    a.nivel_acesso === 'restrito' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {a.nivel_acesso}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400 text-center py-6">
              Nenhum artefato importado ainda.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
