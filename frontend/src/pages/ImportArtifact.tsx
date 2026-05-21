import { useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft, Upload, FileText, AlertCircle, CheckCircle, Shield, Info
} from 'lucide-react';
import { api, getErrorMessage, formatFileSize } from '../lib/api';
import type { SEIProcess, ArtifactType, AccessLevel } from '../types';

interface FormData {
  tipo_artefato: ArtifactType;
  identificador_compras: string;
  nivel_acesso: AccessLevel;
  observacao?: string;
}

const ARTIFACT_TYPES: { value: ArtifactType; label: string }[] = [
  { value: 'DFD', label: 'Documento de Formalização de Demanda (DFD)' },
  { value: 'ETP', label: 'Estudo Técnico Preliminar (ETP)' },
  { value: 'TR', label: 'Termo de Referência' },
  { value: 'MATRIZ_RISCOS', label: 'Matriz de Riscos' },
];

const ACCESS_LEVELS: { value: AccessLevel; label: string; desc: string }[] = [
  { value: 'publico', label: 'Público', desc: 'Visível a todos' },
  { value: 'restrito', label: 'Restrito', desc: 'Apenas usuários autorizados' },
  { value: 'sigiloso', label: 'Sigiloso', desc: 'Acesso controlado' },
];

export default function ImportArtifact() {
  const { id } = useParams<{ id: string }>();
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: process } = useQuery({
    queryKey: ['process', id],
    queryFn: () => api.get<SEIProcess>(`/sei-processes/${id}`).then(r => r.data),
    enabled: !!id,
  });

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormData>({
    defaultValues: { nivel_acesso: 'publico', tipo_artefato: 'DFD' },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError('');
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      setFileError('Apenas arquivos PDF são aceitos');
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setFileError('Arquivo excede 20MB');
      return;
    }
    setFile(f);
  };

  const onSubmit = async (data: FormData) => {
    if (!file) { setFileError('Selecione um arquivo PDF'); return; }
    setSubmitError('');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('sei_process_id', id!);
    formData.append('tipo_artefato', data.tipo_artefato);
    formData.append('identificador_compras', data.identificador_compras);
    formData.append('nivel_acesso', data.nivel_acesso);
    if (data.observacao) formData.append('observacao', data.observacao);

    try {
      await api.post('/artifacts/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSuccess(true);
      reset();
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setSubmitError(getErrorMessage(err));
    }
  };

  if (success) {
    return (
      <div className="max-w-xl mx-auto">
        <div className="card p-8 text-center">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Artefato importado com sucesso!</h2>
          <p className="text-gray-500 text-sm mb-6">
            O arquivo foi validado, o hash SHA-256 foi calculado e os metadados foram registrados.
          </p>
          <div className="flex gap-3 justify-center">
            <button onClick={() => setSuccess(false)} className="btn-secondary">
              Importar outro artefato
            </button>
            <Link to={`/processos/${id}`} className="btn-primary">
              Ver processo
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <Link to={`/processos/${id}`} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Importar Artefato</h2>
          {process && (
            <p className="text-sm text-gray-500 font-mono">{process.numero_processo}</p>
          )}
        </div>
      </div>

      {/* Info banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex gap-3">
        <Info className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
        <p className="text-sm text-blue-800">
          Os artefatos importados terão seu hash SHA-256 e MD5 calculados automaticamente para garantia de integridade.
          Apenas arquivos PDF são aceitos. Tamanho máximo: 20MB.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="card p-6 space-y-5">
        {/* File upload */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Arquivo PDF <span className="text-red-500">*</span>
          </label>
          <div
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              fileError ? 'border-red-300 bg-red-50' :
              file ? 'border-green-300 bg-green-50' :
              'border-gray-300 hover:border-primary-400 hover:bg-blue-50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleFileChange}
              className="hidden"
            />
            {file ? (
              <div className="flex items-center justify-center gap-2 text-green-700">
                <FileText className="w-5 h-5" />
                <div className="text-left">
                  <p className="text-sm font-medium">{file.name}</p>
                  <p className="text-xs">{formatFileSize(file.size)}</p>
                </div>
              </div>
            ) : (
              <div className="text-gray-500">
                <Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                <p className="text-sm">Clique para selecionar um arquivo PDF</p>
                <p className="text-xs mt-1">Máximo 20MB</p>
              </div>
            )}
          </div>
          {fileError && <p className="text-red-500 text-xs mt-1">{fileError}</p>}
        </div>

        {/* Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Tipo de Artefato <span className="text-red-500">*</span>
          </label>
          <select className="input-field" {...register('tipo_artefato', { required: true })}>
            {ARTIFACT_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        {/* Identifier */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Identificador no Compras.gov.br <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            className="input-field"
            placeholder="Ex: 12345678-DFD-2024"
            {...register('identificador_compras', { required: 'Identificador é obrigatório' })}
          />
          {errors.identificador_compras && (
            <p className="text-red-500 text-xs mt-1">{errors.identificador_compras.message}</p>
          )}
        </div>

        {/* Access level */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Nível de Acesso <span className="text-red-500">*</span>
          </label>
          <div className="grid grid-cols-3 gap-3">
            {ACCESS_LEVELS.map(({ value, label, desc }) => (
              <label key={value} className="cursor-pointer">
                <input
                  type="radio"
                  value={value}
                  {...register('nivel_acesso', { required: true })}
                  className="sr-only"
                />
                <div className={`border-2 rounded-lg p-3 text-center transition-all ${
                  value === 'publico' ? 'peer-checked:border-green-500' :
                  value === 'restrito' ? 'peer-checked:border-yellow-500' :
                  'peer-checked:border-red-500'
                } hover:border-primary-400`}>
                  <Shield className={`w-4 h-4 mx-auto mb-1 ${
                    value === 'publico' ? 'text-green-600' :
                    value === 'restrito' ? 'text-yellow-600' : 'text-red-600'
                  }`} />
                  <p className="text-xs font-semibold">{label}</p>
                  <p className="text-xs text-gray-500">{desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Observation */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Observação (opcional)
          </label>
          <textarea
            rows={3}
            className="input-field resize-none"
            placeholder="Informações adicionais sobre este artefato..."
            {...register('observacao')}
          />
        </div>

        {submitError && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            {submitError}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Link to={`/processos/${id}`} className="btn-secondary">Cancelar</Link>
          <button type="submit" disabled={isSubmitting} className="btn-primary flex items-center gap-2">
            {isSubmitting ? (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Upload className="w-4 h-4" />
            )}
            {isSubmitting ? 'Importando...' : 'Importar Artefato'}
          </button>
        </div>
      </form>
    </div>
  );
}
