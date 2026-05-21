import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Building2, Eye, EyeOff, Lock, Mail } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { getErrorMessage } from '../lib/api';

interface FormData {
  email: string;
  password: string;
}

export default function Login() {
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuthStore();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>();

  const onSubmit = async (data: FormData) => {
    setError('');
    try {
      await login(data.email, data.password);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <div className="min-h-screen bg-gov-blue flex flex-col items-center justify-center p-4">
      {/* Top banner */}
      <div className="w-full max-w-md mb-6">
        <div className="flex items-center justify-center gap-3 mb-2">
          <Building2 className="w-10 h-10 text-gov-yellow" />
          <div className="text-center">
            <h1 className="text-white font-bold text-xl">IFPE</h1>
            <p className="text-primary-300 text-sm">Instituto Federal de Pernambuco</p>
          </div>
        </div>
      </div>

      {/* Card */}
      <div className="w-full max-w-md bg-white rounded-xl shadow-2xl overflow-hidden">
        <div className="bg-primary-800 px-6 py-5">
          <h2 className="text-white font-semibold text-lg">Integração Compras-SEI</h2>
          <p className="text-primary-300 text-sm mt-1">
            Sistema de importação de artefatos do Compras.gov.br para o SEI
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="px-6 py-6 space-y-5">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              E-mail institucional
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
              <input
                type="email"
                autoComplete="email"
                className="input-field pl-9"
                placeholder="usuario@ifpe.edu.br"
                {...register('email', {
                  required: 'E-mail é obrigatório',
                  pattern: { value: /\S+@\S+\.\S+/, message: 'E-mail inválido' },
                })}
              />
            </div>
            {errors.email && (
              <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Senha</label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
              <input
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                className="input-field pl-9 pr-9"
                placeholder="••••••••"
                {...register('password', { required: 'Senha é obrigatória' })}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {errors.password && (
              <p className="text-red-500 text-xs mt-1">{errors.password.message}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Lock className="w-4 h-4" />
            )}
            {isSubmitting ? 'Autenticando...' : 'Entrar'}
          </button>
        </form>

        <div className="px-6 pb-5">
          <p className="text-xs text-gray-400 text-center">
            Acesso restrito a servidores do IFPE. Todas as operações são registradas em auditoria.
          </p>
        </div>
      </div>

      <p className="text-primary-400 text-xs mt-6">
        © 2024 IFPE — Pró-Reitoria de Administração
      </p>
    </div>
  );
}
