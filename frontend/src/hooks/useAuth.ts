import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { api } from '../api/client';

interface AuthState {
  username: string | null;
  token: string | null;
  loading: boolean;
}

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType>({
  username: null,
  token: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function useAuthProvider(): AuthContextType {
  const [state, setState] = useState<AuthState>({
    username: null,
    token: localStorage.getItem('ghostpost_token'),
    loading: true,
  });

  // Check auth on mount
  useEffect(() => {
    const token = localStorage.getItem('ghostpost_token');
    if (!token) {
      setState({ username: null, token: null, loading: false });
      return;
    }
    api.get<{ username: string }>('/auth/me')
      .then(data => setState({ username: data.username, token, loading: false }))
      .catch(() => {
        localStorage.removeItem('ghostpost_token');
        setState({ username: null, token: null, loading: false });
      });
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await api.post<{ token: string; message: string }>('/auth/login', {
      username,
      password,
    });
    localStorage.setItem('ghostpost_token', data.token);
    setState({ username, token: data.token, loading: false });
  }, []);

  const logout = useCallback(async () => {
    await api.post('/auth/logout').catch(() => {});
    localStorage.removeItem('ghostpost_token');
    setState({ username: null, token: null, loading: false });
  }, []);

  return { ...state, login, logout };
}
