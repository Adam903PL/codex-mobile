import * as SecureStore from "expo-secure-store";
import { createContext, PropsWithChildren, useContext, useEffect, useMemo, useState } from "react";
import { getDefaultApiUrl, LEGACY_LOCAL_API_URL, normalizeApiUrl, setApiUrlOverride } from "../api/client";

export type AppLanguage = "pl" | "en";
export type AppTheme = "dark" | "oled";
export type ChatDensity = "comfortable" | "compact";
export type AppSettingsSection = "account" | "devices" | "appearance" | "chat" | "safety" | "developer";

export type AppPreferences = {
  language: AppLanguage;
  theme: AppTheme;
  density: ChatDensity;
  runLogDefault: "expanded" | "collapsed";
  startBehavior: "last-chat" | "new-chat";
  autoRefreshCapabilities: boolean;
  apiUrl: string;
};

const STORAGE_KEY = "devlink_app_preferences_v1";

const defaultLanguage = (): AppLanguage => {
  return "pl";
};

export const DEFAULT_APP_PREFERENCES: AppPreferences = {
  language: defaultLanguage(),
  theme: "dark",
  density: "comfortable",
  runLogDefault: "collapsed",
  startBehavior: "last-chat",
  autoRefreshCapabilities: false,
  apiUrl: getDefaultApiUrl()
};

const STRINGS = {
  pl: {
    "common.close": "Zamknij",
    "common.refresh": "Odswiez",
    "common.save": "Zapisz",
    "common.enabled": "Wlaczone",
    "common.disabled": "Wylaczone",
    "chat.connectCli": "Connect CLI",
    "chat.addWorkspace": "Dodaj workspace",
    "chat.noCliBody": "Laptop nie jest polaczony z DevLink. Otworz ustawienia, wygeneruj kod i uruchom devlink connect.",
    "chat.noProjectBody": "CLI jest sparowane. Dodaj workspace z laptopa: devlink projects add --path <sciezka>.",
    "chat.prompt": "Message DevLink...",
    "chat.empty": "Jak moge pomoc?",
    "chat.selectModel": "Wybierz model",
    "drawer.newChat": "Nowy chat",
    "drawer.refreshWorkspaces": "Odswiez workspace",
    "drawer.settings": "Ustawienia",
    "drawer.logout": "Logout",
    "drawer.search": "Szukaj...",
    "settings.title": "App Settings",
    "settings.account": "Konto",
    "settings.devices": "Devices & CLI",
    "settings.appearance": "Wyglad",
    "settings.chat": "Chat",
    "settings.safety": "Safety",
    "settings.developer": "Developer",
    "settings.language": "Jezyk",
    "settings.theme": "Motyw",
    "settings.density": "Gestosc chatu",
    "settings.runLog": "Run log po zakonczeniu",
    "settings.startBehavior": "Start aplikacji",
    "settings.autoRefresh": "Auto-refresh capabilities",
    "settings.apiUrl": "API server URL",
    "settings.testApi": "Test connection",
    "settings.mobileLogout": "Logout from mobile",
    "settings.codexLogout": "Logout Codex on laptop",
    "pairing.title": "CLI pairing",
    "pairing.generate": "Generate pairing code",
    "pairing.expires": "Wazny jeszcze",
    "pairing.expired": "Kod wygasl. Wygeneruj nowy.",
    "pairing.instructions": "Na laptopie uruchom:",
    "pairing.hint": "Kod jest jednorazowy i wazny przez 10 minut.",
    "pairing.inventory": "Inventory",
    "pairing.noDevices": "Brak sparowanych komputerow.",
    "pairing.noProjects": "Brak projektow.",
    "safety.save": "Zapisz safety settings"
  },
  en: {
    "common.close": "Close",
    "common.refresh": "Refresh",
    "common.save": "Save",
    "common.enabled": "Enabled",
    "common.disabled": "Disabled",
    "chat.connectCli": "Connect CLI",
    "chat.addWorkspace": "Add workspace",
    "chat.noCliBody": "Your laptop is not connected to DevLink. Open settings, generate a code, then run devlink connect.",
    "chat.noProjectBody": "The CLI is paired. Add a workspace from the laptop with devlink projects add --path <path>.",
    "chat.prompt": "Message DevLink...",
    "chat.empty": "How can I help?",
    "chat.selectModel": "Select model",
    "drawer.newChat": "New chat",
    "drawer.refreshWorkspaces": "Refresh workspaces",
    "drawer.settings": "Settings",
    "drawer.logout": "Logout",
    "drawer.search": "Search...",
    "settings.title": "App Settings",
    "settings.account": "Account",
    "settings.devices": "Devices & CLI",
    "settings.appearance": "Appearance",
    "settings.chat": "Chat",
    "settings.safety": "Safety",
    "settings.developer": "Developer",
    "settings.language": "Language",
    "settings.theme": "Theme",
    "settings.density": "Chat density",
    "settings.runLog": "Run log after finish",
    "settings.startBehavior": "App start",
    "settings.autoRefresh": "Auto-refresh capabilities",
    "settings.apiUrl": "API server URL",
    "settings.testApi": "Test connection",
    "settings.mobileLogout": "Logout from mobile",
    "settings.codexLogout": "Logout Codex on laptop",
    "pairing.title": "CLI pairing",
    "pairing.generate": "Generate pairing code",
    "pairing.expires": "Valid for",
    "pairing.expired": "Code expired. Generate a new one.",
    "pairing.instructions": "Run on your laptop:",
    "pairing.hint": "The code is single-use and valid for 10 minutes.",
    "pairing.inventory": "Inventory",
    "pairing.noDevices": "No paired computers.",
    "pairing.noProjects": "No projects.",
    "safety.save": "Save safety settings"
  }
} as const;

