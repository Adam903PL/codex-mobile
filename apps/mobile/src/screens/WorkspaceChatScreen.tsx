import { NativeStackScreenProps } from "@react-navigation/native-stack";
import {
  BarChart2,
  Bug,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Code,
  Command,
  Cpu,
  GitBranch,
  GitFork,
  Globe,
  Layers,
  LogOut,
  Menu,
  MoreHorizontal,
  Package,
  Palette,
  Paperclip,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Send,
  Server,
  Settings,
  Shield,
  Square,
  SquareTerminal,
  Terminal,
  Wrench,
  X,
  Zap
} from "lucide-react-native";
import { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  Dimensions,
  FlatList,
  Keyboard,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View
} from "react-native";
import Markdown from "react-native-markdown-display";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Circle } from "react-native-svg";
import { AppSettingsModal } from "../components/AppSettingsModal";
import { CodexHubModal as CodexHubModalV2 } from "../components/codexHub/CodexHubModal";
import { TerminalSheet } from "../components/TerminalSheet";
import {
  AgentSession,
  ApprovalRequest,
  approveRequest,
  CodexCommandDefinition,
  createCodexAction,
  createSession,
  createSessionAttachment,
  Device,
  DeviceCapabilities,
  emergencyStopSession,
  FileMention,
  fetchCommandCatalog,
  fetchDeviceCapabilities,
  fetchSessionTimeline,
  fetchWorkspaceBootstrap,
  Project,
  rejectRequest,
  refreshDeviceCapabilities,
  searchSessions,
  sendSessionMessage,
  sessionWebSocketUrl,
  Task,
  TimelineItem,
  updateSessionSettings,
  SkillCapability
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { AppStackParamList } from "../navigation/AppNavigator";
import { AppSettingsSection, usePreferences } from "../preferences/PreferencesContext";

type Props = NativeStackScreenProps<AppStackParamList, "WorkspaceChat">;

const ACTIVE_TASK_STATUSES = new Set(["queued", "claimed", "running"]);
const TERMINAL_TASK_STATUSES = new Set(["succeeded", "failed", "timed_out", "canceled"]);
const CONNECTED_DEVICE_STATUSES = new Set(["online", "busy"]);
const { width: SW, height: SH } = Dimensions.get("window");
const LONG_FINAL_CHAR = 1800;
const LONG_FINAL_LINES = 14;
const PICKER_BOTTOM_OFFSET = Platform.OS === "ios" ? 128 : 118;
const PLUS_POPUP_BOTTOM_OFFSET = 210;
const PICKER_MAX_HEIGHT = Math.min(380, Math.round(SH * 0.46));
const DEVICE_HEARTBEAT_GRACE_MS = 2 * 60 * 1000;

const C = {
  bg0: "#0a0a0a",
  bg1: "#111111",
  bg2: "#181818",
  bg3: "#222222",
  bg4: "#2a2a2a",
  tx0: "#f0f0f0",
  tx1: "#a0a0a0",
  tx2: "#606060",
  tx3: "#303030",
  ac0: "#f0f0f0",
  ac1: "#10b981",
  ac2: "#f59e0b",
  ac3: "#ef4444",
  ac4: "#6366f1",
  bd0: "#1a1a1a",
  bd1: "#252525",
  bd2: "#333333"
} as const;

type TimelineEntry =
  | { type: "item"; id: string; item: TimelineItem }
  | { type: "run_log"; id: string; taskId: string; items: TimelineItem[]; completed: boolean; hasAssistantMessage: boolean };

function isConnectedDeviceStatus(status?: string | null) {
  return CONNECTED_DEVICE_STATUSES.has(String(status || "").toLowerCase());
}

function isFreshHeartbeat(value?: string | null) {
  if (!value) return false;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) && Date.now() - timestamp <= DEVICE_HEARTBEAT_GRACE_MS;
}

function projectDeviceStatus(project: Project | null | undefined, devices: Device[]) {
  const device = devices.find((item) => item.id === project?.device);
  return device?.status || project?.device_status || "";
}

function projectHasConnectedDevice(project: Project | null | undefined, devices: Device[]) {
  if (!project || !project.is_active || !isConnectedDeviceStatus(projectDeviceStatus(project, devices))) return false;
  const device = devices.find((item) => item.id === project.device);
  return isFreshHeartbeat(device?.last_seen_at || project.device_last_seen_at);
}

function choosePreferredProject(projects: Project[], devices: Device[]) {
  return projects.find((project) => projectHasConnectedDevice(project, devices)) || projects[0] || null;
}

function canReuseSession(session: AgentSession | null, selectedProjectId: string, projects: Project[], devices: Device[]) {
  if (!session || session.status === "closed") return false;
  if (selectedProjectId && session.project !== selectedProjectId) return false;
  const project = projects.find((item) => item.id === session.project);
  return projectHasConnectedDevice(project, devices);
}

type LimitUsage = {
  label: string;
  used?: number;
  limit?: number;
  remaining?: number;
  percent?: number;
  resetAt?: string;
  source?: string;
  observedAt?: string;
  windowMinutes?: number;
};

type LimitUsageStats = {
  fiveHour: LimitUsage;
  weekly: LimitUsage;
  hasTelemetry: boolean;
  refreshing?: boolean;
  error?: string;
  source?: string;
  observedAt?: string;
  stale?: boolean;
};

