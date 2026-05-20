export const LEGACY_LOCAL_API_URL = "http://127.0.0.1:8000/api";
export const DEFAULT_LAN_API_BASE_URL = "http://192.168.0.238:8000";
export const SCHOOL_LAN_API_BASE_URL = "http://192.168.0.238:8000";
const CURRENT_LAN_API_BASE_URL = DEFAULT_LAN_API_BASE_URL;
const DEFAULT_API_URL = process.env.EXPO_PUBLIC_API_URL ?? `${CURRENT_LAN_API_BASE_URL}/api`;
let apiUrlOverride: string | null = null;

export function normalizeApiUrl(value: string) {
  let trimmed = value.trim().replace(/\/+$/, "");
  if (!trimmed) return DEFAULT_API_URL;
  return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
}

export function getDefaultApiUrl() {
  return normalizeApiUrl(DEFAULT_API_URL);
}

export function getApiUrl() {
  return normalizeApiUrl(apiUrlOverride || DEFAULT_API_URL);
}

export function setApiUrlOverride(value: string) {
  apiUrlOverride = normalizeApiUrl(value || DEFAULT_API_URL);
}

export async function testApiConnection(value: string) {
  const apiUrl = normalizeApiUrl(value || DEFAULT_API_URL);
  const response = await fetch(`${apiUrl}/auth/login/`, { method: "GET" });
  return {
    apiUrl,
    ok: response.status < 500,
    status: response.status
  };
}

