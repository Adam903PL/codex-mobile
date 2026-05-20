import { X, RotateCw, Skull, Send, Keyboard as KeyboardIcon, Trash2, ChevronRight } from "lucide-react-native";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  createTerminalSession,
  fetchTerminalEvents,
  killTerminal,
  Project,
  sendTerminalInput,
  TerminalEvent,
  TerminalSession,
  terminalWebSocketUrl
} from "../api/client";
import { T } from "../theme";

// ─── Types ────────────────────────────────────────────────────────────────────

type Props = {
  visible: boolean;
  token: string | null;
  project: Project | null;
  onClose: () => void;
  onNeedSetup: () => void;
};

type TerminalLine = {
  id: string;
  sequence: number;
  kind: TerminalEvent["kind"] | "local";
  text: string;
};

// ─── Constants ────────────────────────────────────────────────────────────────

const TERMINAL_DONE = new Set(["exited", "killed", "failed"]);
const MONO_FONT = Platform.OS === "ios" ? "Menlo" : "monospace";

// ─── ANSI stripping ───────────────────────────────────────────────────────────

// Strip ANSI escape sequences so they don't appear as raw escape codes
const ANSI_RE = /\x1b\[[0-9;]*[mGKJHF]|\x1b\][^\x07]*\x07|\x1b[=><NOPQRSTUV78cDEFHMZ]/g;
function stripAnsi(text: string): string {
  return text.replace(ANSI_RE, "");
}

// ─── Command suggestion data ───────────────────────────────────────────────────

type Suggestion = { label: string; category: string };

const SUGGESTIONS: Suggestion[] = [
  // docker
  { label: "docker ps", category: "docker" },
  { label: "docker ps -a", category: "docker" },
  { label: "docker images", category: "docker" },
  { label: "docker compose up", category: "docker" },
  { label: "docker compose up -d", category: "docker" },
  { label: "docker compose down", category: "docker" },
  { label: "docker compose build", category: "docker" },
  { label: "docker compose logs -f", category: "docker" },
  { label: "docker compose restart", category: "docker" },
  { label: "docker logs -f", category: "docker" },
  { label: "docker exec -it", category: "docker" },
  { label: "docker build -t", category: "docker" },
  { label: "docker pull", category: "docker" },
  { label: "docker run -it --rm", category: "docker" },
  { label: "docker stop", category: "docker" },
  { label: "docker rm", category: "docker" },
  { label: "docker rmi", category: "docker" },
  { label: "docker system prune -f", category: "docker" },
  // git
  { label: "git status", category: "git" },
  { label: "git log --oneline", category: "git" },
  { label: "git diff", category: "git" },
  { label: "git add .", category: "git" },
  { label: "git commit -m", category: "git" },
  { label: "git push", category: "git" },
  { label: "git pull", category: "git" },
  { label: "git fetch --all", category: "git" },
  { label: "git checkout -b", category: "git" },
  { label: "git stash", category: "git" },
  { label: "git stash pop", category: "git" },
  { label: "git rebase", category: "git" },
  { label: "git reset --hard HEAD", category: "git" },
  { label: "git merge", category: "git" },
  // npm
  { label: "npm install", category: "npm" },
  { label: "npm run dev", category: "npm" },
  { label: "npm run build", category: "npm" },
  { label: "npm run start", category: "npm" },
  { label: "npm run test", category: "npm" },
  { label: "npm run lint", category: "npm" },
  { label: "npm run typecheck", category: "npm" },
  { label: "npm ci", category: "npm" },
  { label: "npm outdated", category: "npm" },
  { label: "npm audit fix", category: "npm" },
  // pnpm
  { label: "pnpm install", category: "pnpm" },
  { label: "pnpm dev", category: "pnpm" },
  { label: "pnpm build", category: "pnpm" },
  { label: "pnpm add", category: "pnpm" },
  { label: "pnpm remove", category: "pnpm" },
  // yarn
  { label: "yarn install", category: "yarn" },
  { label: "yarn dev", category: "yarn" },
  { label: "yarn build", category: "yarn" },
  { label: "yarn add", category: "yarn" },
  // node
  { label: "node index.js", category: "node" },
  { label: "node --inspect", category: "node" },
  { label: "npx ts-node", category: "node" },
  // python
  { label: "python -m venv .venv", category: "python" },
  { label: "python manage.py runserver", category: "python" },
  { label: "python manage.py migrate", category: "python" },
  { label: "python manage.py makemigrations", category: "python" },
  { label: "python manage.py shell", category: "python" },
  { label: "python -m pytest", category: "python" },
  { label: "python -m pip install -r requirements.txt", category: "python" },
  // pip
  { label: "pip install -r requirements.txt", category: "pip" },
  { label: "pip install", category: "pip" },
  { label: "pip list", category: "pip" },
  { label: "pip freeze > requirements.txt", category: "pip" },
  // pytest
  { label: "pytest", category: "pytest" },
  { label: "pytest -v", category: "pytest" },
  { label: "pytest -x", category: "pytest" },
  { label: "pytest --tb=short", category: "pytest" },
  // expo
  { label: "expo start", category: "expo" },
  { label: "expo start --tunnel", category: "expo" },
  { label: "expo build:android", category: "expo" },
  { label: "expo build:ios", category: "expo" },
  { label: "npx expo start", category: "expo" },
  // adb
  { label: "adb devices", category: "adb" },
  { label: "adb logcat", category: "adb" },
  { label: "adb shell", category: "adb" },
  { label: "adb reverse tcp:8081 tcp:8081", category: "adb" },
  // navigation
  { label: "cd ..", category: "nav" },
  { label: "ls -la", category: "nav" },
  { label: "dir", category: "nav" },
  { label: "pwd", category: "nav" },
  { label: "mkdir", category: "nav" },
  { label: "rm -rf", category: "nav" },
  { label: "cp -r", category: "nav" },
  { label: "mv", category: "nav" },
  // search
  { label: "rg --type ts", category: "search" },
  { label: "rg -n", category: "search" },
  { label: "find . -name", category: "search" },
  // curl / http
  { label: "curl -s", category: "http" },
  { label: "curl -X POST -H 'Content-Type: application/json' -d", category: "http" },
  // powershell / misc
  { label: "Get-ChildItem", category: "pwsh" },
  { label: "Set-Location", category: "pwsh" },
  { label: "Write-Host", category: "pwsh" },
  { label: "Invoke-WebRequest", category: "pwsh" },
  { label: "cat", category: "misc" },
  { label: "echo", category: "misc" },
  { label: "export", category: "misc" },
  { label: "which", category: "misc" },
  { label: "kill -9", category: "misc" },
];