export function WorkspaceChatScreen({ navigation, route }: Props) {
  const { accessToken, signOut } = useAuth();
  const { preferences, t } = usePreferences();

  const [devices, setDevices] = useState<Device[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [workspaceAccount, setWorkspaceAccount] = useState<{ id: number; username: string } | null>(null);
  const [session, setSession] = useState<AgentSession | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [capabilities, setCapabilities] = useState<DeviceCapabilities["capabilities"]>({});
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [draft, setDraft] = useState("");
  const [modelDraft, setModelDraft] = useState("");
  const [profileDraft, setProfileDraft] = useState("");
  const [sandboxDraft, setSandboxDraft] = useState("workspace-write");
  const [approvalPolicyDraft, setApprovalPolicyDraft] = useState("on-request");
  const [branchDraft, setBranchDraft] = useState("");
  const [branchInput, setBranchInput] = useState("");
  const [webSearchDraft, setWebSearchDraft] = useState(false);
  const [planModeDraft, setPlanModeDraft] = useState(false);
  const [skillDraft, setSkillDraft] = useState<string[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSection, setSettingsSection] = useState<AppSettingsSection>("devices");
  const [isLoading, setIsLoading] = useState(true);
  const [isWorkspaceRefreshing, setIsWorkspaceRefreshing] = useState(false);
  const [workspaceRefreshError, setWorkspaceRefreshError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeTaskStatus, setActiveTaskStatus] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [realtimeStatus, setRealtimeStatus] = useState<"connected" | "reconnecting" | "polling" | "disconnected">("disconnected");
  const [imagePaths, setImagePaths] = useState<string[]>([]);
  const [commandCatalog, setCommandCatalog] = useState<CodexCommandDefinition[]>([]);
  const [slashCommands, setSlashCommands] = useState<Array<{ id: string; name: string; group: string; description: string }>>([]);

  const lastSequenceRef = useRef(0);
  const listRef = useRef<FlatList<TimelineEntry>>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const autoRefreshDoneRef = useRef(false);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawerX = useRef(new Animated.Value(-SW * 0.82)).current;
  const overlayOpacity = useRef(new Animated.Value(0)).current;

  const [plusOpen, setPlusOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [skillSearch, setSkillSearch] = useState("");
  const [skillFilter, setSkillFilter] = useState<"all" | "plugin" | "local" | "system">("all");
  const [modelOpen, setModelOpen] = useState(false);
  const [showModels, setShowModels] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [fileMentionOpen, setFileMentionOpen] = useState(false);
  const [fileMentionQuery, setFileMentionQuery] = useState("");
  const [attachPathDraft, setAttachPathDraft] = useState("");
  const [attachInputOpen, setAttachInputOpen] = useState(false);
  const [hubSection, setHubSection] = useState<string | null>(null);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<AgentSession[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [usageExpanded, setUsageExpanded] = useState(false);
  const [pluginsExpanded, setPluginsExpanded] = useState(false);
  const [selectedReasoning, setSelectedReasoning] = useState("Low");
  const [usageClock, setUsageClock] = useState(() => Date.now());
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  const activeProject = useMemo(
    () => projects.find((project) => project.id === (selectedProjectId || session?.project)) || null,
    [projects, selectedProjectId, session?.project]
  );
  const activeDevice = useMemo(
    () => devices.find((device) => device.id === (session?.device || activeProject?.device)) || null,
    [activeProject?.device, devices, session?.device]
  );
  const androidKeyboardOffset = Platform.OS === "android" ? keyboardHeight : 0;
  const pickerBottomOffset = PICKER_BOTTOM_OFFSET + keyboardHeight;
  const plusPopupBottomOffset = PLUS_POPUP_BOTTOM_OFFSET + keyboardHeight;

  const skills = capabilities.skills || [];
  const filteredSkills = useMemo(() => {
    const query = skillSearch.trim().toLowerCase();
    return skills.filter((skill) => {
      const source = String(skill.source || "").toLowerCase();
      if (skillFilter === "plugin" && source !== "plugin") return false;
      if (skillFilter === "local" && source !== "local") return false;
      if (skillFilter === "system" && source !== "system" && source !== "built-in") return false;
      if (!query) return true;
      return `${skill.name} ${skill.id} ${skill.description || ""}`.toLowerCase().includes(query);
    });
  }, [skillFilter, skillSearch, skills]);
  const filteredSkillRows = useMemo(() => buildSkillRows(filteredSkills), [filteredSkills]);

  const installedPlugins = useMemo(
    () => capabilities.installed_plugins || capabilities.plugins || skills.filter((skill) => skill.source === "plugin"),
    [capabilities, skills]
  );

  const models = useMemo(() => {
    if (Array.isArray(capabilities.models) && capabilities.models.length > 0) return capabilities.models;
    return parseModelsRaw(capabilities.models_raw);
  }, [capabilities.models, capabilities.models_raw]);

  const projectFiles = activeProject ? capabilities.project_files?.[activeProject.id] || [] : [];
  const filteredFileMentions = useMemo(() => {
    const query = fileMentionQuery.trim().toLowerCase();
    if (!query) return projectFiles.slice(0, 40);
    return projectFiles.filter((file) => fileMatchesMentionQuery(file, query)).slice(0, 40);
  }, [fileMentionQuery, projectFiles]);

  const canStop = Boolean(activeTaskId && ACTIVE_TASK_STATUSES.has(activeTaskStatus) && !isStopping);
  const canOpenTerminal = Boolean(activeProject && activeDevice);
  const groupedTimeline = useMemo(() => groupTimelineForChat(timeline), [timeline]);

  const activeModelId = useMemo(() => {
    const settings = session?.model_settings || {};
    const configSummary = capabilities.config_summary || {};
    const firstModel = models[0] ? modelIdFromCapability(models[0]) : "";
    return firstString(modelDraft, session?.model, activeProject?.default_model, settings.model, configSummary.model, firstModel);
  }, [activeProject?.default_model, capabilities.config_summary, modelDraft, models, session?.model, session?.model_settings]);

  const contextStats = useMemo(() => {
    const settings = session?.model_settings || {};
    const usedTokens = Number(settings.context_tokens_used || settings.context_used_tokens || 0);
    const modelWindow = Number(capabilities.model_context_windows?.[activeModelId] || 0);
    const maxTokens = Number(settings.context_tokens_total || settings.context_window_tokens || modelWindow || 0);
    const percentRaw = Number(settings.context_window_used || 0);
    const percent = maxTokens > 0 ? Math.round((usedTokens / maxTokens) * 100) : percentRaw > 0 ? Math.min(Math.max(percentRaw, 0), 100) : 0;
    return { modelId: activeModelId, usedTokens, maxTokens, percent, usageReported: usedTokens > 0, limitKnown: maxTokens > 0 };
  }, [activeModelId, capabilities.model_context_windows, session?.model_settings]);

  const limitStats = useMemo(() => buildLimitUsageStats(timeline, capabilities), [capabilities, timeline]);

  const mergeTimeline = useCallback((items: TimelineItem[]) => {
    if (!items.length) return;
    setTimeline((current) => {
      const byId = new Map(current.map((item) => [item.id, item]));
      items.forEach((item) => byId.set(item.id, item));
      return [...byId.values()].sort((a, b) => {
        // Realtime items can arrive with `sequence=0` (messages) while task events already have
        // a server-assigned sequence. Sorting by sequence first can incorrectly push a freshly
        // sent prompt below an already-rendered run log. Prefer `created_at` when either side
        // lacks a stable sequence.
        const aSeq = Number(a.sequence || 0);
        const bSeq = Number(b.sequence || 0);
        if (aSeq === 0 || bSeq === 0) {
          const byTime = a.created_at.localeCompare(b.created_at);
          if (byTime !== 0) return byTime;
          return a.id.localeCompare(b.id);
        }
        if (aSeq !== bSeq) return aSeq - bSeq;
        const byTime = a.created_at.localeCompare(b.created_at);
        return byTime !== 0 ? byTime : a.id.localeCompare(b.id);
      });
    });
    const maxSequence = Math.max(...items.map((item) => item.sequence || 0), lastSequenceRef.current);
    lastSequenceRef.current = maxSequence;
  }, []);

  useEffect(() => {
    const activeState = latestActiveTaskState(timeline);
    if (activeState) {
      setActiveTaskId(activeState.taskId);
      setActiveTaskStatus(activeState.status);
      setIsStopping(false);
      return;
    }

    const latestState = latestTaskState(timeline);
    if (latestState && TERMINAL_TASK_STATUSES.has(latestState.status)) {
      setActiveTaskId(null);
      setActiveTaskStatus(latestState.status);
      setIsStopping(false);
    }
  }, [timeline]);

  const loadTimeline = useCallback(
    async (nextSession = session, reset = false) => {
      if (!accessToken || !nextSession) return;
      const items = await fetchSessionTimeline(accessToken, nextSession.id);
      if (reset) {
        setTimeline([]);
        lastSequenceRef.current = 0;
      }
      mergeTimeline(items);
    },
    [accessToken, mergeTimeline, session]
  );

  const loadCapabilities = useCallback(
    async (deviceId: string) => {
      if (!accessToken) return {};
      try {
        const payload = await fetchDeviceCapabilities(accessToken, deviceId);
        setCapabilities(payload.capabilities || {});
        return payload.capabilities || {};
      } catch {
        setCapabilities({});
        return {};
      }
    },
    [accessToken]
  );

  const loadBootstrap = useCallback(async () => {
    if (!accessToken) return;
    setError("");
    setWorkspaceRefreshError("");
    setIsLoading(true);
    setIsWorkspaceRefreshing(true);
    try {
      const [payload, catalog] = await Promise.all([fetchWorkspaceBootstrap(accessToken), fetchCommandCatalog(accessToken)]);
      setCommandCatalog(catalog.commands || []);
      setSlashCommands(catalog.slash_commands || []);
      setWorkspaceAccount(payload.account || null);
      setDevices(payload.devices);
      setProjects(payload.projects);
      const preferredProject = choosePreferredProject(payload.projects, payload.devices);
      const bootstrapProjectId = payload.latest_session?.project || preferredProject?.id || "";
      const nextSession =
        preferences.startBehavior === "new-chat" || !canReuseSession(payload.latest_session, bootstrapProjectId, payload.projects, payload.devices)
          ? null
          : payload.latest_session;
      setPendingApprovals(payload.pending_approvals || []);
      setSession(nextSession);
      setSelectedProjectId(nextSession?.project || preferredProject?.id || "");
      if (nextSession) {
        setModelDraft(nextSession.model || "");
        setProfileDraft(nextSession.profile || "");
        setSandboxDraft(nextSession.sandbox || "workspace-write");
        setApprovalPolicyDraft(nextSession.approval_policy || "on-request");
        setBranchDraft(nextSession.git_branch || "");
        setBranchInput(nextSession.git_branch || "");
        setWebSearchDraft(nextSession.web_search_enabled);
        setPlanModeDraft(Boolean(nextSession.model_settings?.planning_mode));
        setSkillDraft(nextSession.selected_skills || []);
        const images = nextSession.tool_settings?.images;
        setImagePaths(Array.isArray(images) ? images.map(String) : []);
        setTimeline([]);
        lastSequenceRef.current = 0;
        mergeTimeline(await fetchSessionTimeline(accessToken, nextSession.id));
        await loadCapabilities(nextSession.device);
      } else if (preferredProject) {
        await loadCapabilities(preferredProject.device);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load workspace.";
      setError(message);
      setWorkspaceRefreshError(message);
    } finally {
      setIsLoading(false);
      setIsWorkspaceRefreshing(false);
    }
  }, [accessToken, loadCapabilities, mergeTimeline, preferences.startBehavior]);

  useEffect(() => {
    loadBootstrap();
  }, [loadBootstrap]);

  useEffect(() => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const showSub = Keyboard.addListener(showEvent, (event) => {
      const height = Math.max(0, SH - event.endCoordinates.screenY);
      setKeyboardHeight(height || event.endCoordinates.height || 0);
    });
    const hideSub = Keyboard.addListener(hideEvent, () => setKeyboardHeight(0));
    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, []);

  useEffect(() => {
    setActiveTaskId(null);
    setActiveTaskStatus("");
    setIsStopping(false);
  }, [session?.id]);

  useEffect(() => {
    const section = route.params?.settingsSection;
    if (section) {
      setSettingsSection(section);
      setSettingsOpen(true);
    }
  }, [route.params?.settingsSection]);

  useEffect(() => {
    if (!preferences.autoRefreshCapabilities || !accessToken || !activeDevice || autoRefreshDoneRef.current) return;
    autoRefreshDoneRef.current = true;
    refreshDeviceCapabilities(accessToken, activeDevice.id).catch(() => undefined);
  }, [accessToken, activeDevice, preferences.autoRefreshCapabilities]);

  useEffect(() => {
    if (!accessToken || !activeDevice) return;
    const timer = setInterval(() => {
      setUsageClock(Date.now());
      loadCapabilities(activeDevice.id).catch(() => undefined);
    }, 60_000);
    return () => clearInterval(timer);
  }, [accessToken, activeDevice, loadCapabilities]);

  useEffect(() => {
    if (!modelDraft && activeModelId) setModelDraft(activeModelId);
  }, [activeModelId, modelDraft]);

  useEffect(() => {
    if (!accessToken || !session) return;
    let closed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const connect = () => {
      setRealtimeStatus(reconnectAttemptsRef.current > 0 ? "reconnecting" : "disconnected");
      const socket = new WebSocket(sessionWebSocketUrl(session.id, accessToken));
      socketRef.current = socket;
      socket.onopen = () => {
        reconnectAttemptsRef.current = 0;
        setRealtimeStatus("connected");
        loadTimeline(session, true).catch(() => undefined);
      };
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as { type?: string; item?: TimelineItem; task?: Task };
          if (payload.type === "timeline.item" && payload.item) mergeTimeline([payload.item]);
          else if (payload.type === "task.status" && payload.task) {
            if (ACTIVE_TASK_STATUSES.has(payload.task.status)) {
              setActiveTaskId(payload.task.id);
              setActiveTaskStatus(payload.task.status);
              setIsStopping(false);
            } else if (TERMINAL_TASK_STATUSES.has(payload.task.status)) {
              setActiveTaskId(null);
              setActiveTaskStatus(payload.task.status);
              setIsStopping(false);
            }
          } else if (payload.type === "capabilities.updated" && activeDevice) loadCapabilities(activeDevice.id).catch(() => undefined);
          else if (payload.type === "workspace.updated") loadBootstrap().catch(() => undefined);
          else if (payload.type === "connection.ready") setRealtimeStatus("connected");
        } catch {
          setRealtimeStatus("polling");
        }
      };
      socket.onerror = () => setRealtimeStatus("polling");
      socket.onclose = () => {
        if (closed) return;
        reconnectAttemptsRef.current += 1;
        setRealtimeStatus("reconnecting");
        timer = setTimeout(connect, Math.min(1000 * reconnectAttemptsRef.current, 5000));
      };
    };
    connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      socketRef.current?.close();
    };
  }, [accessToken, activeDevice, loadBootstrap, loadCapabilities, loadTimeline, mergeTimeline, session]);

  useEffect(() => {
    if (!session) return;
    if (realtimeStatus === "connected" && !activeTaskId) return;
    const interval = realtimeStatus === "connected" ? 12000 : 3000;
    const timer = setInterval(() => loadTimeline().catch(() => undefined), interval);
    return () => clearInterval(timer);
  }, [activeTaskId, loadTimeline, realtimeStatus, session]);

  useEffect(() => {
    if (timeline.length > 0) requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
  }, [timeline.length]);

  useEffect(() => {
    Animated.parallel([
      Animated.spring(drawerX, { toValue: drawerOpen ? 0 : -SW * 0.82, useNativeDriver: true, tension: 100, friction: 20 }),
      Animated.timing(overlayOpacity, { toValue: drawerOpen ? 1 : 0, duration: 250, useNativeDriver: true })
    ]).start();
  }, [drawerOpen, drawerX, overlayOpacity]);

  useEffect(() => {
    if (!accessToken || !searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        setSearchResults(await searchSessions(accessToken, searchQuery));
      } catch {
      } finally {
        setIsSearching(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [searchQuery, accessToken]);

  const handleDraftChange = (text: string) => {
    setDraft(text);
    if (text.endsWith("$")) {
      setSkillsOpen(true);
      setFileMentionOpen(false);
    } else if (skillsOpen && !text.includes("$")) {
      setSkillsOpen(false);
    }
    const mention = currentFileMentionQuery(text);
    if (mention !== null) {
      setFileMentionQuery(mention);
      setFileMentionOpen(true);
      setPlusOpen(false);
      setSkillsOpen(false);
    } else {
      setFileMentionOpen(false);
      setFileMentionQuery("");
    }
  };

  async function ensureSession() {
    if (!accessToken) return null;
    if (canReuseSession(session, selectedProjectId, projects, devices)) return session;
    const preferredProject = choosePreferredProject(projects, devices);
    const projectId = selectedProjectId || preferredProject?.id;
    if (!projectId) {
      setSettingsSection("devices");
      setSettingsOpen(true);
      throw new Error("No project selected.");
    }
    const project = projects.find((item) => item.id === projectId);
    if (!projectHasConnectedDevice(project, devices)) {
      setSession(null);
      setSettingsSection("devices");
      setSettingsOpen(true);
      throw new Error("Urzadzenie projektu nie jest polaczone. Uruchom devlink connect albo wybierz aktywny workspace.");
    }
    const nextSession = await createSession(accessToken, projectId, project?.name || "DevLink chat", {
      model: modelDraft,
      profile: profileDraft,
      sandbox: sandboxDraft,
      approval_policy: approvalPolicyDraft,
      git_branch: branchDraft,
      selected_skills: skillDraft,
      web_search_enabled: webSearchDraft,
      model_settings: { planning_mode: planModeDraft },
      tool_settings: { images: imagePaths }
    });
    setSession(nextSession);
    setSelectedProjectId(nextSession.project);
    await loadCapabilities(nextSession.device);
    return nextSession;
  }

  async function handleSend() {
    if (!accessToken || !draft.trim() || isSending) return;
    const content = draft.trim();
    setDraft("");
    setSkillsOpen(false);
    setIsSending(true);
    setError("");
    try {
      const currentSession = await ensureSession();
      if (!currentSession) return;
      const optimisticId = `opt-${Date.now()}`;
      mergeTimeline([
        {
          id: optimisticId,
          kind: "user_message",
          content,
          task_id: null,
          sequence: lastSequenceRef.current + 1,
          payload: { optimistic: true },
          created_at: new Date().toISOString()
        },
        {
          id: `${optimisticId}-q`,
          kind: "queued",
          content: "Queued",
          task_id: null,
          sequence: lastSequenceRef.current + 2,
          payload: { status: "queued" },
          created_at: new Date().toISOString()
        }
      ]);
      const response = await sendSessionMessage(
        accessToken,
        currentSession.id,
        content,
        {
          model: modelDraft,
          profile: profileDraft,
          sandbox: sandboxDraft,
          approval_policy: approvalPolicyDraft,
          git_branch: branchDraft,
          selected_skills: skillDraft,
          web_search_enabled: webSearchDraft,
          model_settings: { ...(currentSession.model_settings || {}), planning_mode: planModeDraft },
          tool_settings: { ...(currentSession.tool_settings || {}), images: imagePaths }
        },
        skillDraft
      );
      setSession(response.session);
      setActiveTaskId(response.task.id);
      setActiveTaskStatus(response.task.status);
      setTimeline((current) => current.filter((item) => item.id !== optimisticId && item.id !== `${optimisticId}-q`));
      mergeTimeline([
        {
          id: response.message.id,
          kind: "user_message",
          content: response.message.content,
          task_id: response.task.id,
          sequence: lastSequenceRef.current + 1,
          payload: response.message.metadata,
          created_at: response.message.created_at
        }
      ]);
    } catch (err) {
      setDraft(content);
      setError(err instanceof Error ? err.message : "Failed to send.");
    } finally {
      setIsSending(false);
    }
  }

  async function handleStop() {
    if (!accessToken || !session || isStopping) return;
    setIsStopping(true);
    setError("");
    setActiveTaskId(null);
    setActiveTaskStatus("canceled");
    try {
      await emergencyStopSession(accessToken, session.id);
      await loadTimeline(session, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to stop.");
    } finally {
      setIsStopping(false);
    }
  }

  async function handleTogglePlanMode(nextValue: boolean) {
    setPlanModeDraft(nextValue);
    if (!accessToken || !session) return;
    try {
      const nextSession = await updateSessionSettings(accessToken, session.id, {
        model_settings: { ...(session.model_settings || {}), planning_mode: nextValue }
      });
      setSession(nextSession);
    } catch {
    }
  }

  async function handleSaveSettings() {
    if (!accessToken || !session) return;
    const nextSession = await updateSessionSettings(accessToken, session.id, {
      model: modelDraft,
      profile: profileDraft,
      sandbox: sandboxDraft,
      approval_policy: approvalPolicyDraft,
      git_branch: branchDraft,
      selected_skills: skillDraft,
      web_search_enabled: webSearchDraft,
      model_settings: { ...(session.model_settings || {}), planning_mode: planModeDraft },
      tool_settings: { ...(session.tool_settings || {}), images: imagePaths }
    });
    setSession(nextSession);
    setSettingsOpen(false);
  }

  async function handleSelectProject(projectId: string) {
    if (!accessToken) return;
    setError("");
    const project = projects.find((item) => item.id === projectId);
    setSelectedProjectId(projectId);
    if (!projectHasConnectedDevice(project, devices)) {
      setSession(null);
      setTimeline([]);
      setSettingsSection("devices");
      setSettingsOpen(true);
      setError("Urzadzenie projektu nie jest polaczone. Uruchom devlink connect albo wybierz aktywny workspace.");
      return;
    }
    const nextCapabilities = project ? await loadCapabilities(project.device) : capabilities;
    const branch = nextCapabilities.project_git?.[projectId]?.branch || "";
    setBranchDraft(branch);
    setBranchInput(branch);
    const nextSession = await createSession(accessToken, projectId, project?.name || "DevLink chat", {
      model: modelDraft,
      profile: profileDraft,
      sandbox: sandboxDraft,
      approval_policy: approvalPolicyDraft,
      git_branch: branch,
      selected_skills: skillDraft,
      web_search_enabled: webSearchDraft,
      model_settings: { planning_mode: planModeDraft },
      tool_settings: { images: imagePaths }
    });
    setSession(nextSession);
    setTimeline([]);
    lastSequenceRef.current = 0;
    setDrawerOpen(false);
  }

  async function handleSelectModel(modelId: string) {
    setModelDraft(modelId);
    setModelOpen(false);
    setShowModels(false);
    if (!accessToken || !session) return;
    try {
      const nextSession = await updateSessionSettings(accessToken, session.id, {
        model: modelId,
        model_settings: { ...(session.model_settings || {}), reasoning_effort: selectedReasoning }
      });
      setSession(nextSession);
    } catch {
    }
  }

  async function handleSelectReasoning(reasoning: string) {
    setSelectedReasoning(reasoning);
    setModelOpen(false);
    setShowModels(false);
    if (!modelDraft || !accessToken || !session) return;
    try {
      const nextSession = await updateSessionSettings(accessToken, session.id, {
        model_settings: { ...(session.model_settings || {}), reasoning_effort: reasoning }
      });
      setSession(nextSession);
    } catch {
    }
  }

  function toggleSkill(skillId: string) {
    setSkillDraft((current) => (current.includes(skillId) ? current.filter((item) => item !== skillId) : [...current, skillId]));
    if (draft.endsWith("$")) setDraft(draft.slice(0, -1));
    setSkillsOpen(false);
  }

  async function handleAddAttachmentPath() {
    const value = attachPathDraft.trim();
    if (!value) return;
    setImagePaths((current) => (current.includes(value) ? current : [...current, value]));
    if (accessToken && session) {
      try {
        await createSessionAttachment(accessToken, session.id, { path: value, type: "image" });
      } catch {
      }
    }
    setAttachPathDraft("");
    setAttachInputOpen(false);
    setPlusOpen(false);
  }

  async function handleSelectFileMention(file: FileMention) {
    const nextDraft = replaceCurrentFileMention(draft, file.relative_path);
    setDraft(nextDraft);
    setFileMentionOpen(false);
    setFileMentionQuery("");
    if (file.kind === "image") setImagePaths((current) => (current.includes(file.path) ? current : [...current, file.path]));
    if (accessToken && session) {
      try {
        await createSessionAttachment(accessToken, session.id, { path: file.path, type: file.kind === "image" ? "image" : "file" });
      } catch {
      }
    }
  }

  async function handleApprovalDecision(approvalId: string, decision: "approve" | "reject") {
    if (!accessToken) return;
    try {
      const updated = decision === "approve" ? await approveRequest(accessToken, approvalId) : await rejectRequest(accessToken, approvalId);
      setPendingApprovals((current) => current.map((item) => (item.id === approvalId ? updated : item)));
    } catch {
    }
  }

  async function handleRefreshCapabilities() {
    if (!accessToken || !activeDevice) return;
    try {
      await refreshDeviceCapabilities(accessToken, activeDevice.id);
      setActionMessage("Capabilities refresh queued.");
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Failed.");
    }
  }

  function toggleExpanded(itemId: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }

  const radius = 9;
  const circumference = 2 * Math.PI * radius;
  const contextPercent = contextStats.percent ?? 0;
  const dashOffset = circumference - (contextPercent / 100) * circumference;

  return (
    <SafeAreaView style={styles.root}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.fill}>
        <View style={styles.topBar}>
          <Pressable hitSlop={8} onPress={() => setDrawerOpen(true)} style={styles.iconBtn}>
            <Menu size={20} color={C.tx1} />
          </Pressable>

          <Pressable style={styles.topBarCenter} onPress={() => setDrawerOpen(true)}>
            <Text style={styles.topBarTitle} numberOfLines={1}>
              {activeProject?.name || "DevLink"}
            </Text>
            <View style={styles.statusPill}>
              <View style={[styles.statusDot, { backgroundColor: statusColor(realtimeStatus) }]} />
              <Text style={styles.statusText}>{statusLabel(realtimeStatus)}</Text>
            </View>
          </Pressable>

          <Pressable hitSlop={8} onPress={() => { setSession(null); setTimeline([]); setDraft(""); }} style={styles.iconBtn}>
            <Plus size={20} color={C.tx1} />
          </Pressable>
        </View>

        {error ? (
          <Pressable style={styles.errorBar} onPress={() => setError("")}>
            <Text style={styles.errorBarText} numberOfLines={2}>{error}</Text>
            <X size={14} color="#fca5a5" />
          </Pressable>
        ) : null}

        {isLoading ? (
          <View style={styles.centerPane}>
            <ActivityIndicator color={C.tx1} />
            <Text style={styles.centerText}>Loading...</Text>
          </View>
        ) : !activeProject ? (
          <EmptyPane
            hasDevices={devices.length > 0}
            onConnect={() => { setSettingsSection("devices"); setSettingsOpen(true); }}
            onRefresh={loadBootstrap}
            t={t}
          />
        ) : timeline.length === 0 ? (
          <View style={styles.centerPane}>
            <View style={styles.emptyLogo}><Text style={styles.emptyLogoText}>DL</Text></View>
            <Text style={styles.emptyTitle}>{t("chat.empty")}</Text>
            <Text style={styles.emptyHint}>{activeProject.name}</Text>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={groupedTimeline}
            keyExtractor={(entry) => entry.id}
            keyboardDismissMode="interactive"
            keyboardShouldPersistTaps="handled"
            renderItem={({ item }) =>
              item.type === "item" ? (
                <TimelineRow item={item.item} expanded={expanded.has(item.id)} onToggle={() => toggleExpanded(item.id)} />
              ) : (
                <RunLogGroup
                  entry={item}
                  expanded={expanded.has(item.id) || (!item.hasAssistantMessage && preferences.runLogDefault === "expanded") || !item.completed}
                  onToggle={() => toggleExpanded(item.id)}
                />
              )
            }
            contentContainerStyle={styles.timelineContent}
          />
        )}

        <View style={[styles.composerWrap, androidKeyboardOffset ? { marginBottom: androidKeyboardOffset } : null]}>
          {(skillDraft.length > 0 || imagePaths.length > 0) ? (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipsRow}>
              {skillDraft.map((id) => {
                const skill = skills.find((item) => item.id === id);
                return (
                  <View key={id} style={styles.chip}>
                    <Wrench size={11} color={C.tx1} />
                    <Text style={styles.chipText}>{skill?.name || id}</Text>
                    <Pressable hitSlop={4} onPress={() => toggleSkill(id)}><X size={11} color={C.tx2} /></Pressable>
                  </View>
                );
              })}
              {imagePaths.map((path) => (
                <View key={path} style={styles.chip}>
                  <Paperclip size={11} color={C.tx1} />
                  <Text style={styles.chipText} numberOfLines={1}>{path.split(/[\\/]/).pop()}</Text>
                  <Pressable hitSlop={4} onPress={() => setImagePaths((current) => current.filter((item) => item !== path))}>
                    <X size={11} color={C.tx2} />
                  </Pressable>
                </View>
              ))}
            </ScrollView>
          ) : null}

          <View style={styles.composerBox}>
            <Pressable hitSlop={6} style={styles.composerIconBtn} onPress={() => setPlusOpen(!plusOpen)}>
              <Plus size={18} color={C.tx2} />
            </Pressable>
            <TextInput
              style={styles.composerInput}
              placeholder={t("chat.prompt")}
              placeholderTextColor={C.tx3}
              value={draft}
              onChangeText={handleDraftChange}
              multiline
              textAlignVertical="top"
            />
            {canStop ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Emergency stop"
                style={styles.stopBtn}
                onPress={handleStop}
                disabled={isStopping}
              >
                <Square size={12} color={C.bg0} fill={C.bg0} />
              </Pressable>
            ) : (
              <Pressable
                style={[styles.sendBtn, (!draft.trim() || isSending) && styles.sendBtnOff]}
                onPress={handleSend}
                disabled={!draft.trim() || isSending}
              >
                {isSending ? <ActivityIndicator size="small" color={C.bg0} /> : <Send size={14} color={C.bg0} />}
              </Pressable>
            )}
          </View>

          <View style={styles.toolbar}>
            <Pressable style={styles.toolbarBtn} onPress={() => setContextOpen(true)}>
              <Svg height={20} width={20} viewBox="0 0 24 24">
                <Circle cx="12" cy="12" r={radius} stroke={C.bd2} strokeWidth="2.5" fill="none" />
                <Circle
                  cx="12"
                  cy="12"
                  r={radius}
                  stroke={C.tx0}
                  strokeWidth="2.5"
                  fill="none"
                  strokeDasharray={circumference}
                  strokeDashoffset={dashOffset}
                  strokeLinecap="round"
                  transform="rotate(-90 12 12)"
                />
              </Svg>
              <Text style={styles.toolbarBtnText}>{contextPercent > 0 ? `${contextPercent}%` : "ctx"}</Text>
            </Pressable>

            <Pressable style={[styles.toolbarPill, planModeDraft && styles.toolbarPillActive]} onPress={() => handleTogglePlanMode(!planModeDraft)}>
              <Zap size={12} color={planModeDraft ? C.bg0 : C.tx2} />
              <Text style={[styles.toolbarPillText, planModeDraft && styles.toolbarPillTextActive]}>Plan</Text>
            </Pressable>

            <Pressable style={styles.toolbarBtn} onPress={() => setModelOpen(true)}>
              <Cpu size={13} color={C.tx2} />
              <Text style={styles.toolbarBtnText} numberOfLines={1}>{modelDraft ? shortModelName(modelDraft) : "model"}</Text>
              <ChevronDown size={11} color={C.tx3} />
            </Pressable>

            <View style={{ flex: 1 }} />

            {webSearchDraft ? (
              <Pressable hitSlop={6} onPress={() => setWebSearchDraft(false)}>
                <Globe size={16} color={C.ac1} />
              </Pressable>
            ) : null}

            <Pressable
              style={[styles.terminalToolbarBtn, !canOpenTerminal && styles.terminalToolbarBtnDisabled]}
              onPress={() => {
                if (!canOpenTerminal) {
                  setSettingsSection("devices");
                  setSettingsOpen(true);
                  return;
                }
                setTerminalOpen(true);
              }}
              hitSlop={8}
            >
              <SquareTerminal size={17} color={canOpenTerminal ? C.tx1 : C.tx3} />
            </Pressable>
          </View>
        </View>
      </KeyboardAvoidingView>

      {drawerOpen ? (
        <View style={styles.drawerRoot} pointerEvents="box-none">
          <Animated.View style={[styles.overlay, { opacity: overlayOpacity }]}>
            <Pressable style={StyleSheet.absoluteFill} onPress={() => setDrawerOpen(false)} />
          </Animated.View>
          <Animated.View style={[styles.drawerPanel, { transform: [{ translateX: drawerX }] }]}>
            <SafeAreaView style={styles.fill} edges={["top", "left", "bottom"]}>
          <View style={styles.drawerTop}>
            <View style={styles.drawerLogo}><Text style={styles.drawerLogoText}>DL</Text></View>
            <Text style={styles.drawerBrand}>DevLink</Text>
            <View style={{ flex: 1 }} />
            <Pressable hitSlop={8} onPress={() => { setSettingsSection("account"); setSettingsOpen(true); setDrawerOpen(false); }}>
              <Settings size={18} color={C.tx2} />
            </Pressable>
          </View>

          <View style={styles.drawerSearch}>
            <Search size={14} color={C.tx3} />
            <TextInput
              style={styles.drawerSearchInput}
              placeholder="Search chats..."
              placeholderTextColor={C.tx3}
              value={searchQuery}
              onChangeText={setSearchQuery}
            />
            {searchQuery ? <Pressable hitSlop={4} onPress={() => setSearchQuery("")}><X size={14} color={C.tx3} /></Pressable> : null}
          </View>

          <ScrollView style={styles.drawerScroll} showsVerticalScrollIndicator={false}>
            {searchQuery ? (
              <DrawerSection label="RESULTS">
                {isSearching ? <ActivityIndicator color={C.tx1} style={{ margin: 12 }} /> : null}
                {!isSearching && searchResults.length === 0 ? <Text style={styles.drawerMuted}>No results.</Text> : null}
                {!isSearching ? searchResults.map((result) => (
                  <DrawerItem
                    key={result.id}
                    label={result.title || "Chat"}
                    onPress={() => {
                      setSession(result);
                      setTimeline([]);
                      loadTimeline(result, true);
                      setDrawerOpen(false);
                      setSearchQuery("");
                    }}
                  />
                )) : null}
              </DrawerSection>
            ) : (
              <>
                <Pressable style={styles.newChatBtn} onPress={() => { setSession(null); setTimeline([]); setDraft(""); setDrawerOpen(false); }}>
                  <Plus size={15} color={C.tx0} />
                  <Text style={styles.newChatText}>{t("drawer.newChat")}</Text>
                </Pressable>

                <DrawerUsageCard stats={limitStats} expanded={usageExpanded} now={usageClock} onToggle={() => setUsageExpanded((value) => !value)} />

                <DrawerSection label="CODEX HUB">
                  {([
                    ["overview", "Overview", <BarChart2 size={15} color={C.tx2} />],
                    ["workspace", "Workspaces", <Layers size={15} color={C.tx2} />],
                    ["commands", "Commands", <Command size={15} color={C.tx2} />],
                    ["plugins", "Plugins", <Package size={15} color={C.tx2} />],
                    ["mcp", "MCP Servers", <Server size={15} color={C.tx2} />],
                    ["git", "Git", <GitBranch size={15} color={C.tx2} />],
                    ["cloud", "Cloud", <Globe size={15} color={C.tx2} />],
                    ["debug", "Debug", <Bug size={15} color={C.tx2} />],
                    ["approvals", "Approvals", <Shield size={15} color={C.tx2} />]
                  ] as [string, string, ReactNode][]).map(([section, label, icon]) => (
                    <DrawerItem key={section} label={label} icon={icon} onPress={() => { setHubSection(section); setDrawerOpen(false); }} />
                  ))}
                  <DrawerItem label="Refresh" icon={<RefreshCw size={15} color={C.tx2} />} onPress={() => { loadBootstrap(); setDrawerOpen(false); }} />
                </DrawerSection>

                <DrawerSection label="PLUGINS" collapsible expanded={pluginsExpanded} onToggle={() => setPluginsExpanded((value) => !value)}>
                  {installedPlugins.length === 0 ? <Text style={styles.drawerMuted}>No plugins installed.</Text> : null}
                  {installedPlugins.slice(0, 8).map((plugin) => {
                    const active = skillDraft.includes(plugin.id);
                    return (
                      <DrawerItem
                        key={plugin.id}
                        label={plugin.name}
                        icon={<Package size={14} color={active ? C.ac1 : C.tx2} />}
                        trailing={active ? <Check size={14} color={C.ac1} /> : undefined}
                        active={active}
                        onPress={() => toggleSkill(plugin.id)}
                      />
                    );
                  })}
                </DrawerSection>

                {session ? (
                  <DrawerSection label="CURRENT">
                    <DrawerItem label={session.title || "Chat"} active icon={<View style={styles.activeSessionDot} />} />
                  </DrawerSection>
                ) : null}
              </>
            )}
          </ScrollView>

          <View style={styles.drawerFooter}>
            <View style={styles.drawerUserRow}>
              <View style={styles.avatar}><Text style={styles.avatarText}>U</Text></View>
              <Text style={styles.drawerUserName}>User</Text>
            </View>
            <Pressable hitSlop={8} onPress={signOut}>
              <LogOut size={18} color={C.tx2} />
            </Pressable>
          </View>
            </SafeAreaView>
          </Animated.View>
        </View>
      ) : null}

      {plusOpen ? (
        <>
          <Pressable style={styles.popupBg} onPress={() => { setPlusOpen(false); setAttachInputOpen(false); }} />
          <View style={[styles.popup, { bottom: plusPopupBottomOffset }]}>
            <PopupItem
              icon={<Paperclip size={16} color={C.tx0} />}
              label="Attach file (@)"
              onPress={() => { setDraft((current) => `${current}@`); setPlusOpen(false); setFileMentionOpen(true); }}
            />
            <PopupItem
              icon={<Globe size={16} color={webSearchDraft ? C.ac1 : C.tx0} />}
              label={`Web Search${webSearchDraft ? " · on" : ""}`}
              onPress={() => setWebSearchDraft((value) => !value)}
              trailing={webSearchDraft ? <Check size={14} color={C.ac1} /> : undefined}
            />
            <PopupItem icon={<Wrench size={16} color={C.tx0} />} label="Add Skill ($)" onPress={() => { setPlusOpen(false); setSkillsOpen(true); }} />
            <PopupItem icon={<Paperclip size={16} color={C.tx1} />} label="Advanced path" onPress={() => setAttachInputOpen((value) => !value)} />
            {attachInputOpen ? (
              <View style={styles.attachBox}>
                <TextInput
                  style={styles.attachInput}
                  placeholder="C:\\path\\image.png"
                  placeholderTextColor={C.tx2}
                  value={attachPathDraft}
                  onChangeText={setAttachPathDraft}
                />
                <Pressable style={styles.attachBtn} onPress={handleAddAttachmentPath}>
                  <Text style={styles.attachBtnText}>Add</Text>
                </Pressable>
              </View>
            ) : null}
          </View>
        </>
      ) : null}

      {skillsOpen ? (
        <>
          <Pressable style={styles.popupBg} onPress={() => setSkillsOpen(false)} />
          <View style={[styles.skillsPopup, { bottom: pickerBottomOffset }]}>
            <View style={styles.skillsHeader}>
              <Text style={styles.skillsTitle}>Skills</Text>
              <Text style={styles.skillsCount}>{filteredSkills.length}/{skills.length}</Text>
            </View>
            <TextInput
              style={styles.skillsSearch}
              placeholder="Search..."
              placeholderTextColor={C.tx3}
              value={skillSearch}
              onChangeText={setSkillSearch}
            />
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
              {(["all", "plugin", "local", "system"] as const).map((filter) => (
                <Pressable key={filter} style={[styles.filterChip, skillFilter === filter && styles.filterChipActive]} onPress={() => setSkillFilter(filter)}>
                  <Text style={[styles.filterChipText, skillFilter === filter && styles.filterChipTextActive]}>{filter}</Text>
                </Pressable>
              ))}
            </ScrollView>
            <FlatList
              data={filteredSkillRows}
              keyExtractor={(row) => row.renderKey}
              keyboardShouldPersistTaps="handled"
              style={styles.pickerList}
              contentContainerStyle={styles.pickerListContent}
              renderItem={({ item: row }) => {
                const skill = row.skill;
                const active = skillDraft.includes(skillIdentity(skill));
                return (
                  <Pressable style={[styles.skillItem, active && styles.skillItemActive]} onPress={() => toggleSkill(skillIdentity(skill))}>
                    <View style={styles.skillIcon}>
                      {skill.source === "plugin" ? <Package size={14} color={C.tx1} /> : <Wrench size={14} color={C.tx1} />}
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.skillName}>{skill.name}</Text>
                      <Text style={styles.skillSrc}>{skill.source || "skill"}</Text>
                    </View>
                    {active ? <Check size={14} color={C.ac1} /> : null}
                  </Pressable>
                );
              }}
              ListEmptyComponent={<Text style={[styles.drawerMuted, { margin: 12 }]}>No skills match.</Text>}
            />
          </View>
        </>
      ) : null}

      {fileMentionOpen ? (
        <>
          <Pressable style={styles.popupBg} onPress={() => setFileMentionOpen(false)} />
          <View style={[styles.skillsPopup, { bottom: pickerBottomOffset }]}>
            <View style={styles.skillsHeader}>
              <Text style={styles.skillsTitle}>Project files</Text>
              <Text style={styles.skillsCount}>@{fileMentionQuery}</Text>
            </View>
            <FlatList
              data={filteredFileMentions}
              keyExtractor={(file, index) => `${file.path || file.relative_path || file.name || "file"}#${index}`}
              keyboardShouldPersistTaps="handled"
              style={styles.pickerList}
              contentContainerStyle={styles.pickerListContent}
              ListEmptyComponent={<Text style={[styles.drawerMuted, { margin: 12 }]}>No files. Refresh capabilities first.</Text>}
              renderItem={({ item: file }) => (
                <Pressable style={styles.skillItem} onPress={() => handleSelectFileMention(file)}>
                  <View style={styles.skillIcon}><Paperclip size={14} color={C.tx1} /></View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.skillName}>{file.name}</Text>
                    <Text style={styles.skillSrc} numberOfLines={1}>{file.relative_path}</Text>
                  </View>
                </Pressable>
              )}
            />
          </View>
        </>
      ) : null}

      {modelOpen ? (
        <Modal transparent visible animationType="fade" onRequestClose={() => setModelOpen(false)}>
          <Pressable style={styles.modalOverlay} onPress={() => { setModelOpen(false); setShowModels(false); }}>
            <View style={styles.modelSheet}>
              <View style={styles.modelCol}>
                <Text style={styles.modelColHead}>Reasoning</Text>
                {reasoningLevels(models, modelDraft).map((level) => (
                  <Pressable key={level} style={styles.modelOption} onPress={() => handleSelectReasoning(level)}>
                    <Text style={styles.modelOptionText}>{level}</Text>
                    {selectedReasoning === level ? <Check size={14} color={C.ac1} /> : null}
                  </Pressable>
                ))}
                <View style={styles.modelDivider} />
                <Pressable style={[styles.modelOption, showModels && { backgroundColor: C.bg4 }]} onPress={() => setShowModels((value) => !value)}>
                  <Text style={styles.modelOptionText}>{modelDraft ? shortModelName(modelDraft) : "Choose model"}</Text>
                  <ChevronRight size={14} color={C.tx2} />
                </Pressable>
                <Text style={styles.modelHint}>{models.length} models from CLI</Text>
              </View>
              {showModels ? (
                <View style={[styles.modelCol, { borderLeftWidth: 1, borderLeftColor: C.bd1 }]}>
                  <Text style={styles.modelColHead}>Model</Text>
                  <ScrollView style={{ maxHeight: 320 }}>
                    {models.map((model: any) => {
                      const id = modelIdFromCapability(model);
                      const name = typeof model === "string" ? model : model.name || model.id;
                      return (
                        <Pressable key={id} style={styles.modelOption} onPress={() => handleSelectModel(id)}>
                          <Text style={styles.modelOptionText} numberOfLines={1}>{name}</Text>
                          {modelDraft === id ? <Check size={14} color={C.ac1} /> : null}
                        </Pressable>
                      );
                    })}
                    {models.length === 0 ? <Text style={styles.modelHint}>No models. Refresh capabilities.</Text> : null}
                  </ScrollView>
                </View>
              ) : null}
            </View>
          </Pressable>
        </Modal>
      ) : null}

      {contextOpen ? (
        <Modal transparent visible animationType="fade" onRequestClose={() => setContextOpen(false)}>
          <Pressable style={styles.modalOverlay} onPress={() => setContextOpen(false)}>
            <View style={styles.ctxCard}>
              <Text style={styles.ctxTitle}>Context window</Text>
              <Text style={styles.ctxPercent}>{contextPercent}%</Text>
              <Text style={styles.ctxDetail}>
                {contextStats.maxTokens ? `${contextStats.usedTokens.toLocaleString()} / ${contextStats.maxTokens.toLocaleString()} tokens` : "Usage not reported yet"}
              </Text>
              <Text style={styles.ctxNote}>Model: {contextStats.modelId || "unknown"}</Text>
            </View>
          </Pressable>
        </Modal>
      ) : null}

      {hubSection ? (
        <CodexHubModalV2
          section={hubSection}
          onClose={() => setHubSection(null)}
          projects={projects}
          workspaceAccount={workspaceAccount}
          workspaceRefreshing={isWorkspaceRefreshing}
          workspaceError={workspaceRefreshError}
          activeProject={activeProject}
          devices={devices}
          activeDevice={activeDevice}
          capabilities={capabilities}
          commandCatalog={commandCatalog}
          slashCommands={slashCommands}
          pendingApprovals={pendingApprovals}
          actionMessage={actionMessage}
          realtimeStatus={realtimeStatus}
          timeline={timeline}
          onRunCommand={async (command, args = {}) => {
            if (!accessToken) return;
            try {
              const action = await createCodexAction(accessToken, {
                command_id: command.id,
                arguments: args,
                project: activeProject?.id,
                device: activeDevice?.id,
                session: session?.id
              });
              setPendingApprovals((current) => [action, ...current.filter((item) => item.id !== action.id)]);
              setActionMessage(action.status === "pending" ? `${command.label}: awaiting approval.` : `${command.label}: sent.`);
            } catch {
            }
          }}
          onApprovalDecision={handleApprovalDecision}
          onRefreshCapabilities={handleRefreshCapabilities}
          onRefreshWorkspace={loadBootstrap}
          onPairing={() => { setHubSection(null); setSettingsSection("devices"); setSettingsOpen(true); }}
          onSelectProject={handleSelectProject}
          onSignOut={signOut}
        />
      ) : null}

      <AppSettingsModal
        visible={settingsOpen}
        section={settingsSection}
        accessToken={accessToken}
        devices={devices}
        projects={projects}
        activeDevice={activeDevice}
        capabilities={capabilities}
        actionMessage={actionMessage}
        sandboxDraft={sandboxDraft}
        approvalPolicyDraft={approvalPolicyDraft}
        webSearchDraft={webSearchDraft}
        planModeDraft={planModeDraft}
        onClose={() => setSettingsOpen(false)}
        onSectionChange={setSettingsSection}
        onRefreshWorkspace={loadBootstrap}
        onRefreshCapabilities={handleRefreshCapabilities}
        onMobileLogout={signOut}
        onCodexLogout={async () => {
          if (!accessToken) return;
          try {
            const action = await createCodexAction(accessToken, {
              command_id: "codex.logout",
              arguments: {},
              project: activeProject?.id,
              device: activeDevice?.id,
              session: session?.id
            });
            setPendingApprovals((current) => [action, ...current.filter((item) => item.id !== action.id)]);
            setActionMessage("Codex logout sent.");
          } catch {
          }
        }}
        onOpenDebug={() => { setSettingsOpen(false); setHubSection("debug"); }}
        onSandboxChange={setSandboxDraft}
        onApprovalPolicyChange={setApprovalPolicyDraft}
        onWebSearchChange={setWebSearchDraft}
        onPlanModeChange={handleTogglePlanMode}
        onSaveSafety={handleSaveSettings}
      />
      <TerminalSheet
        visible={terminalOpen}
        token={accessToken}
        project={activeProject}
        onClose={() => setTerminalOpen(false)}
        onNeedSetup={() => {
          setTerminalOpen(false);
          setSettingsSection("devices");
          setSettingsOpen(true);
        }}
      />
    </SafeAreaView>
  );
}

