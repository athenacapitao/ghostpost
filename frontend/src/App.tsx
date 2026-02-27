import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthContext, useAuth, useAuthProvider } from './hooks/useAuth';
import Layout from './components/Layout';
import Login from './pages/Login';
import ThreadList from './pages/ThreadList';
import ThreadDetail from './pages/ThreadDetail';
import Stats from './pages/Stats';
import Compose from './pages/Compose';
import Drafts from './pages/Drafts';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import Playbooks from './pages/Playbooks';
import Research from './pages/Research';
import ResearchNew from './pages/ResearchNew';
import ResearchDetail from './pages/ResearchDetail';
import ResearchBatchNew from './pages/ResearchBatchNew';
import ResearchBatchDetail from './pages/ResearchBatchDetail';
import AgentSkills from './pages/AgentSkills';
import Identities from './pages/Identities';
import ResearchImport from './pages/ResearchImport';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { username, loading } = useAuth();
  if (loading) return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-500">Loading...</div>;
  if (!username) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  const { username, loading } = useAuth();

  if (loading) {
    return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-500">Loading...</div>;
  }

  return (
    <Routes>
      <Route path="/login" element={username ? <Navigate to="/" replace /> : <Login />} />
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/threads" element={<ThreadList />} />
        <Route path="/threads/:id" element={<ThreadDetail />} />
        <Route path="/stats" element={<Stats />} />
        <Route path="/compose" element={<Compose />} />
        <Route path="/drafts" element={<Drafts />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/playbooks" element={<Playbooks />} />
        <Route path="/research" element={<Research />} />
        <Route path="/research/new" element={<ResearchNew />} />
        <Route path="/research/import" element={<ResearchImport />} />
        <Route path="/research/batch/new" element={<ResearchBatchNew />} />
        <Route path="/research/batch/:id" element={<ResearchBatchDetail />} />
        <Route path="/research/:id" element={<ResearchDetail />} />
        <Route path="/identities" element={<Identities />} />
        <Route path="/skills" element={<AgentSkills />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  const auth = useAuthProvider();

  return (
    <AuthContext.Provider value={auth}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthContext.Provider>
  );
}