export type Device = {
  id: string;
  owner_username?: string;
  name: string;
  platform: string;
  status: string;
  last_seen_at: string | null;
  project_count: number;
  capabilities_updated_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type Project = {
  id: string;
  owner_username?: string;
  device: string;
  device_name: string;
  device_status: string;
  name: string;
  local_path: string;
  repository_url: string;
  default_model: string;
  default_profile: string;
  default_sandbox: string;
  default_approval_policy: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type AgentSession = {
  id: string;
  device: string;
  device_name: string;
  device_status: string;
  project: string;
  project_name: string;
  project_path: string;
  parent_session: string | null;
  parent_session_title: string;
  agent_type: string;
  title: string;
  summary: string;
  codex_session_id: string;
  model: string;
  profile: string;
  sandbox: string;
  approval_policy: string;
  git_branch: string;
  add_dirs: string[];
  model_settings: Record<string, unknown>;
  selected_skills: string[];
  web_search_enabled: boolean;
  tool_settings: Record<string, unknown>;
  status: string;
  task_count: number;
  last_activity_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DeviceDetail = Device & {
  projects: Array<{
    id: string;
    name: string;
    local_path: string;
    repository_url: string;
    default_model: string;
    default_profile: string;
    default_sandbox: string;
    default_approval_policy: string;
    is_active: boolean;
  }>;
};

export type Task = {
  id: string;
  device: string;
  device_name: string;
  project: string;
  project_name: string;
  session: string | null;
  session_title: string;
  prompt: string;
  agent_type: string;
  status: string;
  final_output: string;
  exit_code: number | null;
  error_code: string;
  error_message: string;
  created_at: string;
  updated_at: string;
};

export type TaskEvent = {
  id: string;
  sequence: number;
  event_type: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type SkillCapability = {
  id: string;
  name: string;
  description: string;
  path?: string;
  source?: string;
};

export type ModelCapability = {
  id: string;
  name: string;
  description?: string;
  context_window?: number;
  default_reasoning_level?: string;
  supported_reasoning_levels?: Array<{ effort: string; description?: string }>;
};

export type FileMention = {
  path: string;
  name: string;
  relative_path: string;
  extension: string;
  kind: "file" | "image" | string;
};

export type GitState = {
  branch: string;
  dirty: boolean;
  upstream: string;
  branches: string[];
  status: string;
};

export type ApprovalRequest = {
  id: string;
  device: string;
  device_name: string;
  project: string | null;
  project_name: string;
  session: string | null;
  session_title: string;
  task: string | null;
  action_type: string;
  action_payload: Record<string, unknown>;
  command_id: string;
  arguments: Record<string, unknown>;
  stdout: string;
  stderr: string;
  exit_code: number | null;
  risk_level: "low" | "medium" | "high" | "critical";
  status: "pending" | "approved" | "rejected" | "running" | "succeeded" | "failed";
  result_message: string;
  error_message: string;
  requested_at: string;
  decided_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  expires_at: string | null;
  updated_at: string;
};

export type CodexCommandDefinition = {
  id: string;
  group: string;
  label: string;
  description: string;
  maturity: string;
  risk_level: "low" | "medium" | "high" | "critical";
  command_template: string;
  args_schema: Array<{
    name: string;
    type: string;
    required?: boolean;
    repeatable?: boolean;
    placeholder?: string;
    choices?: string[];
    risk_level?: string;
    approval_reason?: string;
  }>;
  requires_project: boolean;
  requires_approval: boolean;
  supported_surface: string | string[];
  local_cli_min_version?: string;
};

export type SlashCommandDefinition = {
  id: string;
  name: string;
  group: string;
  description: string;
};

export type DeviceCapabilities = {
  id: string;
  capabilities: {
    codex?: {
      available?: boolean;
      version?: string;
      login_status?: string;
    };
    codex_usage_limits?: {
      five_hour?: CodexUsageLimitWindow;
      weekly?: CodexUsageLimitWindow;
      plan_type?: string;
      rate_limit_reached_type?: string | null;
      source?: string;
      observed_at?: string;
      stale?: boolean;
    };
    models?: ModelCapability[];
    models_raw?: string;
    model_context_windows?: Record<string, number>;
    mcp?: { raw?: string };
    mcp_servers?: Array<{ id: string; name: string }>;
    plugin_marketplaces?: Array<{ id: string; name: string; path?: string; installed?: boolean }>;
    installed_plugins?: Array<{ id: string; name: string; description?: string; marketplace?: string; path?: string; enabled?: boolean; installed?: boolean }>;
    plugins?: Array<{ id: string; name: string; description?: string; marketplace?: string; path?: string; enabled?: boolean; installed?: boolean }>;
    features?: Array<{ id: string; name: string; maturity?: string; enabled?: boolean | null }>;
    features_raw?: string;
    profiles?: string[];
    slash_commands?: Array<{ id: string; name: string }>;
    codex_sessions?: Array<Record<string, unknown>>;
    config_summary?: Record<string, unknown>;
    diagnostics?: Record<string, unknown>;
    skills?: SkillCapability[];
    project_git?: Record<string, GitState>;
    project_files?: Record<string, FileMention[]>;
    platform?: string;
    collected_at?: string;
  };
  capabilities_updated_at: string | null;
};

export type CodexUsageLimitWindow = {
  used_percent?: number;
  remaining_percent?: number;
  window_minutes?: number;
  resets_at?: string;
  source?: string;
  observed_at?: string;
};

export type WorkspaceBootstrap = {
  account?: {
    id: number;
    username: string;
  };
  devices: Device[];
  projects: Project[];
  pending_approvals: ApprovalRequest[];
  latest_session: AgentSession | null;
};

export type TimelineItem = {
  id: string;
  kind:
    | "user_message"
    | "assistant_message"
    | "assistant_preview"
    | "status"
    | "queued"
    | "running"
    | "thinking"
    | "reasoning_summary"
    | "tool_call"
    | "command"
    | "terminal"
    | "terminal_stdout"
    | "terminal_stderr"
    | "diff"
    | "error"
    | "warning"
    | "approval"
    | "usage_limits"
    | "final";
  content: string;
  task_id: string | null;
  sequence: number;
  payload: Record<string, unknown>;
  created_at: string;
};

export type TerminalSession = {
  id: string;
  device: string;
  device_name: string;
  project: string;
  project_name: string;
  project_path: string;
  status: "queued" | "claimed" | "running" | "exited" | "killed" | "failed";
  cwd: string;
  shell: string;
  cols: number;
  rows: number;
  exit_code: number | null;
  error_code: string;
  error_message: string;
  kill_requested: boolean;
  claimed_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  last_activity_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TerminalEvent = {
  id: string;
  session: string;
  sequence: number;
  kind: "ready" | "status" | "output" | "stderr" | "cwd" | "exit" | "error";
  stream: string;
  data: string;
  cwd: string;
  exit_code: number | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type SessionMessage = {
  id: string;
  session: string;
  task: string | null;
  role: "user" | "assistant" | "system";
  content: string;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type SessionSettingsPayload = Partial<
  Pick<
    AgentSession,
    | "model"
    | "profile"
    | "sandbox"
    | "approval_policy"
    | "git_branch"
    | "add_dirs"
    | "model_settings"
    | "selected_skills"
    | "web_search_enabled"
    | "tool_settings"
  >
>;

export type CodexCommandCatalog = {
  commands: CodexCommandDefinition[];
  slash_commands: SlashCommandDefinition[];
};

async function request<T>(path: string, token: string | null, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const apiUrl = getApiUrl();
  const url = `${apiUrl}${path}`;
  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    throw new Error(
      publicErrorMessage(`Network request failed for ${path} using ${apiUrl}. ${detail}`)
    );
  }
  if (!response.ok) {
    const text = await response.text();
    let message = text || `HTTP ${response.status}`;
    try {
      const payload = JSON.parse(text) as { message?: string; details?: unknown; code?: string };
      const detailMessage = firstErrorMessage(payload.details);
      message = detailMessage || payload.message || message;
      if (payload.code && !message.includes(payload.code)) {
        message = `${message} (${payload.code})`;
      }
    } catch {
      const title = text.match(/<title>(.*?)<\/title>/i)?.[1]?.trim();
      if (title) {
        message = `${title}. Restart backendu albo sprawdz DJANGO_ALLOWED_HOSTS/API URL.`;
      } else if (text.trim().startsWith("<!DOCTYPE") || text.trim().startsWith("<html")) {
        message = `Backend zwrocil strone HTML zamiast JSON (HTTP ${response.status}).`;
      }
    }
    throw new Error(publicErrorMessage(message));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

function publicErrorMessage(message: string): string {
  if (
    message.includes("TOKEN_NOT_VALID") ||
    message.includes("token_not_valid") ||
    message.includes("Given token not valid")
  ) {
    return "Sesja wygasla. Zaloguj sie ponownie.";
  }
  return message;
}

function firstErrorMessage(value: unknown): string {
  if (!value) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = firstErrorMessage(item);
      if (message) return message;
    }
  }
  if (typeof value === "object") {
    for (const item of Object.values(value as Record<string, unknown>)) {
      const message = firstErrorMessage(item);
      if (message) return message;
    }
  }
  return "";
}

export async function login(username: string, password: string) {
  return request<{ access: string; refresh: string }>("/auth/login/", null, {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
}

export async function fetchDevices(token: string) {
  return request<Device[]>("/devices/", token);
}

export async function fetchWorkspaceBootstrap(token: string) {
  return request<WorkspaceBootstrap>("/workspace/bootstrap/", token);
}

export async function fetchDevice(token: string, deviceId: string) {
  return request<DeviceDetail>(`/devices/${deviceId}/`, token);
}

export async function fetchDeviceCapabilities(token: string, deviceId: string) {
  return request<DeviceCapabilities>(`/devices/${deviceId}/capabilities/`, token);
}

export async function refreshDeviceCapabilities(token: string, deviceId: string) {
  return request<{ id: string; status: string }>(`/devices/${deviceId}/capabilities/refresh/`, token, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export async function deleteDevice(token: string, deviceId: string) {
  return request<void>(`/devices/${deviceId}/`, token, {
    method: "DELETE"
  });
}

export async function fetchProjects(token: string) {
  return request<Project[]>("/projects/", token);
}

export async function fetchProject(token: string, projectId: string) {
  return request<Project>(`/projects/${projectId}/`, token);
}

export async function updateProject(
  token: string,
  projectId: string,
  payload: Partial<Pick<Project, "name" | "default_model" | "default_profile" | "default_sandbox" | "default_approval_policy">>
) {
  return request<Project>(`/projects/${projectId}/`, token, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function createTask(token: string, project: string, prompt: string, agentType = "codex", session?: string) {
  return request<Task>("/tasks/", token, {
    method: "POST",
    body: JSON.stringify({ project, prompt, agent_type: agentType, session: session || null })
  });
}

export async function fetchTasks(
  token: string,
  filters: Partial<{
    status: string;
    agent_type: string;
    device: string;
    project: string;
    session: string;
    ordering: string;
    page: number;
  }> = {}
) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<Paginated<Task>>(`/tasks/${query}`, token);
}

export async function fetchTask(token: string, taskId: string) {
  return request<Task>(`/tasks/${taskId}/`, token);
}

export async function cancelTask(token: string, taskId: string) {
  return request<Task>(`/tasks/${taskId}/cancel/`, token, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export async function fetchTaskEvents(token: string, taskId: string, after?: number) {
  const query = after ? `?after=${after}` : "";
  return request<TaskEvent[]>(`/tasks/${taskId}/events/${query}`, token);
}

export async function createPairingCode(token: string) {
  return request<{ code: string; expires_at: string; created_at: string }>("/pairing-codes/", token, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export async function fetchSessions(
  token: string,
  filters: Partial<{
    project: string;
    device: string;
    status: string;
    agent_type: string;
    ordering: string;
    page: number;
  }> = {}
) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<Paginated<AgentSession>>(`/sessions/${query}`, token);
}

export async function fetchSession(token: string, sessionId: string) {
  return request<AgentSession>(`/sessions/${sessionId}/`, token);
}

export async function createSession(token: string, project: string, title?: string, settings: SessionSettingsPayload = {}) {
  return request<AgentSession>("/sessions/", token, {
    method: "POST",
    body: JSON.stringify({ project, title: title || "", ...settings })
  });
}

export async function updateSession(token: string, sessionId: string, payload: Partial<Pick<AgentSession, "title" | "summary">>) {
  return request<AgentSession>(`/sessions/${sessionId}/`, token, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function closeSession(token: string, sessionId: string) {
  return request<AgentSession>(`/sessions/${sessionId}/close/`, token, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export async function forkSession(token: string, sessionId: string, title?: string) {
  return request<AgentSession>(`/sessions/${sessionId}/fork/`, token, {
    method: "POST",
    body: JSON.stringify({ title: title || "" })
  });
}

export async function emergencyStopSession(token: string, sessionId: string) {
  return request<{ status: "stopped"; canceled_tasks: string[]; killed_terminals: string[] }>(
    `/sessions/${sessionId}/emergency-stop/`,
    token,
    {
      method: "POST",
      body: JSON.stringify({})
    }
  );
}

export async function fetchSessionTimeline(token: string, sessionId: string, after?: number) {
  const query = after ? `?after=${after}` : "";
  return request<TimelineItem[]>(`/sessions/${sessionId}/timeline/${query}`, token);
}

export async function sendSessionMessage(
  token: string,
  sessionId: string,
  content: string,
  settingsOverrides?: SessionSettingsPayload,
  selectedSkillIds?: string[]
) {
  return request<{ message: SessionMessage; task: Task; session: AgentSession }>(`/sessions/${sessionId}/messages/`, token, {
    method: "POST",
    body: JSON.stringify({
      content,
      settings_overrides: settingsOverrides,
      selected_skill_ids: selectedSkillIds
    })
  });
}

export async function updateSessionSettings(token: string, sessionId: string, payload: SessionSettingsPayload) {
  return request<AgentSession>(`/sessions/${sessionId}/settings/`, token, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function fetchSessionAttachments(token: string, sessionId: string) {
  return request<{ images: string[]; attachments: Array<{ path: string; type: string }> }>(`/sessions/${sessionId}/attachments/`, token);
}

export async function createSessionAttachment(token: string, sessionId: string, payload: { path: string; type?: "image" | "file" }) {
  return request<{ images: string[]; attachments: Array<{ path: string; type: string }> }>(`/sessions/${sessionId}/attachments/`, token, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function createBranchApproval(
  token: string,
  projectId: string,
  payload: { action: "switch" | "create"; branch: string; base?: string; dirty?: boolean; session?: string }
) {
  return request<ApprovalRequest>(`/projects/${projectId}/git/branch/`, token, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchApprovals(token: string, status?: string) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<Paginated<ApprovalRequest>>(`/approvals/${query}`, token);
}

export async function approveRequest(token: string, approvalId: string) {
  return request<ApprovalRequest>(`/approvals/${approvalId}/approve/`, token, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export async function rejectRequest(token: string, approvalId: string) {
  return request<ApprovalRequest>(`/approvals/${approvalId}/reject/`, token, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export async function fetchCommandCatalog(token: string) {
  return request<CodexCommandCatalog>("/codex/command-catalog/", token);
}

export async function createCodexAction(
  token: string,
  payload: { command_id: string; arguments?: Record<string, unknown>; project?: string; device?: string; session?: string }
) {
  return request<ApprovalRequest>("/codex/actions/", token, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function searchSessions(token: string, q: string) {
  const query = q ? `?q=${encodeURIComponent(q)}` : "";
  return request<AgentSession[]>(`/sessions/search/${query}`, token);
}

export async function createTerminalSession(token: string, projectId: string, cwd?: string, cols = 96, rows = 28) {
  return request<TerminalSession>("/terminal/sessions/", token, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, cwd: cwd || "", cols, rows })
  });
}

export async function fetchTerminalSession(token: string, terminalId: string) {
  return request<TerminalSession>(`/terminal/sessions/${terminalId}/`, token);
}

export async function fetchTerminalEvents(token: string, terminalId: string, after?: number) {
  const query = after ? `?after=${after}` : "";
  return request<TerminalEvent[]>(`/terminal/sessions/${terminalId}/events/${query}`, token);
}

export async function sendTerminalInput(token: string, terminalId: string, data: string) {
  return request<void>(`/terminal/sessions/${terminalId}/input/`, token, {
    method: "POST",
    body: JSON.stringify({ data })
  });
}

export async function resizeTerminal(token: string, terminalId: string, cols: number, rows: number) {
  return request<void>(`/terminal/sessions/${terminalId}/resize/`, token, {
    method: "POST",
    body: JSON.stringify({ cols, rows })
  });
}

export async function killTerminal(token: string, terminalId: string) {
  return request<TerminalSession>(`/terminal/sessions/${terminalId}/kill/`, token, {
    method: "POST",
    body: JSON.stringify({})
  });
}

export function sessionWebSocketUrl(sessionId: string, token: string) {
  const configured = process.env.EXPO_PUBLIC_WS_URL;
  if (configured) {
    return `${configured.replace(/\/$/, "")}/ws/sessions/${sessionId}/?token=${encodeURIComponent(token)}`;
  }
  const base = getApiUrl().replace(/\/api\/?$/, "").replace(/^http/, "ws");
  return `${base}/ws/sessions/${sessionId}/?token=${encodeURIComponent(token)}`;
}

export function terminalWebSocketUrl(terminalId: string, token: string) {
  const configured = process.env.EXPO_PUBLIC_WS_URL;
  if (configured) {
    return `${configured.replace(/\/$/, "")}/ws/terminal/${terminalId}/?token=${encodeURIComponent(token)}`;
  }
  const base = getApiUrl().replace(/\/api\/?$/, "").replace(/^http/, "ws");
  return `${base}/ws/terminal/${terminalId}/?token=${encodeURIComponent(token)}`;
}