function EmptyPane({ hasDevices, onConnect, onRefresh, t }: { hasDevices: boolean; onConnect: () => void; onRefresh: () => void; t: (key: any) => string }) {
  return (
    <View style={styles.centerPane}>
      <View style={styles.emptyLogo}><Terminal size={26} color={C.tx1} /></View>
      <Text style={styles.emptyTitle}>{hasDevices ? t("chat.addWorkspace") : t("chat.connectCli")}</Text>
      <Text style={styles.emptyBody}>{hasDevices ? t("chat.noProjectBody") : t("chat.noCliBody")}</Text>
      <View style={styles.emptyActions}>
        <Pressable style={styles.emptyPrimary} onPress={onConnect}>
          <Text style={styles.emptyPrimaryText}>{hasDevices ? "Add project" : "Connect CLI"}</Text>
        </Pressable>
        <Pressable style={styles.emptySecondary} onPress={onRefresh}>
          <RefreshCw size={14} color={C.tx1} />
          <Text style={styles.emptySecondaryText}>Refresh</Text>
        </Pressable>
      </View>
      <View style={styles.cmdBox}>
        <Text style={styles.cmdText}>devlink pair --force --code CODE --name "Laptop"</Text>
        <Text style={styles.cmdText}>devlink projects add --path C:\path\to\repo</Text>
        <Text style={styles.cmdText}>devlink connect</Text>
      </View>
    </View>
  );
}

