import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, CheckCircle, AlertCircle, Eye, EyeOff, Info } from 'lucide-react';
import { api, getErrorMessage } from '../lib/api';
import type { SEIConfig } from '../types';

interface FormData {
  soap_url: string;
  sigla_sistema: string;
  identificacao_servico: string;
  id_unidade_default: string;
  sin_retornar_assuntos: boolean;
  sin_retornar_interessados: boolean;
  sin_retornar_observacoes: boolean;
  sin_retornar_ultimo_andamento: boolean;
  sin_retornar_unidades: boolean;
}

export default function SEIConfig() {
  const [showKey, setShowKey] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const queryClient = useQueryClient();

  const { data: config, isLoading } = useQuery({
    queryKey: ['sei-config'],
    queryFn: () => api.get<SEIConfig | null>('/sei-config/').then(r => r.data),
  });

  const { data: status } = useQuery({
    queryKey: ['sei-status'],
    queryFn: () => api.get('/sei-config/status').then(r => r.data),
  });

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormData>({
    defaultValues: {
      soap_url: 'https://sei-testes.ifpe.edu.br/sei/ws/SeiWS.php',
      sigla_sistema: 'MVP',
      id_unidade_default: '110001189',
      sin_retornar_assuntos: true,
      sin_retornar_interessados: true,
      sin_retornar_observacoes: true,
      sin_retornar_ultimo_andamento: true,
      sin_retornar_unidades: true,
    },
  });

  useEffect(() => {
    if (config) {
      reset({
        soap_url: config.soap_url,
        sigla_sistema: config.sigla_sistema,
        identificacao_servico: '',  // Never pre-fill key
        id_unidade_default: config.id_unidade_default,
        sin_retornar_assuntos: config.sin_retornar_assuntos,
        sin_retornar_interessados: config.sin_retornar_interessados,
        sin_retornar_observacoes: config.sin_retornar_observacoes,
        sin_retornar_ultimo_andamento: config.sin_retornar_ultimo_andamento,
        sin_retornar_unidades: config.sin_retornar_unidades,
      });
    }
  }, [config, reset]);

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      config
        ? api.put('/sei-config/', data).then(r => r.data)
        : api.post('/sei-config/', data).then(r => r.data),
    onSuccess: () => {
      setSuccess('Configuração salva com sucesso!');
      setError('');
      queryClient.invalidateQueries({ queryKey: ['sei-config', 'sei-status'] });
    },
    onError: (err) => {
      setError(getErrorMessage(err));
      setSuccess('');
    },
  });

  return (
    <div className="max-w-2xl space-y-6">
      {/* Status card */}
      <div className={`rounded-lg p-4 flex items-center gap-3 ${
        status?.configured ? 'bg-green-50 border border-green-200' : 'bg-amber-50 border border-amber-200'
      }`}>
        {status?.configured ? (
          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
        ) : (
          <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0" />
        )}
        <div className="text-sm">
          <p className={`font-medium ${status?.configured ? 'text-green-800' : 'text-amber-800'}`}>
            {status?.configured ? 'SEI configurado' : 'SEI não configurado'}
          </p>
          {status?.configured && (
            <p className="text-green-600 text-xs mt-0.5">
              Fonte: {status.source === 'database' ? 'Banco de dados' : 'Variáveis de ambiente'} · {status.soap_url}
            </p>
          )}
        </div>
      </div>

      {/* Security notice */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex gap-3">
        <Info className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
        <div className="text-sm text-blue-800">
          <p className="font-medium mb-1">Segurança das credenciais</p>
          <p>
            A chave de acesso (IdentificacaoServico) é criptografada com Fernet antes de ser armazenada.
            Ela <strong>nunca</strong> é retornada nas respostas da API nem registrada em logs.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit((d) => mutation.mutate(d))} className="card p-6 space-y-5">
        <h3 className="section-title">Configuração do Web Service SOAP</h3>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            URL SOAP <span className="text-red-500">*</span>
          </label>
          <input
            type="url"
            className="input-field font-mono text-sm"
            placeholder="https://sei-testes.ifpe.edu.br/sei/ws/SeiWS.php"
            {...register('soap_url', { required: 'URL é obrigatória' })}
          />
          {errors.soap_url && <p className="text-red-500 text-xs mt-1">{errors.soap_url.message}</p>}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              SiglaSistema <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              className="input-field"
              placeholder="MVP"
              {...register('sigla_sistema', { required: 'Sigla é obrigatória' })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              IdUnidade padrão <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              className="input-field"
              placeholder="110001189"
              {...register('id_unidade_default', { required: 'IdUnidade é obrigatória' })}
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            IdentificacaoServico (Chave de Acesso)
            {config ? <span className="text-gray-400 font-normal"> — deixe em branco para manter a atual</span> : <span className="text-red-500"> *</span>}
          </label>
          <div className="relative">
            <input
              type={showKey ? 'text' : 'password'}
              className="input-field pr-9"
              placeholder={config ? '••••••••••• (mantida)' : 'Chave de acesso ao SEI'}
              {...register('identificacao_servico', {
                required: !config ? 'Chave de acesso é obrigatória' : false,
              })}
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600"
            >
              {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {errors.identificacao_servico && (
            <p className="text-red-500 text-xs mt-1">{errors.identificacao_servico.message}</p>
          )}
        </div>

        {/* Flags */}
        <div>
          <p className="text-sm font-medium text-gray-700 mb-3">Flags de Retorno</p>
          <div className="space-y-2">
            {[
              { name: 'sin_retornar_assuntos', label: 'SinRetornarAssuntos' },
              { name: 'sin_retornar_interessados', label: 'SinRetornarInteressados' },
              { name: 'sin_retornar_observacoes', label: 'SinRetornarObservacoes' },
              { name: 'sin_retornar_ultimo_andamento', label: 'SinRetornarUltimoAndamento' },
              { name: 'sin_retornar_unidades', label: 'SinRetornarUnidadesProcedimentoAberto' },
            ].map(({ name, label }) => (
              <label key={name} className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  className="rounded text-gov-blue"
                  {...register(name as keyof FormData)}
                />
                <span className="text-sm font-mono text-gray-700">{label}</span>
              </label>
            ))}
          </div>
        </div>

        {success && (
          <div className="flex items-center gap-2 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md text-sm">
            <CheckCircle className="w-4 h-4" />
            {success}
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}

        <div className="flex justify-end pt-2">
          <button type="submit" disabled={isSubmitting || isLoading} className="btn-primary flex items-center gap-2">
            {isSubmitting ? (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {isSubmitting ? 'Salvando...' : 'Salvar Configuração'}
          </button>
        </div>
      </form>

      {/* Write operations note */}
      <div className="card p-5">
        <h3 className="section-title mb-3">Operações de Escrita no SEI</h3>
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            As operações <code className="bg-gray-100 px-1 rounded text-xs">adicionarArquivo</code> e{' '}
            <code className="bg-gray-100 px-1 rounded text-xs">incluirDocumento</code> estão em modo
            <strong> simulado</strong> por padrão.
          </p>
          <p>
            Para habilitá-las, configure <code className="bg-gray-100 px-1 rounded text-xs">SEI_ENABLE_WRITE_OPERATIONS=true</code> no arquivo <code>.env</code> do backend.
          </p>
          <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium ${
            false ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
          }`}>
            <span className={`w-2 h-2 rounded-full ${false ? 'bg-green-500' : 'bg-gray-400'}`} />
            Escrita no SEI: Desabilitada (simulação ativa)
          </div>
        </div>
      </div>
    </div>
  );
}