export type TranslationKey = keyof typeof STRINGS.en;

type PreferencesContextValue = {
  preferences: AppPreferences;
  isLoading: boolean;
  updatePreferences: (patch: Partial<AppPreferences>) => Promise<void>;
  t: (key: TranslationKey) => string;
};

const PreferencesContext = createContext<PreferencesContextValue | undefined>(undefined);

function coercePreferences(value: unknown): AppPreferences {
  if (!value || typeof value !== "object") return DEFAULT_APP_PREFERENCES;
  const raw = value as Partial<AppPreferences>;
  const apiUrl = raw.apiUrl && raw.apiUrl !== LEGACY_LOCAL_API_URL ? normalizeApiUrl(raw.apiUrl) : DEFAULT_APP_PREFERENCES.apiUrl;
  return {
    ...DEFAULT_APP_PREFERENCES,
    ...raw,
    language: raw.language === "en" ? "en" : "pl",
    theme: raw.theme === "oled" ? "oled" : "dark",
    density: raw.density === "compact" ? "compact" : "comfortable",
    runLogDefault: raw.runLogDefault === "expanded" ? "expanded" : "collapsed",
    startBehavior: raw.startBehavior === "new-chat" ? "new-chat" : "last-chat",
    autoRefreshCapabilities: Boolean(raw.autoRefreshCapabilities),
    apiUrl
  };
}

export function PreferencesProvider({ children }: PropsWithChildren) {
  const [preferences, setPreferences] = useState<AppPreferences>(DEFAULT_APP_PREFERENCES);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    SecureStore.getItemAsync(STORAGE_KEY)
      .then((stored) => {
        const parsed = stored ? JSON.parse(stored) : null;
        const next = coercePreferences(parsed);
        setPreferences(next);
        setApiUrlOverride(next.apiUrl);
      })
      .catch(() => {
        setApiUrlOverride(DEFAULT_APP_PREFERENCES.apiUrl);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const value = useMemo<PreferencesContextValue>(
    () => ({
      preferences,
      isLoading,
      async updatePreferences(patch) {
        const next = coercePreferences({ ...preferences, ...patch });
        setPreferences(next);
        setApiUrlOverride(next.apiUrl);
        await SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(next));
      },
      t(key) {
        return STRINGS[preferences.language][key] || STRINGS.en[key] || key;
      }
    }),
    [isLoading, preferences]
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context) {
    throw new Error("usePreferences must be used inside PreferencesProvider");
  }
  return context;
}