function getSuggestions(input: string): Suggestion[] {
  const trimmed = input.trimStart().toLowerCase();
  if (!trimmed) return [];
  return SUGGESTIONS.filter((s) => s.label.toLowerCase().startsWith(trimmed)).slice(0, 8);
}

// ─── Category badge colors ────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  docker: T.ac4,
  git: T.ac2,
  npm: T.ac3,
  pnpm: T.ac4,
  yarn: T.ac1,
  node: T.ac1,
  python: T.ac2,
  pip: T.ac2,
  pytest: T.ac2,
  expo: T.ac4,
  adb: T.ac3,
  nav: T.tx2,
  search: T.tx2,
  http: T.ac4,
  pwsh: T.ac4,
  misc: T.tx2,
};

// ─── Line styling helpers ─────────────────────────────────────────────────────

type LineStyle = {
  color: string;
  prefix?: string;
  prefixColor?: string;
  faded?: boolean;
};

function getLineStyle(kind: TerminalLine["kind"]): LineStyle {
  switch (kind) {
    case "stderr":
      return { color: T.ac3, prefix: "ERR", prefixColor: T.ac3 };
    case "error":
      return { color: T.ac3, prefix: "ERR", prefixColor: T.ac3 };
    case "exit":
      return { color: T.tx2, prefix: "EXIT", prefixColor: T.tx2, faded: true };
    case "status":
      return { color: T.tx2, prefix: "SYS", prefixColor: T.tx2, faded: true };
    case "ready":
      return { color: T.ac1, prefix: "RDY", prefixColor: T.ac1 };
    case "local":
      return { color: T.tx0, prefix: "IN", prefixColor: T.tx1 };
    case "output":
    default:
      return { color: T.tx0, prefix: "OUT", prefixColor: T.tx2 };
  }
}

// ─── Exit code badge ──────────────────────────────────────────────────────────

