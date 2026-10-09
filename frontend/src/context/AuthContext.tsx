import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { User } from '../types/api';
import { authApi, ApiClientError } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<User>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('access_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = localStorage.getItem('access_token');
      if (!storedToken) {
        setIsLoading(false);
        return;
      }

      try {
        const userData = await authApi.me();
        setUser(userData);
        setToken(storedToken);
      } catch (err) {
        console.warn('Session expired or invalid token:', err);
        localStorage.removeItem('access_token');
        setUser(null);
        setToken(null);
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();
  }, []);

  const login = async (username: string, password: string): Promise<User> => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await authApi.login({ username, password });
      localStorage.setItem('access_token', response.access_token);
      setToken(response.access_token);
      setUser(response.user);
      return response.user;
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Invalid username or password.');
      } else {
        setError('Unable to connect to clinical server. Please try again.');
      }
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    authApi.logout().catch(() => {});
    localStorage.removeItem('access_token');
    setUser(null);
    setToken(null);
    setError(null);
  };

  const clearError = () => setError(null);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        error,
        login,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