function TimelineRow({ item, expanded, onToggle }: { item: TimelineItem; expanded: boolean; onToggle: () => void }) {
  if (item.kind === "user_message") {
    return (
      <View style={styles.userRow}>
        <Text style={styles.userBubble}>{item.content}</Text>
      </View>
    );
  }
  if (item.kind === "assistant_message" || item.kind === "assistant_preview" || item.kind === "final") {
    return (
      <View style={styles.assistantRow}>
        <View style={styles.assistantAvatar}><Text style={styles.assistantAvatarText}>DL</Text></View>
        <View style={{ flex: 1 }}>
          <AssistantBox content={item.content || payloadPreview(item.payload)} isFinal={item.kind === "final"} expanded={expanded} onToggle={onToggle} />
        </View>
      </View>
    );
  }
  return null;
}

function AssistantBox({ content, isFinal, expanded, onToggle }: { content: string; isFinal: boolean; expanded: boolean; onToggle: () => void }) {
  const plan = stripPlanTags(content);
  const text = plan.content;
  const isLong = isFinal && (text.length > LONG_FINAL_CHAR || text.split(/\r?\n/).length > LONG_FINAL_LINES);
  const lines = text.split(/\r?\n/).length;

  if (plan.isPlan) {
    return (
      <View style={styles.planBox}>
        <View style={styles.planBoxHeader}>
          <Text style={styles.planBoxLabel}>PLAN</Text>
          <Text style={styles.planBoxMeta}>{lines} lines</Text>
        </View>
        <MarkdownMsg content={text} />
      </View>
    );
  }

  if (isLong) {
    return (
      <View style={styles.finalBox}>
        <View style={styles.finalBoxHeader}>
          <View>
            <Text style={styles.finalBoxLabel}>Final answer</Text>
            <Text style={styles.finalBoxMeta}>{text.length.toLocaleString()} chars · {lines} lines</Text>
          </View>
          <Pressable style={styles.finalBoxToggle} onPress={onToggle}>
            <Text style={styles.finalBoxToggleText}>{expanded ? "Collapse" : "Expand"}</Text>
          </Pressable>
        </View>
        <ScrollView style={[styles.finalBoxScroll, expanded && styles.finalBoxScrollExp]} nestedScrollEnabled>
          <MarkdownMsg content={text} />
        </ScrollView>
      </View>
    );
  }

  return <MarkdownMsg content={text} />;
}

