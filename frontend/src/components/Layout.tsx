import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const navItems = [
  { path: '/', label: 'Dashboard' },
  { path: '/threads', label: 'Threads' },
  { path: '/compose', label: 'Compose' },
  { path: '/drafts', label: 'Drafts' },
  { path: '/research', label: 'Research' },
  { path: '/identities', label: 'Identities' },
  { path: '/settings', label: 'Settings' },
  { path: '/playbooks', label: 'Playbooks' },
  { path: '/skills', label: 'Skills' },
];

export default function Layout() {
  const { username, logout } = useAuth();
  const location = useLocation();

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link to="/" className="text-lg font-bold tracking-tight">
              GhostPost
            </Link>
            <nav className="hidden sm:flex gap-1">
              {navItems.map(item => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                    (item.path === '/' ? location.pathname === '/' : location.pathname.startsWith(item.path))
                      ? 'bg-gray-800 text-white'
                      : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-400">{username}</span>
            <button
              onClick={logout}
              className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
