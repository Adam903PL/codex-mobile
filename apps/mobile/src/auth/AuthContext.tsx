import * as SecureStore from "expo-secure-store";
import { createContext, PropsWithChildren, useContext, useEffect, useMemo, useState } from "react";
import { login } from "../api/client";

type AuthContextValue = {
  accessToken: string | null;
  isLoading: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    SecureStore.getItemAsync("devlink_access_token")
      .then(setAccessToken)
      .finally(() => setIsLoading(false));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      accessToken,
      isLoading,
      async signIn(username: string, password: string) {
        const tokens = await login(username, password);
        await SecureStore.setItemAsync("devlink_access_token", tokens.access);
        await SecureStore.setItemAsync("devlink_refresh_token", tokens.refresh);
        setAccessToken(tokens.access);
      },
      async signOut() {
        await SecureStore.deleteItemAsync("devlink_access_token");
        await SecureStore.deleteItemAsync("devlink_refresh_token");
        setAccessToken(null);
      }
    }),
    [accessToken, isLoading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}