function MarkdownMsg({ content }: { content: string }) {
  return <Markdown style={markdownStyles} mergeStyle>{content}</Markdown>;
}

function RunLogGroup({ entry, expanded, onToggle }: { entry: Extract<TimelineEntry, { type: "run_log" }>; expanded: boolean; onToggle: () => void }) {
  const latest = entry.items[entry.items.length - 1];
  const severity = runLogSeverity(entry);
  const label = severity === "fatal" ? "Run failed" : latest?.kind === "diff" ? runLogPreviewText(latest) : entry.completed ? "Completed run" : kindLabel(latest?.kind || "running");
  return (
    <View style={[styles.runLog, severity === "fatal" && styles.runLogFatal]}>
      <Pressable style={styles.runLogHead} onPress={onToggle}>
        <Terminal size={13} color={severity === "fatal" ? "#fca5a5" : C.tx2} />
        <Text style={[styles.runLogTitle, severity === "fatal" && { color: "#fca5a5" }]}>{label}</Text>
        <View style={styles.runLogBadge}><Text style={styles.runLogBadgeText}>{entry.items.length}</Text></View>
        <ChevronDown size={13} color={C.tx3} style={expanded ? { transform: [{ rotate: "180deg" }] } : undefined} />
      </Pressable>
      {expanded ? (
        <ScrollView style={styles.runLogBody} nestedScrollEnabled>
          {entry.items.map((item) => (
            <RunLogLine key={item.id} item={item} />
          ))}
        </ScrollView>
      ) : latest ? (
        <Text style={styles.runLogPreview} numberOfLines={2}>{runLogPreviewText(latest)}</Text>
      ) : null}
    </View>
  );
}

function RunLogLine({ item }: { item: TimelineItem }) {
  if (item.kind === "diff") {
    const info = fileEditInfo(item);
    return (
      <View style={[styles.runLogLine, styles.editRunLogLine]}>
        <View style={styles.editLineTop}>
          <Pencil size={13} color={C.tx2} />
          <Text style={styles.editVerb}>Editing</Text>
          <Text style={styles.editFile} numberOfLines={1}>{info.fileName}</Text>
          {info.countsKnown ? (
            <>
              <Text style={styles.editAdd}>+{info.additions}</Text>
              <Text style={styles.editDel}>-{info.deletions}</Text>
            </>
          ) : (
            <Text style={styles.editPending}>lines pending</Text>
          )}
        </View>
        {info.files.length > 1 ? (
          <View style={styles.editFilesList}>
            {info.files.slice(1, 4).map((file) => (
              <View key={file.filePath} style={styles.editSubRow}>
                <Text style={styles.editSubFile} numberOfLines={1}>{file.fileName}</Text>
                {file.countsKnown ? (
                  <>
                    <Text style={styles.editSubAdd}>+{file.additions}</Text>
                    <Text style={styles.editSubDel}>-{file.deletions}</Text>
                  </>
                ) : (
                  <Text style={styles.editSubPending}>pending</Text>
                )}
              </View>
            ))}
          </View>
        ) : null}
      </View>
    );
  }
  return (
    <View style={styles.runLogLine}>
      <Text style={styles.runLogLineKind}>{kindLabel(item.kind)}</Text>
      <Text style={[styles.runLogLineText, runLogTextStyle(item)]}>
        {item.content || payloadPreview(item.payload)}
      </Text>
    </View>
  );
}

function DrawerSection({ label, children, collapsible, expanded, onToggle }: {
  label: string;
  children: ReactNode;
  collapsible?: boolean;
  expanded?: boolean;
  onToggle?: () => void;
}) {
  return (
    <View style={styles.drawerSection}>
      <Pressable style={styles.drawerSectionHead} onPress={collapsible ? onToggle : undefined} disabled={!collapsible}>
        <Text style={styles.drawerSectionLabel}>{label}</Text>
        {collapsible ? <ChevronDown size={13} color={C.tx3} style={expanded ? { transform: [{ rotate: "180deg" }] } : undefined} /> : null}
      </Pressable>
      {(!collapsible || expanded) ? children : null}
    </View>
  );
}

function DrawerItem({ label, icon, trailing, active, onPress }: { label: string; icon?: ReactNode; trailing?: ReactNode; active?: boolean; onPress?: () => void }) {
  return (
    <Pressable style={[styles.drawerItem, active && styles.drawerItemActive]} onPress={onPress}>
      {icon ? <View style={styles.drawerItemIcon}>{icon}</View> : null}
      <Text style={[styles.drawerItemLabel, active && styles.drawerItemLabelActive]} numberOfLines={1}>{label}</Text>
      {trailing ? <View style={styles.drawerItemTrailing}>{trailing}</View> : null}
    </Pressable>
  );
}

function DrawerUsageCard({ stats, expanded, now, onToggle }: { stats: LimitUsageStats; expanded: boolean; now: number; onToggle: () => void }) {
  return (
    <View style={styles.usageCard}>
      <Pressable style={styles.usageCardHead} onPress={onToggle}>
        <BarChart2 size={15} color={C.tx2} />
        <Text style={styles.usageCardTitle}>Usage</Text>
        <View style={{ flex: 1 }} />
        {stats.hasTelemetry ? <Text style={styles.usageCardSummary}>{usageRemainingLabel(stats.fiveHour)} left</Text> : null}
        <ChevronDown size={13} color={C.tx3} style={expanded ? { transform: [{ rotate: "180deg" }] } : undefined} />
      </Pressable>
      {expanded ? (
        <View style={styles.usageRows}>
          {stats.hasTelemetry ? (
            <>
              <UsageRow label="5h" usage={stats.fiveHour} now={now} />
              <UsageRow label="Weekly" usage={stats.weekly} now={now} />
              {stats.source ? <Text style={styles.usageSource}>source: {stats.source}</Text> : null}
            </>
          ) : (
            <Text style={styles.drawerMuted}>{stats.error || "No usage data yet — run a task first."}</Text>
          )}
        </View>
      ) : null}
    </View>
  );
}

function UsageRow({ label, usage, now }: { label: string; usage: LimitUsage; now: number }) {
  const remaining = usageRemainingPercent(usage);
  const reset = usageResetLabel(usage, now);
  return (
    <View style={styles.usageRow}>
      <Text style={styles.usageRowLabel}>{label}</Text>
      <View style={styles.usageBar}>
        <View style={[styles.usageBarFill, { width: `${remaining ?? 100}%`, backgroundColor: (remaining ?? 100) < 15 ? C.ac3 : (remaining ?? 100) < 40 ? C.ac2 : C.ac1 }]} />
      </View>
      <Text style={styles.usageRowRight}>{usageRemainingLabel(usage)}</Text>
      <Text style={styles.usageReset}>{reset}</Text>
    </View>
  );
}

function PopupItem({ icon, label, trailing, onPress }: { icon: ReactNode; label: string; trailing?: ReactNode; onPress: () => void }) {
  return (
    <Pressable style={styles.popupItem} onPress={onPress}>
      {icon}
      <Text style={styles.popupItemLabel}>{label}</Text>
      {trailing}
    </Pressable>
  );
}

type TaskState = {
  taskId: string;
  status: string;
  sequence: number;
  createdAt: string;
  index: number;
};

function latestActiveTaskState(items: TimelineItem[]) {
  return latestTaskState(items, ACTIVE_TASK_STATUSES);
}

function latestTaskState(items: TimelineItem[], allowedStatuses?: Set<string>) {
  const latestByTask = new Map<string, TaskState>();
  items.forEach((item, index) => {
    if (!item.task_id) return;
    const status = taskStatusFromTimelineItem(item);
    if (!status) return;
    const state = {
      taskId: item.task_id,
      status,
      sequence: Number(item.sequence || 0),
      createdAt: item.created_at || "",
      index,
    };
    const current = latestByTask.get(item.task_id);
    if (!current || compareTaskState(state, current) > 0) {
      latestByTask.set(item.task_id, state);
    }
  });

  const candidates = [...latestByTask.values()].filter((state) => !allowedStatuses || allowedStatuses.has(state.status));
  candidates.sort(compareTaskState);
  return candidates.length > 0 ? candidates[candidates.length - 1] : null;
}

function taskStatusFromTimelineItem(item: TimelineItem) {
  const payload = item.payload || {};
  const explicit = String(payload.status || payload.to || payload.task_status || "").toLowerCase().trim();
  if (explicit) return explicit;
  if (item.kind === "queued") return "queued";
  if (item.kind === "running") return "running";
  return "";
}

function compareTaskState(a: TaskState, b: TaskState) {
  if (a.sequence !== b.sequence) return a.sequence - b.sequence;
  const timeCompare = a.createdAt.localeCompare(b.createdAt);
  if (timeCompare !== 0) return timeCompare;
  return a.index - b.index;
}

function skillIdentity(skill: SkillCapability) {
  return String(skill.id || skill.name || skill.path || "").trim();
}

function buildSkillRows(skills: SkillCapability[]) {
  const seen = new Map<string, number>();
  return skills.map((skill, index) => {
    const base = skillRenderKeyBase(skill) || `skill#${index}`;
    const seenCount = seen.get(base) || 0;
    seen.set(base, seenCount + 1);
    return {
      skill,
      renderKey: seenCount === 0 ? base : `${base}#dup${seenCount}`,
    };
  });
}

function skillRenderKeyBase(skill: SkillCapability) {
  const base = [skill.source, skill.path, skill.id, skill.name]
    .map((part) => String(part || "").trim())
    .filter(Boolean)
    .join("::");
  return base;
}