function parseExitCode(text: string, kind: TerminalLine["kind"]): number | null {
  if (kind !== "exit") return null;
  const match = text.match(/exit.*?(\d+)/i);
  return match ? parseInt(match[1], 10) : null;
}

// ─── Main component ───────────────────────────────────────────────────────────

export function TerminalSheet({ visible, token, project, onClose, onNeedSetup }: Props) {
  const [session, setSession] = useState<TerminalSession | null>(null);
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<"idle" | "connecting" | "connected" | "reconnecting" | "closed" | "error">("idle");
  const [error, setError] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const listRef = useRef<FlatList<TerminalLine>>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const lastSequenceRef = useRef(0);
  const onNeedSetupRef = useRef(onNeedSetup);

  const projectId = project?.id || "";
  const projectPath = project?.local_path || "";
  const title = project?.name || "Terminal";
  const cwd = session?.cwd || project?.local_path || "";
  const canSend = Boolean(token && session && !TERMINAL_DONE.has(session.status));

  const suggestions = useMemo(() => getSuggestions(input), [input]);

  useEffect(() => { onNeedSetupRef.current = onNeedSetup; }, [onNeedSetup]);

  const openTerminal = useCallback(async () => {
    if (!visible) return;
    if (!token || !projectId) { onNeedSetupRef.current(); return; }
    setStatus("connecting");
    setError("");
    lastSequenceRef.current = 0;
    try {
      const next = await createTerminalSession(token, projectId, projectPath);
      setSession(next);
      setLines((current) => current.length ? current : [{
        id: "local-start",
        sequence: 0,
        kind: "local",
        text: `Starting ${next.shell} in ${next.cwd}`
      }]);
      const backfill = await fetchTerminalEvents(token, next.id);
      mergeEvents(backfill);
      connectSocket(next);
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Could not start terminal.");
    }
  }, [projectId, projectPath, token, visible]);

  useEffect(() => {
    if (!visible) return;
    openTerminal();
    return () => { wsRef.current?.close(); wsRef.current = null; };
  }, [openTerminal, visible]);

  useEffect(() => {
    if (!visible || !token || !session) return;
    const intervalId = setInterval(async () => {
      try {
        const nextEvents = await fetchTerminalEvents(token, session.id, lastSequenceRef.current);
        mergeEvents(nextEvents);
      } catch { }
    }, 1500);
    return () => clearInterval(intervalId);
  }, [session?.id, token, visible]);

  useEffect(() => {
    if (autoScroll && lines.length) {
      requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
    }
  }, [autoScroll, lines.length]);

  function mergeEvents(events: TerminalEvent[]) {
    if (!events.length) return;
    setLines((current) => {
      const map = new Map(current.map((line) => [line.id, line]));
      events.forEach((event) => {
        map.set(event.id, terminalLineFromEvent(event));
        lastSequenceRef.current = Math.max(lastSequenceRef.current, event.sequence);
      });
      return [...map.values()].sort((a, b) => a.sequence - b.sequence);
    });
    const terminalEvent = [...events].reverse().find((event) =>
      event.kind === "exit" || event.kind === "error" || event.kind === "status"
    );
    if (terminalEvent?.payload?.status) {
      setSession((current) =>
        current ? { ...current, status: String(terminalEvent.payload.status) as TerminalSession["status"] } : current
      );
    }
  }

  function connectSocket(nextSession = session) {
    if (!token || !nextSession) return;
    wsRef.current?.close();
    const ws = new WebSocket(terminalWebSocketUrl(nextSession.id, token));
    wsRef.current = ws;
    ws.onopen = async () => {
      setStatus("connected");
      try { mergeEvents(await fetchTerminalEvents(token, nextSession.id, lastSequenceRef.current)); } catch { }
    };
    ws.onmessage = (message) => {
      try {
        const payload = JSON.parse(message.data) as { type?: string; event?: TerminalEvent };
        if (payload.event) mergeEvents([payload.event]);
      } catch { }
    };
    ws.onerror = () => setStatus("error");
    ws.onclose = () => {
      if (!visible) return;
      setStatus((current) => current === "closed" ? "closed" : "reconnecting");
    };
  }

  async function handleSend(text = input) {
    if (!token || !session || !text) return;
    setInput("");
    const data = text.endsWith("\r") || text.endsWith("\n") ? text : `${text}\r`;
    setLines((current) => [...current, {
      id: `local-${Date.now()}`,
      sequence: lastSequenceRef.current + 0.1,
      kind: "local",
      text: `PS> ${text}`
    }]);
    try {
      await sendTerminalInput(token, session.id, data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send input.");
    }
  }

  async function handleCtrlC() {
    if (!token || !session) return;
    await sendTerminalInput(token, session.id, "\x03");
  }

  async function handleKill() {
    if (!token || !session) return;
    try {
      const next = await killTerminal(token, session.id);
      setSession(next);
      setStatus("closed");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not kill terminal.");
    }
  }

  function handleSuggestionTap(label: string) {
    setInput(label);
  }

  const statusLabel = useMemo(() => {
    if (session?.status) return session.status;
    return status;
  }, [session?.status, status]);

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={styles.root}>
        <KeyboardAvoidingView
          style={styles.fill}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          keyboardVerticalOffset={0}
        >
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerMain}>
              <Text style={styles.eyebrow}>pwsh terminal</Text>
              <Text style={styles.title} numberOfLines={1}>{title}</Text>
              <Text style={styles.cwd} numberOfLines={1}>{cwd || "waiting for workspace"}</Text>
            </View>
            <StatusPill value={statusLabel} />
            <Pressable style={styles.iconButton} onPress={() => connectSocket()} hitSlop={8}>
              <RotateCw size={17} color={T.tx1} />
            </Pressable>
            <Pressable style={styles.iconButton} onPress={handleKill} hitSlop={8}>
              <Skull size={17} color={T.ac3} />
            </Pressable>
            <Pressable style={styles.iconButton} onPress={onClose} hitSlop={8}>
              <X size={18} color={T.tx1} />
            </Pressable>
          </View>

          {/* Error banner */}
          {error ? (
            <View style={styles.errorBanner}>
              <Text style={styles.errorBannerLabel}>⚠ Error</Text>
              <Text style={styles.errorBannerText}>{error}</Text>
            </View>
          ) : null}

          {/* Output */}
          <FlatList
            ref={listRef}
            data={lines}
            keyExtractor={(item) => item.id}
            style={styles.output}
            contentContainerStyle={styles.outputContent}
            onScrollBeginDrag={() => setAutoScroll(false)}
            renderItem={({ item }) => <TerminalLineView line={item} />}
            ListEmptyComponent={
              <View style={styles.empty}>
                <ActivityIndicator color={T.tx1} />
                <Text style={styles.emptyText}>Connecting to local pwsh…</Text>
              </View>
            }
          />

          {/* Suggestion bar — sits above input, inside KeyboardAvoidingView */}
          {suggestions.length > 0 ? (
            <View style={styles.suggestions}>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                keyboardShouldPersistTaps="always"
                contentContainerStyle={styles.suggestionsContent}
              >
                {suggestions.map((s) => (
                  <Pressable
                    key={s.label}
                    style={styles.suggestionChip}
                    onPress={() => handleSuggestionTap(s.label)}
                    hitSlop={4}
                  >
                    <Text
                      style={[styles.suggestionCategory, { color: CATEGORY_COLORS[s.category] ?? T.tx2 }]}
                    >
                      {s.category}
                    </Text>
                    <Text style={styles.suggestionLabel}>{s.label}</Text>
                    <ChevronRight size={10} color={T.tx3} />
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          ) : null}

          {/* Input bar */}
          <View style={styles.inputBar}>
            <Pressable style={styles.smallButton} onPress={() => setLines([])} hitSlop={8}>
              <Trash2 size={16} color={T.tx2} />
            </Pressable>
            <Pressable style={styles.smallButton} onPress={handleCtrlC} hitSlop={8}>
              <KeyboardIcon size={16} color={T.tx2} />
              <Text style={styles.smallButtonText}>^C</Text>
            </Pressable>
            <TextInput
              style={styles.input}
              value={input}
              onChangeText={setInput}
              placeholder="Enter pwsh command"
              placeholderTextColor={T.tx3}
              autoCapitalize="none"
              autoCorrect={false}
              editable={canSend}
              onSubmitEditing={() => handleSend()}
              returnKeyType="send"
            />
            <Pressable
              style={[styles.sendButton, !canSend && styles.sendButtonDisabled]}
              onPress={() => handleSend()}
              disabled={!canSend}
              hitSlop={8}
            >
              <Send size={15} color={T.bg0} />
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </Modal>
  );
}

// ─── TerminalLineView ─────────────────────────────────────────────────────────

function TerminalLineView({ line }: { line: TerminalLine }) {
  const ls = getLineStyle(line.kind);
  const text = stripAnsi(line.text);
  const exitCode = parseExitCode(text, line.kind);

  // For "local" (command echo), render a distinct prompt row
  if (line.kind === "local") {
    return (
      <View style={lineStyles.row}>
        <View style={[lineStyles.badge, { backgroundColor: T.bg3 }]}>
          <Text style={[lineStyles.badgeText, { color: T.tx1 }]}>IN</Text>
        </View>
        <Text style={[lineStyles.text, { color: T.tx0, fontWeight: "700" }]} selectable>
          {text}
        </Text>
      </View>
    );
  }

  // Exit line: show exit code badge
  if (line.kind === "exit") {
    const success = exitCode === 0 || exitCode === null;
    return (
      <View style={[lineStyles.row, lineStyles.exitRow]}>
        <View style={[lineStyles.badge, { backgroundColor: T.bg3 }]}>
          <Text style={[lineStyles.badgeText, { color: success ? T.ac1 : T.ac3 }]}>
            {exitCode !== null ? `EXIT ${exitCode}` : "EXIT"}
          </Text>
        </View>
        <Text style={[lineStyles.text, { color: success ? T.ac1 : T.ac3, opacity: 0.85 }]} selectable>
          {text}
        </Text>
      </View>
    );
  }

  // Status / ready lines: subtle system row
  if (line.kind === "status" || line.kind === "ready") {
    return (
      <View style={[lineStyles.row, lineStyles.systemRow]}>
        <View style={[lineStyles.badge, { backgroundColor: T.bg3 }]}>
          <Text style={[lineStyles.badgeText, { color: T.tx2 }]}>{ls.prefix}</Text>
        </View>
        <Text style={[lineStyles.text, { color: T.tx2 }]} selectable>{text}</Text>
      </View>
    );
  }

  // stderr / error
  if (line.kind === "stderr" || line.kind === "error") {
    return (
      <View style={[lineStyles.row, lineStyles.errorRow]}>
        <View style={[lineStyles.badge, { backgroundColor: T.bg3 }]}>
          <Text style={[lineStyles.badgeText, { color: T.ac3 }]}>ERR</Text>
        </View>
        <Text style={[lineStyles.text, { color: T.ac3 }]} selectable>{text}</Text>
      </View>
    );
  }

  // stdout default
  return (
    <View style={lineStyles.stdoutRow}>
      <Text style={lineStyles.stdoutText} selectable>{text}</Text>
    </View>
  );
}

const lineStyles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 1,
    gap: 6,
  },
  exitRow: {
    marginTop: 4,
    marginBottom: 4,
  },
  systemRow: {
    opacity: 0.7,
  },
  errorRow: {
    marginBottom: 2,
  },
  badge: {
    borderRadius: 4,
    paddingHorizontal: 5,
    paddingVertical: 1,
    marginTop: 2,
    minWidth: 36,
    alignItems: "center",
  },
  badgeText: {
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 0.5,
    fontFamily: MONO_FONT,
  },
  text: {
    flex: 1,
    fontSize: 13,
    lineHeight: 20,
    fontFamily: MONO_FONT,
  },
  stdoutRow: {
    marginBottom: 0,
    paddingLeft: 2,
  },
  stdoutText: {
    color: T.tx0,
    fontSize: 13,
    lineHeight: 20,
    fontFamily: MONO_FONT,
  },
});

