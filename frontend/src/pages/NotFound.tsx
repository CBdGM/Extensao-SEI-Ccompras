import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-gov-blue flex items-center justify-center">
      <div className="text-center">
        <p className="text-6xl font-bold text-primary-400">404</p>
        <p className="text-white text-xl mt-2">Página não encontrada</p>
        <Link to="/" className="inline-block mt-4 btn-secondary text-sm">
          Voltar ao início
        </Link>
      </div>
    </div>
  );
}