function CodexHubModal({
  section,
  onClose,
  projects,
  activeProject,
  capabilities,
  commandCatalog,
  slashCommands,
  pendingApprovals,
  actionMessage,
  onRunCommand,
  onApprovalDecision,
  onRefreshCapabilities,
  onRefreshWorkspace,
  onPairing,
  onSelectProject
}: {
  section: string;
  onClose: () => void;
  projects: Project[];
  activeProject: Project | null;
  devices: Device[];
  activeDevice: Device | null;
  capabilities: DeviceCapabilities["capabilities"];
  commandCatalog: CodexCommandDefinition[];
  slashCommands: Array<{ id: string; name: string; group: string; description: string }>;
  pendingApprovals: ApprovalRequest[];
  actionMessage: string;
  onRunCommand: (command: CodexCommandDefinition, args?: Record<string, unknown>) => void;
  onApprovalDecision: (id: string, decision: "approve" | "reject") => void;
  onRefreshCapabilities: () => void;
  onRefreshWorkspace: () => void;
  onPairing: () => void;
  onSelectProject: (id: string) => void;
  onSignOut: () => void;
}) {
  const skills = capabilities.skills || [];
  const installedPlugins = capabilities.installed_plugins || capabilities.plugins || [];
  const marketplaces = capabilities.plugin_marketplaces || [];
  const mcpServers = capabilities.mcp_servers || [];
  const features = capabilities.features || [];
  const profiles = capabilities.profiles || [];
  const gitState = activeProject ? capabilities.project_git?.[activeProject.id] : undefined;
  const [expandedCommand, setExpandedCommand] = useState<string | null>(null);
  const [commandArgs, setCommandArgs] = useState<Record<string, Record<string, unknown>>>({});

  const commands = commandCatalog.filter((command) => (section === "commands" ? true : command.group === section));

  function updateArg(commandId: string, name: string, value: unknown) {
    setCommandArgs((current) => ({ ...current, [commandId]: { ...(current[commandId] || {}), [name]: value } }));
  }

  const sectionIcons: Record<string, ReactNode> = {
    workspace: <Layers size={18} color={C.tx0} />,
    commands: <Command size={18} color={C.tx0} />,
    plugins: <Package size={18} color={C.tx0} />,
    mcp: <Server size={18} color={C.tx0} />,
    git: <GitBranch size={18} color={C.tx0} />,
    debug: <Bug size={18} color={C.tx0} />
  };

  const sectionTitles: Record<string, string> = {
    workspace: "Projects",
    commands: "Commands",
    plugins: "Plugins",
    mcp: "MCP Servers",
    git: "Git",
    debug: "Debug"
  };

  return (
    <Modal visible animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={styles.hubRoot}>
        <View style={styles.hubHeader}>
          <View style={styles.hubHeaderIcon}>{sectionIcons[section] || <Terminal size={18} color={C.tx0} />}</View>
          <Text style={styles.hubTitle}>{sectionTitles[section] || section}</Text>
          <View style={{ flex: 1 }} />
          <Pressable hitSlop={10} onPress={onClose} style={styles.hubCloseBtn}>
            <X size={18} color={C.tx1} />
          </Pressable>
        </View>

        {actionMessage ? <View style={styles.hubBanner}><Text style={styles.hubBannerText}>{actionMessage}</Text></View> : null}

        <ScrollView contentContainerStyle={styles.hubContent} showsVerticalScrollIndicator={false}>
          {section === "workspace" ? (
            <>
              <HubAction label="Refresh workspaces" icon={<RefreshCw size={14} color={C.tx0} />} onPress={onRefreshWorkspace} />
              <HubAction label="Pairing / Devices" icon={<Settings size={14} color={C.tx0} />} onPress={onPairing} />
              <HubSectionTitle label="Projects" />
              {projects.length === 0 ? <Text style={styles.hubMuted}>No projects. Add one with devlink projects add --path.</Text> : null}
              {projects.map((project) => (
                <Pressable key={project.id} style={[styles.hubProjectRow, project.id === activeProject?.id && styles.hubProjectRowActive]} onPress={() => onSelectProject(project.id)}>
                  <View style={styles.hubProjectLeft}>
                    <GitBranch size={15} color={project.id === activeProject?.id ? C.ac1 : C.tx2} />
                    <View>
                      <Text style={styles.hubProjectName}>{project.name}</Text>
                      <Text style={styles.hubProjectPath} numberOfLines={1}>{project.local_path}</Text>
                    </View>
                  </View>
                  {project.id === activeProject?.id ? <Check size={15} color={C.ac1} /> : null}
                </Pressable>
              ))}
              {profiles.length > 0 ? (
                <>
                  <HubSectionTitle label="Profiles" />
                  {profiles.map((profile) => <HubInfoRow key={profile} label={profile} value="config.toml" />)}
                </>
              ) : null}
            </>
          ) : null}

          {section === "plugins" ? (
            <>
              <HubSectionTitle label={`Marketplaces (${marketplaces.length})`} />
              {marketplaces.length === 0 ? <Text style={styles.hubMuted}>No marketplaces cached.</Text> : null}
              {marketplaces.map((marketplace) => <HubInfoRow key={marketplace.id} label={marketplace.name} value={marketplace.path || "installed"} />)}
              <HubSectionTitle label={`Installed plugins (${installedPlugins.length})`} />
              {installedPlugins.length === 0 ? <Text style={styles.hubMuted}>No plugins detected.</Text> : null}
              {installedPlugins.map((plugin) => <HubInfoRow key={plugin.id} label={plugin.name} value={plugin.marketplace || plugin.path || "installed"} />)}
              <HubSectionTitle label={`Plugin skills (${skills.filter((skill) => skill.source === "plugin").length})`} />
              {skills.filter((skill) => skill.source === "plugin").map((skill) => <HubInfoRow key={skill.id} label={skill.name} value={skill.description || "plugin skill"} />)}
            </>
          ) : null}

          {section === "mcp" ? (
            <>
              <HubSectionTitle label={`Servers (${mcpServers.length})`} />
              {mcpServers.length === 0 ? <Text style={styles.hubMuted}>No MCP servers configured.</Text> : null}
              {mcpServers.map((server: any) => <HubInfoRow key={server.name || server.id} label={server.name || server.id} value={server.auth_status || server.transport?.type || "configured"} />)}
            </>
          ) : null}

          {section === "git" ? (
            <>
              <HubInfoRow label="Branch" value={gitState?.branch || "—"} />
              <HubInfoRow label="Dirty" value={gitState?.dirty ? "yes" : "no"} />
              <HubInfoRow label="Upstream" value={gitState?.upstream || "—"} />
              <HubInfoRow label="Project" value={activeProject?.name || "none"} />
            </>
          ) : null}

          {section === "debug" ? (
            <>
              <HubAction label="Refresh capabilities" icon={<RefreshCw size={14} color={C.tx0} />} onPress={onRefreshCapabilities} />
              <HubSectionTitle label="Inventory" />
              <HubInfoRow label="Skills" value={String(skills.length)} />
              <HubInfoRow label="Plugins" value={String(installedPlugins.length)} />
              <HubInfoRow label="Marketplaces" value={String(marketplaces.length)} />
              <HubInfoRow label="MCP" value={String(mcpServers.length)} />
              {features.length > 0 ? (
                <>
                  <HubSectionTitle label="Features" />
                  {features.map((feature: any) => <HubInfoRow key={feature.id} label={feature.id} value={feature.enabled === null ? feature.maturity : feature.enabled ? "on" : "off"} />)}
                </>
              ) : null}
              <HubSectionTitle label="Diagnostics" />
              {Object.entries(capabilities.diagnostics || {}).map(([key, value]) => <HubInfoRow key={key} label={key} value={String(value)} />)}
            </>
          ) : null}

          {commands.length > 0 ? (
            <>
              <HubSectionTitle label="Commands" />
              {commands.map((command) => (
                <View key={command.id} style={styles.hubCmdCard}>
                  <View style={styles.hubCmdTop}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.hubCmdLabel}>{command.label}</Text>
                      <Text style={styles.hubCmdMeta}>{command.id}</Text>
                      {command.description ? <Text style={styles.hubCmdDesc}>{command.description}</Text> : null}
                    </View>
                    <View style={styles.hubCmdActions}>
                      {command.args_schema.length > 0 ? (
                        <Pressable style={styles.hubCmdConfigure} onPress={() => setExpandedCommand(expandedCommand === command.id ? null : command.id)}>
                          <Settings size={13} color={C.tx1} />
                        </Pressable>
                      ) : null}
                      <Pressable style={[styles.hubCmdRun, command.risk_level === "high" && styles.hubCmdRunDanger]} onPress={() => onRunCommand(command, commandArgs[command.id] || {})}>
                        <Text style={styles.hubCmdRunText}>{command.requires_approval ? "Request" : "Run"}</Text>
                      </Pressable>
                    </View>
                  </View>
                  {expandedCommand === command.id ? (
                    <CmdArgsForm command={command} values={commandArgs[command.id] || {}} onChange={(name, value) => updateArg(command.id, name, value)} />
                  ) : null}
                </View>
              ))}
            </>
          ) : null}

          {section === "commands" && slashCommands.length > 0 ? (
            <>
              <HubSectionTitle label="Slash commands" />
              {slashCommands.map((command) => <HubInfoRow key={command.id} label={`/${command.name}`} value={command.description} />)}
            </>
          ) : null}

          {pendingApprovals.length > 0 ? (
            <>
              <HubSectionTitle label={`Approvals (${pendingApprovals.filter((item) => item.status === "pending").length} pending)`} />
              {pendingApprovals.map((approval) => (
                <View key={approval.id} style={styles.hubApproval}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.hubApprovalCmd}>{approval.command_id || approval.action_type}</Text>
                    <Text style={styles.hubApprovalMeta}>{approval.status} · {approval.risk_level}</Text>
                  </View>
                  {approval.status === "pending" ? (
                    <View style={styles.hubApprovalBtns}>
                      <Pressable style={styles.approveBtn} onPress={() => onApprovalDecision(approval.id, "approve")}><Check size={14} color="#fff" /></Pressable>
                      <Pressable style={styles.rejectBtn} onPress={() => onApprovalDecision(approval.id, "reject")}><X size={14} color="#fff" /></Pressable>
                    </View>
                  ) : null}
                </View>
              ))}
            </>
          ) : null}
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

function HubSectionTitle({ label }: { label: string }) {
  return <Text style={styles.hubSectionTitle}>{label}</Text>;
}

function HubInfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.hubInfoRow}>
      <Text style={styles.hubInfoLabel}>{label}</Text>
      <Text style={styles.hubInfoValue} numberOfLines={2}>{value}</Text>
    </View>
  );
}

function HubAction({ label, icon, onPress }: { label: string; icon: ReactNode; onPress: () => void }) {
  return (
    <Pressable style={styles.hubAction} onPress={onPress}>
      {icon}
      <Text style={styles.hubActionText}>{label}</Text>
      <ChevronRight size={14} color={C.tx3} />
    </Pressable>
  );
}

function CmdArgsForm({ command, values, onChange }: { command: CodexCommandDefinition; values: Record<string, unknown>; onChange: (name: string, value: unknown) => void }) {
  return (
    <View style={styles.cmdForm}>
      {command.args_schema.map((arg) => {
        const value = values[arg.name];
        if (arg.type === "boolean") {
          return (
            <View key={arg.name} style={styles.cmdSwitchRow}>
              <Text style={styles.cmdArgLabel}>{arg.name}</Text>
              <Switch value={Boolean(value)} onValueChange={(nextValue) => onChange(arg.name, nextValue)} trackColor={{ true: C.ac1 }} />
            </View>
          );
        }
        if (arg.type === "choice" && Array.isArray(arg.choices)) {
          return (
            <View key={arg.name} style={styles.cmdArgBlock}>
              <Text style={styles.cmdArgLabel}>{arg.name}{arg.required ? " *" : ""}</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingVertical: 4 }}>
                {arg.choices.map((choice) => (
                  <Pressable key={choice} style={[styles.filterChip, value === choice && styles.filterChipActive]} onPress={() => onChange(arg.name, choice)}>
                    <Text style={[styles.filterChipText, value === choice && styles.filterChipTextActive]}>{choice}</Text>
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          );
        }
        return (
          <View key={arg.name} style={styles.cmdArgBlock}>
            <Text style={styles.cmdArgLabel}>{arg.name}{arg.required ? " *" : ""}</Text>
            <TextInput
              style={styles.cmdArgInput}
              placeholder={arg.placeholder || arg.name}
              placeholderTextColor={C.tx2}
              value={String(value || "")}
              onChangeText={(text) => onChange(arg.name, text)}
            />
          </View>
        );
      })}
    </View>
  );
}

function groupTimelineForChat(items: TimelineItem[]): TimelineEntry[] {
  const entries: TimelineEntry[] = [];
  const groups = new Map<string, Extract<TimelineEntry, { type: "run_log" }>>();
  const completedTasks = new Set<string>();
  const assistantMessageTasks = new Set<string>();
  const assistantPreviewTasks = new Set<string>();
  items.forEach((item) => {
    if (item.kind === "assistant_message" && item.task_id) assistantMessageTasks.add(item.task_id);
    if (item.kind === "assistant_preview" && item.task_id) assistantPreviewTasks.add(item.task_id);
  });
  items.forEach((item) => {
    if (!item.task_id) return;
    const status = String(item.payload?.status || item.payload?.to || "").toLowerCase();
    if (item.kind === "final" || TERMINAL_TASK_STATUSES.has(status)) completedTasks.add(item.task_id);
  });
  items.forEach((item) => {
    if (item.kind === "usage_limits") return;
    if (item.kind === "assistant_preview" && item.task_id && assistantMessageTasks.has(item.task_id)) return;
    if (item.kind === "final" && item.task_id && (assistantMessageTasks.has(item.task_id) || assistantPreviewTasks.has(item.task_id))) return;
    if (item.task_id && assistantMessageTasks.has(item.task_id) && isAssistantOutputLog(item)) return;
    if (isRunLogKind(item.kind)) {
      const id = `rl-${item.task_id || "session"}`;
      let group = groups.get(id);
      if (!group) {
        const taskId = item.task_id || "session";
        group = {
          type: "run_log",
          id,
          taskId,
          items: [],
          completed: completedTasks.has(taskId),
          hasAssistantMessage: assistantMessageTasks.has(taskId),
        };
        groups.set(id, group);
        entries.push(group);
      }
      group.items.push(item);
      group.completed = group.completed || completedTasks.has(item.task_id || "");
      group.hasAssistantMessage = group.hasAssistantMessage || assistantMessageTasks.has(item.task_id || "");
      return;
    }
    entries.push({ type: "item", id: item.id, item });
  });

  // Keep active run logs pinned at the bottom to avoid UI "jumping" as new events arrive.
  // Completed run logs stay in the normal flow.
  const head: TimelineEntry[] = [];
  const tail: TimelineEntry[] = [];
  entries.forEach((entry) => {
    if (entry.type === "run_log" && !entry.completed) tail.push(entry);
    else head.push(entry);
  });
  return head.concat(tail);
}

function isRunLogKind(kind: TimelineItem["kind"]) {
  return !["user_message", "assistant_message", "assistant_preview", "final", "usage_limits"].includes(kind);
}

function isAssistantOutputLog(item: TimelineItem) {
  const payload = item.payload || {};
  const nestedItem = payload.item && typeof payload.item === "object" ? payload.item as Record<string, unknown> : {};
  return (
    String(payload.type || payload.raw_type || "").toLowerCase() === "item.completed" &&
    String(nestedItem.type || "").toLowerCase() === "agent_message"
  );
}

function runLogSeverity(entry: Extract<TimelineEntry, { type: "run_log" }>) {
  if (entry.items.some(isFatalItem)) return "fatal";
  if (entry.items.some((item) => item.kind === "warning" || item.kind === "terminal_stderr")) return "warning";
  return "neutral";
}

function isFatalItem(item: TimelineItem) {
  const payload = item.payload || {};
  const status = String(payload.status || payload.to || "").toLowerCase();
  if (["failed", "timed_out", "canceled"].includes(status)) return true;
  if (item.kind === "error" && String(payload.level || "").toLowerCase() !== "warning") return true;
  const message = `${item.content || ""} ${JSON.stringify(payload)}`.toLowerCase();
  return /token_not_valid|unauthorized|quota|rate.?limit|context length|out of credits/.test(message);
}

function runLogTextStyle(item: TimelineItem) {
  if (isFatalItem(item)) return { color: "#fca5a5" };
  if (item.kind === "warning" || item.kind === "terminal_stderr") return { color: "#fcd34d" };
  return undefined;
}

type FileEditLine = {
  filePath: string;
  fileName: string;
  additions: number;
  deletions: number;
  countsKnown: boolean;
};

function fileEditInfo(item: TimelineItem): { fileName: string; additions: number; deletions: number; countsKnown: boolean; files: FileEditLine[] } {
  const payload = item.payload || {};
  const rawFiles = Array.isArray(payload.files) ? payload.files : [];
  const files = rawFiles
    .map((raw) => fileEditLineFromPayload(raw))
    .filter((file): file is FileEditLine => Boolean(file));
  const direct = fileEditLineFromPayload(payload);
  const allFiles = files.length > 0 ? files : direct ? [direct] : [];
  const additions = numberFromPayload(payload.additions) ?? allFiles.reduce((sum, file) => sum + file.additions, 0);
  const deletions = numberFromPayload(payload.deletions) ?? allFiles.reduce((sum, file) => sum + file.deletions, 0);
  const first = allFiles[0] || {
    filePath: stringFromPayload(payload.file_path) || stringFromPayload(payload.path) || item.content || "file",
    fileName: stringFromPayload(payload.file_name) || "file",
    additions,
    deletions,
    countsKnown: boolFromPayload(payload.counts_known) ?? (numberFromPayload(payload.additions) !== undefined || numberFromPayload(payload.deletions) !== undefined)
  };
  const countsKnown = boolFromPayload(payload.counts_known) ?? allFiles.some((file) => file.countsKnown);
  return {
    fileName: first.fileName || basename(first.filePath),
    additions,
    deletions,
    countsKnown,
    files: allFiles.length > 0 ? allFiles : [first]
  };
}

function fileEditLineFromPayload(raw: unknown): FileEditLine | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const payload = raw as Record<string, unknown>;
  const filePath = stringFromPayload(payload.file_path) || stringFromPayload(payload.path) || stringFromPayload(payload.relative_path) || stringFromPayload(payload.filename);
  const fileName = stringFromPayload(payload.file_name) || basename(filePath);
  if (!filePath && !fileName) return null;
  return {
    filePath: filePath || fileName,
    fileName: fileName || filePath,
    additions: numberFromPayload(payload.additions) ?? numberFromPayload(payload.added) ?? 0,
    deletions: numberFromPayload(payload.deletions) ?? numberFromPayload(payload.deleted) ?? numberFromPayload(payload.removed) ?? 0,
    countsKnown: boolFromPayload(payload.counts_known) ?? (numberFromPayload(payload.additions) !== undefined || numberFromPayload(payload.deletions) !== undefined || numberFromPayload(payload.added) !== undefined || numberFromPayload(payload.deleted) !== undefined || numberFromPayload(payload.removed) !== undefined)
  };
}

function runLogPreviewText(item: TimelineItem) {
  if (item.kind !== "diff") return item.content || payloadPreview(item.payload);
  const info = fileEditInfo(item);
  if (!info.countsKnown) return `Editing ${info.fileName}`;
  return `Editing ${info.fileName} +${info.additions} -${info.deletions}`;
}

