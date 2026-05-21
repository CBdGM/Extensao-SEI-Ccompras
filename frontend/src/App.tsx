import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import MainLayout from './components/Layout/MainLayout';
import ProtectedRoute from './components/Layout/ProtectedRoute';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import SEIProcess from './pages/SEIProcess';
import ProcessDetail from './pages/ProcessDetail';
import ImportArtifact from './pages/ImportArtifact';
import Artifacts from './pages/Artifacts';
import Documents from './pages/Documents';
import AuditLogs from './pages/AuditLogs';
import SEIConfig from './pages/SEIConfig';
import NotFound from './pages/NotFound';

export default function App() {
  const { isAuthenticated } = useAuthStore();

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="processos" element={<SEIProcess />} />
          <Route path="processos/:id" element={<ProcessDetail />} />
          <Route path="processos/:id/importar" element={<ImportArtifact />} />
          <Route path="artefatos" element={<Artifacts />} />
          <Route path="documentos" element={<Documents />} />
          <Route path="auditoria" element={
            <ProtectedRoute adminOnly>
              <AuditLogs />
            </ProtectedRoute>
          } />
          <Route path="configuracoes" element={
            <ProtectedRoute adminOnly>
              <SEIConfig />
            </ProtectedRoute>
          } />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}
