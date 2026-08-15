import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "../lib/api";

type AuthContextValue = {
  username: string | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setReady(true);
      return;
    }
    api<{ username: string }>("/api/v1/auth/me")
      .then((user) => setUsername(user.username))
      .catch(() => setToken(null))
      .finally(() => setReady(true));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      username,
      ready,
      async login(nextUser, password) {
        const result = await api<{ access_token: string; username: string }>("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ username: nextUser, password }),
        });
        setToken(result.access_token);
        setUsername(result.username);
      },
      logout() {
        setToken(null);
        setUsername(null);
      },
    }),
    [username, ready],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("AuthProvider missing");
  return ctx;
}