function stringFromPayload(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function numberFromPayload(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function boolFromPayload(value: unknown) {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true") return true;
    if (normalized === "false") return false;
  }
  return undefined;
}

function basename(path: string) {
  return path.replace(/\\/g, "/").split("/").filter(Boolean).pop() || path;
}

function kindLabel(kind: TimelineItem["kind"]) {
  const map: Partial<Record<TimelineItem["kind"], string>> = {
    queued: "Queued",
    running: "Running",
    thinking: "Thinking",
    reasoning_summary: "Reasoning...",
    tool_call: "Tool",
    command: "Command",
    terminal: "Terminal",
    terminal_stdout: "Output",
    terminal_stderr: "Stderr",
    diff: "Editing",
    warning: "Warning",
    approval: "Approval",
    error: "Error"
  };
  return map[kind] || kind;
}

function stripPlanTags(content: string) {
  const match = content.match(/<proposed_plan>\s*([\s\S]*?)\s*<\/proposed_plan>/i);
  return match ? { isPlan: true, content: match[1].trim() } : { isPlan: false, content };
}

function statusColor(status: "connected" | "reconnecting" | "polling" | "disconnected") {
  return { connected: "#10b981", reconnecting: "#f59e0b", polling: "#60a5fa", disconnected: "#6b7280" }[status];
}

function statusLabel(status: "connected" | "reconnecting" | "polling" | "disconnected") {
  return { connected: "Live", reconnecting: "Reconnecting", polling: "Polling", disconnected: "Offline" }[status];
}

function shortModelName(id: string) {
  return id.split("/").pop()?.slice(0, 20) || id.slice(0, 20);
}

function modelIdFromCapability(model: unknown) {
  if (typeof model === "string") return model;
  if (model && typeof model === "object" && "id" in model) return String((model as any).id || "");
  return "";
}

function firstString(...values: unknown[]) {
  for (const value of values) if (typeof value === "string" && value.trim()) return value.trim();
  return "";
}

function payloadPreview(payload: Record<string, unknown>) {
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return "";
  }
}

function currentFileMentionQuery(text: string) {
  const match = text.match(/(?:^|\s)@([^\s@]*)$/);
  return match ? match[1] : null;
}

function replaceCurrentFileMention(text: string, path: string) {
  return text.replace(/(?:^|\s)@([^\s@]*)$/, (match) => `${match.startsWith(" ") ? " " : ""}@${path} `);
}

function fileMatchesMentionQuery(file: FileMention, query: string) {
  return `${file.relative_path} ${file.name}`.toLowerCase().includes(query);
}

function parseModelsRaw(raw: unknown) {
  if (typeof raw !== "string" || !raw.trim()) return [];
  try {
    const parsed = JSON.parse(raw) as { models?: Array<Record<string, unknown>> };
    if (!Array.isArray(parsed.models)) return [];
    return parsed.models
      .map((model) => ({
        id: String(model.slug || model.id || ""),
        name: String(model.display_name || model.name || model.id || ""),
        context_window: Number(model.context_window || 0),
        supported_reasoning_levels: Array.isArray(model.supported_reasoning_levels) ? model.supported_reasoning_levels : []
      }))
      .filter((model) => model.id);
  } catch {
    return [];
  }
}

function reasoningLevels(models: any[], modelId: string) {
  const model = (models || []).find((item: any) => modelIdFromCapability(item) === modelId) as any;
  const levels = model?.supported_reasoning_levels;
  if (Array.isArray(levels) && levels.length) {
    return levels.map((level: any) => (typeof level === "string" ? level : String(level.effort || level.id || ""))).filter(Boolean);
  }
  return ["Low", "Medium", "High"];
}

function buildLimitUsageStats(items: TimelineItem[], capabilities: DeviceCapabilities["capabilities"]): LimitUsageStats {
  const candidates = [statsFromLimits(capabilities.codex_usage_limits)];
  for (const item of items.slice(-120).reverse()) {
    candidates.push(statsFromLimits((item.payload || {}).codex_usage_limits));
  }
  const newest = candidates
    .filter((stats) => stats.hasTelemetry)
    .sort((a, b) => usageObservedTime(b) - usageObservedTime(a))[0];
  if (newest) return newest;
  return { fiveHour: { label: "5h" }, weekly: { label: "weekly" }, hasTelemetry: false, error: String((capabilities.diagnostics || {}).usage_limits_error || "") };
}

function statsFromLimits(value: unknown): LimitUsageStats {
  if (!value || typeof value !== "object") return { fiveHour: { label: "5h" }, weekly: { label: "weekly" }, hasTelemetry: false };
  const raw = value as Record<string, unknown>;
  const fiveHour = limitFromWindow(raw.five_hour, "5h");
  const weekly = limitFromWindow(raw.weekly, "weekly");
  const observedAt = str(raw.observed_at);
  return {
    fiveHour: withObservedAt(fiveHour || { label: "5h" }, observedAt),
    weekly: withObservedAt(weekly || { label: "weekly" }, observedAt),
    hasTelemetry: Boolean(fiveHour || weekly),
    source: str(raw.source),
    observedAt,
    stale: Boolean(raw.stale)
  };
}

function limitFromWindow(value: unknown, label: string): LimitUsage | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const raw = value as Record<string, unknown>;
  const usedPercent = num(raw.used_percent, raw.percent_used);
  const remainingPercent = num(raw.remaining_percent, raw.percent_remaining);
  const resetAt = str(raw.resets_at, raw.reset_at);
  if (usedPercent === undefined && remainingPercent === undefined && !resetAt) return null;
  return {
    label,
    percent: usedPercent !== undefined ? clamp(usedPercent) : remainingPercent !== undefined ? clamp(100 - remainingPercent) : undefined,
    resetAt: resetAt || undefined,
    source: str(raw.source),
    observedAt: str(raw.observed_at),
    windowMinutes: num(raw.window_minutes)
  };
}

function withObservedAt(usage: LimitUsage, observedAt: string) {
  return observedAt ? { ...usage, observedAt: usage.observedAt || observedAt } : usage;
}

function usageObservedTime(stats: LimitUsageStats) {
  const observed = stats.fiveHour.observedAt || stats.weekly.observedAt || "";
  const parsed = observed ? Date.parse(observed) : 0;
  return Number.isFinite(parsed) ? parsed : 0;
}

function usageRemainingPercent(usage: LimitUsage) {
  if (usage.percent !== undefined) return clamp(100 - usage.percent);
  if (usage.remaining !== undefined && usage.limit) return clamp((usage.remaining / usage.limit) * 100);
  return undefined;
}

function usageRemainingLabel(usage: LimitUsage) {
  const percent = usageRemainingPercent(usage);
  return percent !== undefined ? `${percent}%` : "—";
}