// ─── StatusPill ────────────────────────────────────────────────────────────────

function StatusPill({ value }: { value: string }) {
  const active = value === "running" || value === "connected";
  return (
    <View style={[styles.statusPill, active && styles.statusPillActive]}>
      {active && <View style={styles.statusDot} />}
      <Text style={[styles.statusPillText, active && styles.statusPillTextActive]}>{value}</Text>
    </View>
  );
}

// ─── Helper ────────────────────────────────────────────────────────────────────

function terminalLineFromEvent(event: TerminalEvent): TerminalLine {
  const prefix = event.kind === "stderr" ? "stderr: " : event.kind === "error" ? "error: " : "";
  return {
    id: event.id,
    sequence: event.sequence,
    kind: event.kind,
    text: `${prefix}${event.data || event.cwd || event.payload?.status || ""}`
  };
}

// ─── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: T.bg0 },
  fill: { flex: 1 },

  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: T.s8,
    paddingHorizontal: T.s14,
    paddingVertical: T.s12,
    borderBottomWidth: 1,
    borderBottomColor: T.bd0,
  },
  headerMain: { flex: 1, minWidth: 0 },
  eyebrow: { color: T.tx2, fontSize: T.f11, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.8 },
  title: { color: T.tx0, fontSize: T.f18, fontWeight: "800", marginTop: 2 },
  cwd: { color: T.tx2, fontSize: T.f12, marginTop: 2, fontFamily: MONO_FONT },

  iconButton: {
    width: 44, height: 44, borderRadius: T.r10, borderWidth: 1,
    borderColor: T.bd1, backgroundColor: T.bg2, alignItems: "center", justifyContent: "center",
  },

  statusPill: {
    height: 30, borderRadius: T.rFull, borderWidth: 1, borderColor: T.bd2,
    paddingHorizontal: T.s10, alignItems: "center", justifyContent: "center",
    flexDirection: "row", gap: 5,
  },
  statusPillActive: { borderColor: T.ac1, backgroundColor: T.bg2 },
  statusDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: T.ac1 },
  statusPillText: { color: T.tx2, fontSize: T.f11, fontWeight: "800" },
  statusPillTextActive: { color: T.ac1 },

  errorBanner: {
    margin: T.s12,
    backgroundColor: T.bg2,
    borderRadius: T.r8,
    padding: T.s10,
    borderLeftWidth: 3,
    borderLeftColor: T.ac3,
  },
  errorBannerLabel: { color: T.ac3, fontSize: T.f11, fontWeight: "800", marginBottom: 2 },
  errorBannerText: { color: T.ac3, fontSize: T.f13, fontFamily: MONO_FONT },

  output: { flex: 1, backgroundColor: T.bg0 },
  outputContent: { padding: T.s12, paddingBottom: T.s20, gap: 0 },

  empty: { paddingTop: T.s32, alignItems: "center", gap: T.s10 },
  emptyText: { color: T.tx2, fontSize: T.f13 },

  // Suggestions
  suggestions: {
    borderTopWidth: 1,
    borderTopColor: T.bd0,
    backgroundColor: T.bg1,
    paddingVertical: 6,
  },
  suggestionsContent: {
    paddingHorizontal: T.s10,
    gap: 6,
  },
  suggestionChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: T.bd1,
    backgroundColor: T.bg2,
  },
  suggestionCategory: {
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 0.5,
    textTransform: "uppercase",
    fontFamily: MONO_FONT,
  },
  suggestionLabel: {
    color: T.tx0,
    fontSize: 12,
    fontFamily: MONO_FONT,
  },

  // Input bar
  inputBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: T.s8,
    paddingHorizontal: T.s10,
    paddingVertical: T.s10,
    borderTopWidth: 1,
    borderTopColor: T.bd0,
    backgroundColor: T.bg1,
  },
  smallButton: {
    minWidth: 44, height: 44, borderRadius: T.r10, borderWidth: 1,
    borderColor: T.bd1, backgroundColor: T.bg2, alignItems: "center",
    justifyContent: "center", flexDirection: "row", gap: T.s4, paddingHorizontal: T.s8,
  },
  smallButtonText: { color: T.tx2, fontSize: T.f11, fontWeight: "800" },
  input: {
    flex: 1, minHeight: 44, borderRadius: T.r10, borderWidth: 1,
    borderColor: T.bd1, backgroundColor: T.bg2, color: T.tx0,
    paddingHorizontal: T.s12, fontSize: T.f14, fontFamily: MONO_FONT,
  },
  sendButton: { width: 44, height: 44, borderRadius: T.rFull, backgroundColor: T.tx0, alignItems: "center", justifyContent: "center" },
  sendButtonDisabled: { backgroundColor: T.bg4 },
});
