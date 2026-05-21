import { useLocation } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';

const titles: Record<string, string> = {
  '/': 'Dashboard',
  '/processos': 'Consultar Processo SEI',
  '/artefatos': 'Artefatos Importados',
  '/documentos': 'Documentos de Comprovação',
  '/auditoria': 'Logs de Auditoria',
  '/configuracoes': 'Configuração da Integração SEI',
};

export default function Header() {
  const location = useLocation();
  const { user } = useAuthStore();

  const getTitle = () => {
    for (const [path, title] of Object.entries(titles)) {
      if (location.pathname === path || location.pathname.startsWith(path + '/')) {
        if (path !== '/') return title;
      }
    }
    return titles['/'];
  };

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      <div>
        <h1 className="text-lg font-semibold text-gray-900">{getTitle()}</h1>
        <p className="text-xs text-gray-500 mt-0.5">
          Integração Compras.gov.br — SEI | IFPE
        </p>
      </div>
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <Shield className="w-3.5 h-3.5 text-green-500" />
        <span>
          {user?.role === 'admin' ? 'Administrador' : 'Usuário'} • Conexão segura
        </span>
      </div>
    </header>
  );
}