function usageResetLabel(usage: LimitUsage, now: number) {
  if (!usage.resetAt) return "--";
  const date = new Date(usage.resetAt);
  if (!Number.isFinite(date.getTime())) return "--";
  const diffMs = date.getTime() - now;
  if (diffMs > -60_000 && diffMs < 36 * 60 * 60 * 1000) {
    return date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
}

function num(...values: unknown[]): number | undefined {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string") {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return undefined;
}

function str(...values: unknown[]) {
  for (const value of values) if (typeof value === "string" && value.trim()) return value.trim();
  return "";
}

function clamp(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

const markdownStyles = StyleSheet.create({
  body: { color: C.tx0, fontSize: 15, lineHeight: 22 },
  paragraph: { marginTop: 0, marginBottom: 8 },
  heading1: { color: C.tx0, fontSize: 22, fontWeight: "700", marginBottom: 10 },
  heading2: { color: C.tx0, fontSize: 18, fontWeight: "700", marginBottom: 8 },
  heading3: { color: C.tx0, fontSize: 15, fontWeight: "700", marginBottom: 6 },
  strong: { color: C.tx0, fontWeight: "700" },
  em: { fontStyle: "italic" },
  link: { color: "#93c5fd", textDecorationLine: "underline" },
  bullet_list: { marginBottom: 8 },
  ordered_list: { marginBottom: 8 },
  list_item: { marginBottom: 4 },
  blockquote: { borderLeftWidth: 2, borderLeftColor: C.bd2, paddingLeft: 12, marginVertical: 8, opacity: 0.85 },
  code_inline: { color: "#e2e8f0", backgroundColor: C.bg3, borderRadius: 4, paddingHorizontal: 4, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace", fontSize: 13 },
  code_block: { color: "#e2e8f0", backgroundColor: C.bg1, borderRadius: 8, padding: 12, marginVertical: 8, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace", fontSize: 13 },
  fence: { color: "#e2e8f0", backgroundColor: C.bg1, borderRadius: 8, padding: 12, marginVertical: 8, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace", fontSize: 13 },
  text: { color: C.tx0 }
});

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg0 },
  fill: { flex: 1 },
  topBar: { flexDirection: "row", alignItems: "center", paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: C.bd0 },
  topBarCenter: { flex: 1, alignItems: "center", marginHorizontal: 8 },
  topBarTitle: { color: C.tx0, fontSize: 15, fontWeight: "600" },
  statusPill: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 3 },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusText: { color: C.tx2, fontSize: 11, fontWeight: "500" },
  iconBtn: { padding: 6, borderRadius: 8 },
  errorBar: { flexDirection: "row", alignItems: "center", backgroundColor: "#2d1515", paddingHorizontal: 14, paddingVertical: 10, gap: 8 },
  errorBarText: { color: "#fca5a5", flex: 1, fontSize: 13 },
  centerPane: { flex: 1, justifyContent: "center", alignItems: "center", padding: 32 },
  centerText: { color: C.tx2, marginTop: 10, fontSize: 14 },
  emptyLogo: { width: 56, height: 56, borderRadius: 28, backgroundColor: C.bg2, borderWidth: 1, borderColor: C.bd1, alignItems: "center", justifyContent: "center", marginBottom: 20 },
  emptyLogoText: { color: C.tx0, fontSize: 14, fontWeight: "800", letterSpacing: 0.5 },
  emptyTitle: { color: C.tx0, fontSize: 22, fontWeight: "600", textAlign: "center" },
  emptyHint: { color: C.tx2, fontSize: 14, marginTop: 6 },
  emptyBody: { color: C.tx1, fontSize: 14, textAlign: "center", lineHeight: 20, marginTop: 8, maxWidth: 320 },
  emptyActions: { flexDirection: "row", gap: 10, marginTop: 24 },
  emptyPrimary: { backgroundColor: C.tx0, borderRadius: 10, paddingHorizontal: 18, paddingVertical: 11 },
  emptyPrimaryText: { color: C.bg0, fontWeight: "700", fontSize: 14 },
  emptySecondary: { flexDirection: "row", alignItems: "center", gap: 6, borderWidth: 1, borderColor: C.bd2, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10 },
  emptySecondaryText: { color: C.tx1, fontSize: 14, fontWeight: "600" },
  cmdBox: { marginTop: 20, backgroundColor: C.bg1, borderRadius: 8, borderWidth: 1, borderColor: C.bd1, padding: 12, gap: 4 },
  cmdText: { color: C.tx2, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace", fontSize: 12 },
  timelineContent: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 40 },
  userRow: { alignItems: "flex-end", marginBottom: 20 },
  userBubble: { backgroundColor: C.bg3, color: C.tx0, paddingHorizontal: 16, paddingVertical: 12, borderRadius: 18, borderBottomRightRadius: 4, maxWidth: "85%", fontSize: 15, lineHeight: 22 },
  assistantRow: { flexDirection: "row", marginBottom: 20, gap: 10 },
  assistantAvatar: { width: 28, height: 28, borderRadius: 14, backgroundColor: C.bg3, borderWidth: 1, borderColor: C.bd1, alignItems: "center", justifyContent: "center", marginTop: 2 },
  assistantAvatarText: { color: C.tx0, fontSize: 9, fontWeight: "800" },
  planBox: { borderWidth: 1, borderColor: C.bd1, borderRadius: 10, backgroundColor: C.bg2, padding: 14 },
  planBoxHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
  planBoxLabel: { color: C.tx2, fontSize: 11, fontWeight: "800", letterSpacing: 1 },
  planBoxMeta: { color: C.tx3, fontSize: 12 },
  finalBox: { borderWidth: 1, borderColor: C.bd1, borderRadius: 10, backgroundColor: C.bg2, overflow: "hidden" },
  finalBoxHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: C.bd1 },
  finalBoxLabel: { color: C.tx0, fontSize: 13, fontWeight: "700" },
  finalBoxMeta: { color: C.tx2, fontSize: 11, marginTop: 2 },
  finalBoxToggle: { borderWidth: 1, borderColor: C.bd2, borderRadius: 99, paddingHorizontal: 10, paddingVertical: 5 },
  finalBoxToggleText: { color: C.tx1, fontSize: 12, fontWeight: "700" },
  finalBoxScroll: { maxHeight: 300, paddingHorizontal: 14, paddingTop: 10 },
  finalBoxScrollExp: { maxHeight: 640 },
  runLog: { marginLeft: 38, marginBottom: 14, backgroundColor: C.bg2, borderRadius: 10, borderWidth: 1, borderColor: C.bd1, overflow: "hidden" },
  runLogFatal: { backgroundColor: "#1e0a0a", borderColor: "#5a1414" },
  runLogHead: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingVertical: 10 },
  runLogTitle: { flex: 1, color: C.tx1, fontSize: 13, fontWeight: "600" },
  runLogBadge: { backgroundColor: C.bg3, borderRadius: 99, paddingHorizontal: 7, paddingVertical: 2 },
  runLogBadgeText: { color: C.tx2, fontSize: 11, fontWeight: "700" },
  runLogBody: { maxHeight: 200, borderTopWidth: 1, borderTopColor: C.bd0 },
  runLogLine: { paddingHorizontal: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: C.bd0 },
  runLogLineKind: { color: C.tx2, fontSize: 11, fontWeight: "700", marginBottom: 3, textTransform: "uppercase" },
  runLogLineText: { color: C.tx1, fontSize: 12, lineHeight: 17, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  runLogPreview: { paddingHorizontal: 12, paddingBottom: 10, color: C.tx2, fontSize: 12, lineHeight: 17 },
  editRunLogLine: { gap: 6 },
  editLineTop: { flexDirection: "row", alignItems: "center", gap: 7 },
  editVerb: { color: C.tx2, fontSize: 13, fontWeight: "600" },
  editFile: { flex: 1, color: "#93c5fd", fontSize: 13, fontWeight: "700" },
  editAdd: { color: C.ac1, fontSize: 13, fontWeight: "800", fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  editDel: { color: C.ac3, fontSize: 13, fontWeight: "800", fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  editPending: { color: C.tx3, fontSize: 12, fontWeight: "700" },
  editFilesList: { marginLeft: 20, gap: 3 },
  editSubRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  editSubFile: { flex: 1, color: C.tx2, fontSize: 12 },
  editSubAdd: { color: C.ac1, fontSize: 12, fontWeight: "700", fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  editSubDel: { color: C.ac3, fontSize: 12, fontWeight: "700", fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  editSubPending: { color: C.tx3, fontSize: 11, fontWeight: "700" },
  composerWrap: { paddingHorizontal: 12, paddingBottom: 8, paddingTop: 6, borderTopWidth: 1, borderTopColor: C.bd0 },
  chipsRow: { flexDirection: "row", marginBottom: 8, maxHeight: 28 },
  chip: { flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: C.bg3, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 99, marginRight: 6 },
  chipText: { color: C.tx1, fontSize: 12, maxWidth: 120 },
  composerBox: { flexDirection: "row", alignItems: "flex-end", backgroundColor: C.bg2, borderRadius: 16, borderWidth: 1, borderColor: C.bd1, paddingHorizontal: 6, paddingVertical: 6 },
  composerIconBtn: { padding: 8 },
  composerInput: { flex: 1, color: C.tx0, fontSize: 15, maxHeight: 120, paddingHorizontal: 6, paddingVertical: 6 },
  sendBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: C.tx0, alignItems: "center", justifyContent: "center", marginLeft: 4 },
  sendBtnOff: { backgroundColor: C.bg4 },
  stopBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: C.tx0, alignItems: "center", justifyContent: "center", marginLeft: 4 },
  toolbar: { flexDirection: "row", alignItems: "center", paddingTop: 8, gap: 4 },
  toolbarBtn: { flexDirection: "row", alignItems: "center", gap: 5, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 99 },
  toolbarBtnText: { color: C.tx2, fontSize: 12, fontWeight: "500", maxWidth: 120 },
  toolbarPill: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 99, borderWidth: 1, borderColor: C.bd2 },
  toolbarPillActive: { backgroundColor: C.tx0, borderColor: C.tx0 },
  toolbarPillText: { color: C.tx2, fontSize: 12, fontWeight: "600" },
  toolbarPillTextActive: { color: C.bg0 },
  terminalToolbarBtn: { width: 36, height: 32, borderRadius: 9, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: C.bd2, backgroundColor: C.bg2 },
  terminalToolbarBtnDisabled: { opacity: 0.45 },
  overlay: { ...StyleSheet.absoluteFill, backgroundColor: "rgba(0,0,0,0.6)" },
  drawerRoot: { ...StyleSheet.absoluteFill, zIndex: 100 },
  drawerPanel: { position: "absolute", top: 0, bottom: 0, left: 0, width: SW * 0.82, backgroundColor: C.bg1, borderRightWidth: 1, borderRightColor: C.bd0 },
  drawerTop: { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingVertical: 14, gap: 10 },
  drawerLogo: { width: 28, height: 28, borderRadius: 8, backgroundColor: C.tx0, alignItems: "center", justifyContent: "center" },
  drawerLogoText: { color: C.bg0, fontSize: 10, fontWeight: "900" },
  drawerBrand: { color: C.tx0, fontSize: 16, fontWeight: "700" },
  drawerSearch: { flexDirection: "row", alignItems: "center", gap: 8, marginHorizontal: 12, marginBottom: 12, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: C.bg2, borderRadius: 10, borderWidth: 1, borderColor: C.bd0 },
  drawerSearchInput: { flex: 1, color: C.tx0, fontSize: 14 },
  drawerScroll: { flex: 1 },
  drawerSection: { marginBottom: 4 },
  drawerSectionHead: { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingVertical: 8 },
  drawerSectionLabel: { flex: 1, color: C.tx3, fontSize: 11, fontWeight: "700", letterSpacing: 0.8 },
  drawerItem: { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingVertical: 10, gap: 10 },
  drawerItemActive: { backgroundColor: C.bg3 },
  drawerItemIcon: { width: 20, alignItems: "center" },
  drawerItemLabel: { flex: 1, color: C.tx1, fontSize: 14 },
  drawerItemLabelActive: { color: C.tx0 },
  drawerItemTrailing: {},
  drawerMuted: { color: C.tx3, fontSize: 13, paddingHorizontal: 16, paddingVertical: 8 },
  activeSessionDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.ac1 },
  newChatBtn: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 16, paddingVertical: 12, marginBottom: 8 },
  newChatText: { color: C.tx0, fontSize: 15, fontWeight: "500" },
  drawerFooter: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 16, paddingVertical: 14, borderTopWidth: 1, borderTopColor: C.bd0 },
  drawerUserRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  drawerUserName: { color: C.tx1, fontSize: 14, fontWeight: "500" },
  avatar: { width: 30, height: 30, borderRadius: 15, backgroundColor: C.ac4, alignItems: "center", justifyContent: "center" },
  avatarText: { color: "#fff", fontSize: 13, fontWeight: "700" },
  usageCard: { marginHorizontal: 12, marginBottom: 8, borderWidth: 1, borderColor: C.bd0, borderRadius: 10, overflow: "hidden" },
  usageCardHead: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingVertical: 10 },
  usageCardTitle: { color: C.tx0, fontSize: 13, fontWeight: "600" },
  usageCardSummary: { color: C.tx2, fontSize: 12 },
  usageRows: { paddingHorizontal: 12, paddingBottom: 12, gap: 8 },
  usageRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  usageRowLabel: { color: C.tx1, fontSize: 12, fontWeight: "600", width: 52 },
  usageBar: { flex: 1, height: 4, backgroundColor: C.bg3, borderRadius: 2, overflow: "hidden" },
  usageBarFill: { height: 4, borderRadius: 2 },
  usageRowRight: { color: C.tx2, fontSize: 12, width: 40, textAlign: "right" },
  usageReset: { color: C.tx2, fontSize: 12, width: 52, textAlign: "right" },
  usageSource: { color: C.tx3, fontSize: 11 },
  popupBg: { ...StyleSheet.absoluteFill, zIndex: 48 },
  popup: { position: "absolute", left: 14, backgroundColor: C.bg2, borderRadius: 14, borderWidth: 1, borderColor: C.bd1, overflow: "hidden", zIndex: 50, minWidth: 220 },
  popupItem: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 13, borderBottomWidth: 1, borderBottomColor: C.bd0 },
  popupItemLabel: { flex: 1, color: C.tx0, fontSize: 14 },
  attachBox: { paddingHorizontal: 12, paddingBottom: 12, gap: 8 },
  attachInput: { height: 38, borderWidth: 1, borderColor: C.bd2, borderRadius: 8, paddingHorizontal: 10, color: C.tx0, backgroundColor: C.bg3 },
  attachBtn: { height: 36, borderRadius: 8, backgroundColor: C.tx0, alignItems: "center", justifyContent: "center" },
  attachBtnText: { color: C.bg0, fontWeight: "700" },
  skillsPopup: { position: "absolute", left: 14, right: 14, maxHeight: PICKER_MAX_HEIGHT, backgroundColor: C.bg2, borderRadius: 14, borderWidth: 1, borderColor: C.bd1, overflow: "hidden", zIndex: 50 },
  skillsHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 14, paddingTop: 12, paddingBottom: 6 },
  skillsTitle: { color: C.tx0, fontSize: 14, fontWeight: "700" },
  skillsCount: { color: C.tx2, fontSize: 12 },
  skillsSearch: { marginHorizontal: 12, marginBottom: 8, height: 36, borderWidth: 1, borderColor: C.bd2, borderRadius: 8, paddingHorizontal: 10, color: C.tx0, backgroundColor: C.bg3, fontSize: 14 },
  filterRow: { paddingHorizontal: 12, paddingBottom: 8, gap: 6 },
  pickerList: { maxHeight: PICKER_MAX_HEIGHT - 128 },
  pickerListContent: { paddingBottom: 16 },
  filterChip: { borderWidth: 1, borderColor: C.bd2, borderRadius: 99, paddingHorizontal: 12, paddingVertical: 5 },
  filterChipActive: { backgroundColor: C.tx0, borderColor: C.tx0 },
  filterChipText: { color: C.tx2, fontSize: 12, fontWeight: "600" },
  filterChipTextActive: { color: C.bg0 },
  skillItem: { flexDirection: "row", alignItems: "center", paddingHorizontal: 12, paddingVertical: 10, gap: 10 },
  skillItemActive: { backgroundColor: C.bg3 },
  skillIcon: { width: 28, height: 28, borderRadius: 7, backgroundColor: C.bg3, alignItems: "center", justifyContent: "center" },
  skillName: { color: C.tx0, fontSize: 14, fontWeight: "500" },
  skillSrc: { color: C.tx2, fontSize: 12 },
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "flex-end" },
  modelSheet: { flexDirection: "row", backgroundColor: C.bg2, borderTopLeftRadius: 18, borderTopRightRadius: 18, overflow: "hidden" },
  modelCol: { flex: 1, paddingHorizontal: 16, paddingVertical: 16 },
  modelColHead: { color: C.tx2, fontSize: 11, fontWeight: "700", letterSpacing: 0.8, marginBottom: 12, textTransform: "uppercase" },
  modelOption: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: 12, paddingHorizontal: 8, borderRadius: 8 },
  modelOptionText: { color: C.tx0, fontSize: 14, flex: 1, marginRight: 8 },
  modelDivider: { height: 1, backgroundColor: C.bd1, marginVertical: 8 },
  modelHint: { color: C.tx2, fontSize: 12, marginTop: 8, lineHeight: 16 },
  ctxCard: { position: "absolute", bottom: 170, left: 14, backgroundColor: C.bg2, borderRadius: 14, borderWidth: 1, borderColor: C.bd1, padding: 16, width: 260 },
  ctxTitle: { color: C.tx2, fontSize: 12, fontWeight: "600", marginBottom: 6 },
  ctxPercent: { color: C.tx0, fontSize: 32, fontWeight: "700", marginBottom: 4 },
  ctxDetail: { color: C.tx1, fontSize: 13, marginBottom: 6 },
  ctxNote: { color: C.tx2, fontSize: 12 },
  hubRoot: { flex: 1, backgroundColor: C.bg0 },
  hubHeader: { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: C.bd0, gap: 12 },
  hubHeaderIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: C.bg2, borderWidth: 1, borderColor: C.bd1, alignItems: "center", justifyContent: "center" },
  hubTitle: { color: C.tx0, fontSize: 18, fontWeight: "700" },
  hubCloseBtn: { width: 32, height: 32, borderRadius: 8, backgroundColor: C.bg2, alignItems: "center", justifyContent: "center" },
  hubBanner: { backgroundColor: "#0a2a1a", borderBottomWidth: 1, borderBottomColor: "#1a4a2a", paddingHorizontal: 16, paddingVertical: 10 },
  hubBannerText: { color: "#6ee7b7", fontSize: 13 },
  hubContent: { paddingHorizontal: 16, paddingTop: 20, paddingBottom: 40 },
  hubSectionTitle: { color: C.tx2, fontSize: 12, fontWeight: "700", letterSpacing: 0.8, textTransform: "uppercase", marginTop: 24, marginBottom: 10 },
  hubMuted: { color: C.tx2, fontSize: 14, lineHeight: 20, marginBottom: 8 },
  hubAction: { flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: C.bg2, borderRadius: 10, borderWidth: 1, borderColor: C.bd1, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 8 },
  hubActionText: { flex: 1, color: C.tx0, fontSize: 14, fontWeight: "500" },
  hubProjectRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", backgroundColor: C.bg2, borderRadius: 10, borderWidth: 1, borderColor: C.bd1, padding: 14, marginBottom: 8 },
  hubProjectRowActive: { borderColor: C.ac1 },
  hubProjectLeft: { flexDirection: "row", alignItems: "center", gap: 10, flex: 1 },
  hubProjectName: { color: C.tx0, fontSize: 14, fontWeight: "600", marginBottom: 2 },
  hubProjectPath: { color: C.tx2, fontSize: 12 },
  hubInfoRow: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: C.bd0, gap: 16 },
  hubInfoLabel: { color: C.tx1, fontSize: 13, fontWeight: "600", flex: 1 },
  hubInfoValue: { color: C.tx2, fontSize: 13, flex: 2, textAlign: "right" },
  hubCmdCard: { backgroundColor: C.bg2, borderRadius: 10, borderWidth: 1, borderColor: C.bd1, padding: 14, marginBottom: 8 },
  hubCmdTop: { flexDirection: "row", alignItems: "flex-start", gap: 12 },
  hubCmdLabel: { color: C.tx0, fontSize: 14, fontWeight: "600", marginBottom: 2 },
  hubCmdMeta: { color: C.tx3, fontSize: 11, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace", marginBottom: 4 },
  hubCmdDesc: { color: C.tx2, fontSize: 13 },
  hubCmdActions: { alignItems: "center", gap: 6 },
  hubCmdConfigure: { width: 32, height: 32, borderRadius: 8, borderWidth: 1, borderColor: C.bd2, alignItems: "center", justifyContent: "center" },
  hubCmdRun: { backgroundColor: C.tx0, borderRadius: 8, paddingHorizontal: 14, paddingVertical: 8 },
  hubCmdRunDanger: { backgroundColor: "#7f1d1d" },
  hubCmdRunText: { color: C.bg0, fontSize: 13, fontWeight: "700" },
  hubApproval: { flexDirection: "row", alignItems: "center", backgroundColor: C.bg2, borderRadius: 10, borderWidth: 1, borderColor: C.bd1, padding: 14, marginBottom: 8, gap: 12 },
  hubApprovalCmd: { color: C.tx0, fontSize: 14, fontWeight: "600", marginBottom: 2 },
  hubApprovalMeta: { color: C.tx2, fontSize: 12 },
  hubApprovalBtns: { flexDirection: "row", gap: 8 },
  approveBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: "#15803d", alignItems: "center", justifyContent: "center" },
  rejectBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: "#b91c1c", alignItems: "center", justifyContent: "center" },
  cmdForm: { marginTop: 14, gap: 12, borderTopWidth: 1, borderTopColor: C.bd0, paddingTop: 14 },
  cmdArgBlock: { gap: 6 },
  cmdArgLabel: { color: C.tx2, fontSize: 12, fontWeight: "600" },
  cmdArgInput: { height: 38, borderWidth: 1, borderColor: C.bd2, borderRadius: 8, paddingHorizontal: 10, color: C.tx0, backgroundColor: C.bg3, fontSize: 14 },
  cmdSwitchRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" }
});
