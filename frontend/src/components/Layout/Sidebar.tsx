import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Search, FileText, Upload, ClipboardList,
  Settings, LogOut, Building2,
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import clsx from 'clsx';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', exact: true },
  { to: '/processos', icon: Search, label: 'Consultar Processo' },
  { to: '/artefatos', icon: Upload, label: 'Artefatos' },
  { to: '/documentos', icon: FileText, label: 'Documentos' },
];

const adminItems = [
  { to: '/auditoria', icon: ClipboardList, label: 'Auditoria' },
  { to: '/configuracoes', icon: Settings, label: 'Configuração SEI' },
];

export default function Sidebar() {
  const { user, logout } = useAuthStore();

  return (
    <aside className="w-64 bg-gov-blue flex flex-col shadow-xl">
      {/* Logo */}
      <div className="p-5 border-b border-primary-700">
        <div className="flex items-center gap-2">
          <Building2 className="text-gov-yellow w-7 h-7 flex-shrink-0" />
          <div>
            <p className="text-white font-bold text-sm leading-tight">IFPE</p>
            <p className="text-primary-300 text-xs leading-tight">Compras-SEI</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map(({ to, icon: Icon, label, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-700 text-white'
                  : 'text-primary-200 hover:bg-primary-700 hover:text-white'
              )
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}

        {user?.role === 'admin' && (
          <>
            <div className="pt-4 pb-1">
              <p className="px-3 text-xs font-semibold text-primary-400 uppercase tracking-wider">
                Administração
              </p>
            </div>
            {adminItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary-700 text-white'
                      : 'text-primary-200 hover:bg-primary-700 hover:text-white'
                  )
                }
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                {label}
              </NavLink>
            ))}
          </>
        )}
      </nav>

      {/* User footer */}
      <div className="p-4 border-t border-primary-700">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-primary-700 flex items-center justify-center flex-shrink-0">
            <span className="text-white text-sm font-bold">
              {user?.name?.charAt(0).toUpperCase()}
            </span>
          </div>
          <div className="overflow-hidden">
            <p className="text-white text-xs font-medium truncate">{user?.name}</p>
            <p className="text-primary-300 text-xs truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-2 w-full px-3 py-2 text-primary-200 hover:text-white
                     hover:bg-primary-700 rounded-md text-sm transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sair
        </button>
      </div>
    </aside>
  );
}
