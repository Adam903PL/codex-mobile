import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { AlertCircle, Check, Eye, EyeOff, GraduationCap, Home, Server, Terminal } from "lucide-react-native";
import { DEFAULT_LAN_API_BASE_URL, SCHOOL_LAN_API_BASE_URL, normalizeApiUrl, testApiConnection } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { usePreferences } from "../preferences/PreferencesContext";

const THEME = {
  bg: "#050505",
  panel: "#0d0d0d",
  inputBg: "#111111",
  inputBgFocus: "#151515",
  textPrimary: "#f4f4f5",
  textSecondary: "#a1a1aa",
  textMuted: "#71717a",
  placeholder: "#666666",
  border: "#27272a",
  borderFocus: "#52525b",
  accent: "#ffffff",
  dangerBg: "#2d1515",
  dangerBorder: "#7f1d1d",
  dangerText: "#fca5a5"
};

export function LoginScreen() {
  const { signIn } = useAuth();
  const { preferences, updatePreferences } = usePreferences();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [apiDraft, setApiDraft] = useState(preferences.apiUrl);
  const [apiStatus, setApiStatus] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [focusedField, setFocusedField] = useState<"username" | "password" | "api" | null>(null);
  const [error, setError] = useState("");
  const [isButtonHovered, setIsButtonHovered] = useState(false);
  const [isButtonFocused, setIsButtonFocused] = useState(false);

  const passwordRef = useRef<TextInput>(null);
  const entrance = useRef(new Animated.Value(0)).current;
  const errorEntrance = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(entrance, {
      toValue: 1,
      duration: 520,
      useNativeDriver: true
    }).start();
  }, [entrance]);

  useEffect(() => {
    setApiDraft(preferences.apiUrl);
  }, [preferences.apiUrl]);

  useEffect(() => {
    if (!error) {
      errorEntrance.setValue(0);
      return;
    }
    Animated.spring(errorEntrance, {
      toValue: 1,
      friction: 8,
      tension: 90,
      useNativeDriver: true
    }).start();
  }, [error, errorEntrance]);

  const handleLogin = async () => {
    if (!username || !password || isSubmitting) return;
    setError("");
    setIsSubmitting(true);
    try {
      await signIn(username.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie zalogowac.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const normalizeBackendDraft = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return normalizeApiUrl(DEFAULT_LAN_API_BASE_URL);
    if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(trimmed)) return normalizeApiUrl(`http://${trimmed}:8000`);
    if (/^[\w.-]+:\d+$/.test(trimmed)) return normalizeApiUrl(`http://${trimmed}`);
    return normalizeApiUrl(trimmed);
  };

  const saveBackend = async (value = apiDraft) => {
    const next = normalizeBackendDraft(value);
    setApiDraft(next);
    setApiStatus("Zapisywanie...");
    await updatePreferences({ apiUrl: next });
    setApiStatus("Zapisane globalnie.");
  };

  const testBackend = async () => {
    const next = normalizeBackendDraft(apiDraft);
    setApiDraft(next);
    setApiStatus("Test...");
    try {
      const result = await testApiConnection(next);
      setApiStatus(result.ok ? `Polaczono (${result.status})` : `HTTP ${result.status}`);
    } catch (err) {
      setApiStatus(err instanceof Error ? err.message : "Nie udalo sie polaczyc.");
    }
  };

  const canSubmit = Boolean(username.trim() && password && !isSubmitting);
  const translateY = entrance.interpolate({ inputRange: [0, 1], outputRange: [18, 0] });
  const scale = entrance.interpolate({ inputRange: [0, 1], outputRange: [0.98, 1] });

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : "height"}>
        <ScrollView contentContainerStyle={styles.scrollContent} keyboardDismissMode="interactive" keyboardShouldPersistTaps="handled">
          <Animated.View style={[styles.content, { opacity: entrance, transform: [{ translateY }, { scale }] }]}>
            <View style={styles.logoContainer}>
              <View style={styles.logoMark}>
                <Terminal color={THEME.accent} size={30} strokeWidth={1.8} />
              </View>
              <Text style={styles.brand}>DevLink</Text>
            </View>

            <Text style={styles.title}>Zaloguj sie do DevLink</Text>
            <Text style={styles.subtitle}>
              Steruj lokalnym Codexem z telefonu i wracaj od razu do swojego workspace'u.
            </Text>

            <View style={styles.form}>
              <View style={styles.backendPanel}>
                <View style={styles.backendHeader}>
                  <View style={styles.backendTitleRow}>
                    <Server size={16} color={THEME.textSecondary} />
                    <Text style={styles.backendTitle}>Backend</Text>
                  </View>
                  <View style={styles.presetRow}>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel="Ustaw domowy backend"
                      style={({ pressed }) => [styles.smallButton, pressed && styles.smallButtonPressed]}
                      onPress={() => saveBackend(DEFAULT_LAN_API_BASE_URL)}
                    >
                      <Home size={14} color={THEME.textPrimary} />
                      <Text style={styles.smallButtonText}>Home</Text>
                    </Pressable>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel="Ustaw szkolny backend"
                      style={({ pressed }) => [styles.smallButton, pressed && styles.smallButtonPressed]}
                      onPress={() => saveBackend(SCHOOL_LAN_API_BASE_URL)}
                    >
                      <GraduationCap size={14} color={THEME.textPrimary} />
                      <Text style={styles.smallButtonText}>School</Text>
                    </Pressable>
                  </View>
                </View>

                <View style={[styles.inputContainer, focusedField === "api" && styles.inputFocused]}>
                  <Text style={styles.label}>Globalny IP / URL</Text>
                  <TextInput
                    style={styles.input}
                    value={apiDraft}
                    onChangeText={(value) => {
                      setApiDraft(value);
                      setApiStatus("");
                    }}
                    placeholder="192.168.0.9 albo http://192.168.0.9:8000/api"
                    placeholderTextColor={THEME.placeholder}
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="url"
                    returnKeyType="done"
                    onFocus={() => setFocusedField("api")}
                    onBlur={() => setFocusedField(null)}
                    onSubmitEditing={() => saveBackend()}
                  />
                </View>

                <View style={styles.backendActions}>
                  <Pressable
                    accessibilityRole="button"
                    style={({ pressed }) => [styles.secondaryButton, pressed && styles.secondaryButtonPressed]}
                    onPress={testBackend}
                  >
                    <Text style={styles.secondaryButtonText}>Test</Text>
                  </Pressable>
                  <Pressable
                    accessibilityRole="button"
                    style={({ pressed }) => [styles.secondaryButton, styles.saveButton, pressed && styles.secondaryButtonPressed]}
                    onPress={() => saveBackend()}
                  >
                    <Check size={14} color="#050505" />
                    <Text style={styles.saveButtonText}>Save</Text>
                  </Pressable>
                </View>
                {apiStatus ? <Text style={styles.backendStatus}>{apiStatus}</Text> : null}
              </View>

              <View style={[styles.inputContainer, focusedField === "username" && styles.inputFocused]}>
                <Text style={styles.label}>Login</Text>
                <TextInput
                  style={styles.input}
                  value={username}
                  onChangeText={setUsername}
                  placeholder="Np. devlink"
                  placeholderTextColor={THEME.placeholder}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="default"
                  returnKeyType="next"
                  onFocus={() => setFocusedField("username")}
                  onBlur={() => setFocusedField(null)}
                  onSubmitEditing={() => passwordRef.current?.focus()}
                />
              </View>

              <View style={[styles.inputContainer, focusedField === "password" && styles.inputFocused]}>
                <Text style={styles.label}>Haslo</Text>
                <View style={styles.passwordRow}>
                  <TextInput
                    ref={passwordRef}
                    style={styles.input}
                    value={password}
                    onChangeText={setPassword}
                    placeholder="Wpisz haslo"
                    placeholderTextColor={THEME.placeholder}
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    autoCorrect={false}
                    returnKeyType="send"
                    onFocus={() => setFocusedField("password")}
                    onBlur={() => setFocusedField(null)}
                    onSubmitEditing={handleLogin}
                  />
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={showPassword ? "Ukryj haslo" : "Pokaz haslo"}
                    hitSlop={10}
                    onPress={() => setShowPassword((value) => !value)}
                    style={({ pressed }) => [styles.iconButton, pressed && styles.iconButtonPressed]}
                  >
                    {showPassword ? (
                      <EyeOff size={20} color={THEME.textSecondary} />
                    ) : (
                      <Eye size={20} color={THEME.textSecondary} />
                    )}
                  </Pressable>
                </View>
              </View>

              {error ? (
                <Animated.View
                  style={[
                    styles.errorBanner,
                    {
                      opacity: errorEntrance,
                      transform: [
                        {
                          translateY: errorEntrance.interpolate({ inputRange: [0, 1], outputRange: [-6, 0] })
                        }
                      ]
                    }
                  ]}
                >
                  <AlertCircle size={16} color={THEME.dangerText} />
                  <Text style={styles.errorText}>{error}</Text>
                </Animated.View>
              ) : null}

              <Pressable
                style={({ pressed }) => [
                  styles.button,
                  isButtonHovered && styles.buttonHover,
                  isButtonFocused && styles.buttonFocus,
                  pressed && styles.buttonPressed,
                  !canSubmit && styles.buttonDisabled
                ]}
                onPress={handleLogin}
                onHoverIn={() => setIsButtonHovered(true)}
                onHoverOut={() => setIsButtonHovered(false)}
                onFocus={() => setIsButtonFocused(true)}
                onBlur={() => setIsButtonFocused(false)}
                disabled={!canSubmit}
              >
                {isSubmitting ? <ActivityIndicator color="#050505" /> : <Text style={styles.buttonText}>Sign in</Text>}
              </Pressable>
            </View>

            <Text style={styles.footerText}>Backend: {preferences.apiUrl.replace(/\/api$/, "")}</Text>
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: THEME.bg
  },
  container: {
    flex: 1
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    paddingHorizontal: 22,
    paddingVertical: 34
  },
  content: {
    width: "100%",
    maxWidth: 430,
    alignSelf: "center"
  },
  logoContainer: {
    alignItems: "center",
    marginBottom: 30
  },
  logoMark: {
    width: 62,
    height: 62,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: THEME.panel,
    borderWidth: 1,
    borderColor: THEME.border,
    marginBottom: 14
  },
  brand: {
    color: THEME.textPrimary,
    fontSize: 15,
    fontWeight: "700",
    letterSpacing: 0
  },
  title: {
    color: THEME.textPrimary,
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "700",
    textAlign: "center",
    marginBottom: 10
  },
  subtitle: {
    color: THEME.textSecondary,
    fontSize: 15,
    lineHeight: 22,
    textAlign: "center",
    marginBottom: 28
  },
  form: {
    gap: 14
  },
  backendPanel: {
    borderWidth: 1,
    borderColor: THEME.border,
    borderRadius: 14,
    padding: 12,
    backgroundColor: THEME.panel,
    gap: 10
  },
  backendHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10
  },
  backendTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  backendTitle: {
    color: THEME.textPrimary,
    fontSize: 13,
    fontWeight: "700"
  },
  presetRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  smallButton: {
    minHeight: 32,
    borderRadius: 16,
    paddingHorizontal: 11,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#181818",
    borderWidth: 1,
    borderColor: THEME.border
  },
  smallButtonPressed: {
    backgroundColor: "#222222"
  },
  smallButtonText: {
    color: THEME.textPrimary,
    fontSize: 12,
    fontWeight: "700"
  },
  backendActions: {
    flexDirection: "row",
    gap: 10
  },
  secondaryButton: {
    minHeight: 40,
    flex: 1,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: THEME.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#141414",
    flexDirection: "row",
    gap: 7
  },
  secondaryButtonPressed: {
    opacity: 0.8,
    transform: [{ scale: 0.99 }]
  },
  secondaryButtonText: {
    color: THEME.textPrimary,
    fontSize: 13,
    fontWeight: "700"
  },
  saveButton: {
    backgroundColor: THEME.accent,
    borderColor: THEME.accent
  },
  saveButtonText: {
    color: "#050505",
    fontSize: 13,
    fontWeight: "800"
  },
  backendStatus: {
    color: THEME.textSecondary,
    fontSize: 12,
    lineHeight: 16
  },
  inputContainer: {
    borderWidth: 1,
    borderColor: THEME.border,
    borderRadius: 14,
    paddingHorizontal: 15,
    paddingVertical: 11,
    backgroundColor: THEME.inputBg
  },
  inputFocused: {
    borderColor: THEME.borderFocus,
    backgroundColor: THEME.inputBgFocus
  },
  label: {
    color: THEME.textSecondary,
    fontSize: 12,
    fontWeight: "600",
    marginBottom: 5
  },
  input: {
    flex: 1,
    color: THEME.textPrimary,
    fontSize: 16,
    paddingVertical: 3
  },
  passwordRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  iconButton: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: "center",
    justifyContent: "center"
  },
  iconButtonPressed: {
    backgroundColor: "#1f1f1f"
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 9,
    borderWidth: 1,
    borderColor: THEME.dangerBorder,
    backgroundColor: THEME.dangerBg,
    borderRadius: 12,
    paddingHorizontal: 13,
    paddingVertical: 11
  },
  errorText: {
    color: THEME.dangerText,
    flex: 1,
    fontSize: 13,
    lineHeight: 18
  },
  button: {
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: THEME.accent,
    borderWidth: 1,
    borderColor: THEME.accent,
    marginTop: 2
  },
  buttonHover: {
    backgroundColor: "#f4f4f5"
  },
  buttonFocus: {
    borderColor: "#a1a1aa"
  },
  buttonPressed: {
    transform: [{ scale: 0.985 }],
    opacity: 0.9
  },
  buttonDisabled: {
    opacity: 0.42
  },
  buttonText: {
    color: "#050505",
    fontSize: 16,
    fontWeight: "700"
  },
  footerText: {
    color: THEME.textMuted,
    fontSize: 12,
    textAlign: "center",
    marginTop: 28
  }
});
