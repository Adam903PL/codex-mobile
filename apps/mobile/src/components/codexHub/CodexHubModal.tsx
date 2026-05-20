import {
  Activity,
  BarChart2,
  Bug,
  Check,
  ChevronDown,
  ChevronRight,
  Cloud,
  Code,
  Command,
  Cpu,
  GitBranch,
  Globe,
  Layers,
  Package,
  RefreshCw,
  Search,
  Server,
  Settings,
  Shield,
  Terminal,
  Wrench,
  X
} from "lucide-react-native";
import { memo, useCallback, useMemo, useState } from "react";
import {
  FlatList,
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
import { SafeAreaView } from "react-native-safe-area-context";
import {
  ApprovalRequest,
  CodexCommandDefinition,
  Device,
  DeviceCapabilities,
  Project,
  SlashCommandDefinition,
  TimelineItem
} from "../../api/client";
import { T } from "../../theme";

export type HubSectionId =
  | "overview"
  | "workspace"
  | "commands"
  | "plugins"
  | "mcp"
  | "git"
  | "cloud"
  | "debug"
  | "approvals";

type HubMetric = {
  id: string;
  label: string;
  value: string;
  tone?: "neutral" | "good" | "warn" | "danger";
};

type HubCommandFilter = {
  search: string;
  group: string;
  risk: string;
};

type HubInventoryTab = "marketplaces" | "installed" | "skills";
type UsageWindow = NonNullable<NonNullable<DeviceCapabilities["capabilities"]["codex_usage_limits"]>["five_hour"]>;

type Props = {
  section: string;
  onClose: () => void;
  projects: Project[];
  workspaceAccount?: { id: number; username: string } | null;
  workspaceRefreshing?: boolean;
  workspaceError?: string;
  activeProject: Project | null;
  devices: Device[];
  activeDevice: Device | null;
  capabilities: DeviceCapabilities["capabilities"];
  commandCatalog: CodexCommandDefinition[];
  slashCommands: SlashCommandDefinition[];
  pendingApprovals: ApprovalRequest[];
  actionMessage: string;
  realtimeStatus: "connected" | "reconnecting" | "polling" | "disconnected";
  timeline: TimelineItem[];
  onRunCommand: (command: CodexCommandDefinition, args?: Record<string, unknown>) => void;
  onApprovalDecision: (id: string, decision: "approve" | "reject") => void;
  onRefreshCapabilities: () => void;
  onRefreshWorkspace: () => void;
  onPairing: () => void;
  onSelectProject: (id: string) => void;
  onSignOut: () => void;
};

const HUB_SECTIONS: Array<{ id: HubSectionId; label: string; Icon: typeof Layers }> = [
  { id: "overview", label: "Overview", Icon: BarChart2 },
  { id: "workspace", label: "Workspaces", Icon: Layers },
  { id: "commands", label: "Commands", Icon: Command },
  { id: "plugins", label: "Plugins", Icon: Package },
  { id: "mcp", label: "MCP", Icon: Server },
  { id: "git", label: "Git", Icon: GitBranch },
  { id: "cloud", label: "Cloud", Icon: Cloud },
  { id: "debug", label: "Debug", Icon: Bug },
  { id: "approvals", label: "Approvals", Icon: Shield }
];

const RISK_ORDER = ["all", "low", "medium", "high", "critical", "approval"];

export function CodexHubModal({
  section,
  onClose,
  projects,
  workspaceAccount,
  workspaceRefreshing = false,
  workspaceError = "",
  activeProject,
  devices,
  activeDevice,
  capabilities,
  commandCatalog,
  slashCommands,
  pendingApprovals,
  actionMessage,
  realtimeStatus,
  timeline,
  onRunCommand,
  onApprovalDecision,
  onRefreshCapabilities,
  onRefreshWorkspace,
  onPairing,
  onSelectProject,
  onSignOut
}: Props) {
  const initialSection = normalizeSection(section);
  const [activeSection, setActiveSection] = useState<HubSectionId>(initialSection);
  const [commandFilter, setCommandFilter] = useState<HubCommandFilter>({ search: "", group: "all", risk: "all" });
  const [expandedCommand, setExpandedCommand] = useState<string | null>(null);
  const [commandArgs, setCommandArgs] = useState<Record<string, Record<string, unknown>>>({});
  const [pluginTab, setPluginTab] = useState<HubInventoryTab>("installed");
  const [pluginSearch, setPluginSearch] = useState("");
  const [mcpSearch, setMcpSearch] = useState("");
  const [debugSearch, setDebugSearch] = useState("");

  const pendingCount = pendingApprovals.filter((approval) => approval.status === "pending").length;
  const skills = capabilities.skills || [];
  const installedPlugins = capabilities.installed_plugins || capabilities.plugins || [];
  const marketplaces = capabilities.plugin_marketplaces || [];
  const mcpServers = capabilities.mcp_servers || [];
  const features = capabilities.features || [];
  const diagnostics = capabilities.diagnostics || {};
  const models = capabilities.models || [];
  const gitState = activeProject ? capabilities.project_git?.[activeProject.id] : undefined;
  const codex = capabilities.codex || {};

  const commandGroups = useMemo(() => {
    return ["all", ...Array.from(new Set(commandCatalog.map((command) => command.group))).sort()];
  }, [commandCatalog]);

  const filteredCommands = useMemo(() => {
    return commandCatalog.filter((command) => {
      const q = commandFilter.search.trim().toLowerCase();
      if (commandFilter.group !== "all" && command.group !== commandFilter.group) return false;
      if (commandFilter.risk === "approval" && !command.requires_approval) return false;
      if (commandFilter.risk !== "all" && commandFilter.risk !== "approval" && command.risk_level !== commandFilter.risk) return false;
      if (!q) return true;
      return `${command.id} ${command.label} ${command.description} ${command.group}`.toLowerCase().includes(q);
    });
  }, [commandCatalog, commandFilter]);

  function updateArg(commandId: string, name: string, value: unknown) {
    setCommandArgs((current) => ({ ...current, [commandId]: { ...(current[commandId] || {}), [name]: value } }));
  }

  function runCommand(command: CodexCommandDefinition) {
    onRunCommand(command, commandArgs[command.id] || {});
  }

  const current = HUB_SECTIONS.find((item) => item.id === activeSection) || HUB_SECTIONS[0];
  const CurrentIcon = current.Icon;

  return (
    <Modal visible animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={styles.root}>
        <View style={styles.header}>
          <View style={styles.headerIcon}>
            <CurrentIcon size={18} color={T.tx0} />
          </View>
          <View style={styles.headerText}>
            <Text style={styles.eyebrow}>Codex Hub</Text>
            <Text style={styles.title}>{current.label}</Text>
          </View>
          <Pressable style={styles.headerAction} onPress={onRefreshCapabilities} hitSlop={8}>
            <RefreshCw size={16} color={T.tx1} />
          </Pressable>
          <Pressable style={styles.headerAction} onPress={onClose} hitSlop={8}>
            <X size={16} color={T.tx1} />
          </Pressable>
        </View>

        <HubSectionNav active={activeSection} pendingCount={pendingCount} onChange={setActiveSection} />

        {actionMessage ? (
          <View style={styles.banner}>
            <Text style={styles.bannerText}>{actionMessage}</Text>
          </View>
        ) : null}

        {pendingCount > 0 && activeSection !== "approvals" ? (
          <Pressable style={styles.pendingStrip} onPress={() => setActiveSection("approvals")}>
            <Shield size={15} color={T.ac2} />
            <Text style={styles.pendingStripText}>{pendingCount} approval{pendingCount === 1 ? "" : "s"} waiting</Text>
            <ChevronRight size={15} color={T.tx2} />
          </Pressable>
        ) : null}

        {activeSection === "overview" ? (
          <HubOverview
            codex={codex}
            realtimeStatus={realtimeStatus}
            activeDevice={activeDevice}
            activeProject={activeProject}
            devices={devices}
            projects={projects}
            capabilities={capabilities}
            metrics={[
              { id: "models", label: "Models", value: String(models.length), tone: models.length ? "good" : "warn" },
              { id: "skills", label: "Skills", value: String(skills.length), tone: skills.length ? "good" : "warn" },
              { id: "plugins", label: "Plugins", value: String(installedPlugins.length), tone: installedPlugins.length ? "good" : "neutral" },
              { id: "mcp", label: "MCP", value: String(mcpServers.length), tone: mcpServers.length ? "good" : "neutral" }
            ]}
            onPairing={onPairing}
            onRefreshWorkspace={onRefreshWorkspace}
            onRefreshCapabilities={onRefreshCapabilities}
          />
        ) : null}

        {activeSection === "workspace" ? (
          <HubWorkspaces
            projects={projects}
            workspaceAccount={workspaceAccount}
            workspaceRefreshing={workspaceRefreshing}
            workspaceError={workspaceError}
            activeProject={activeProject}
            activeDevice={activeDevice}
            capabilities={capabilities}
            onSelectProject={onSelectProject}
            onRefreshWorkspace={onRefreshWorkspace}
            onPairing={onPairing}
          />
        ) : null}

        {activeSection === "commands" ? (
          <HubCommands
            commands={filteredCommands}
            slashCommands={slashCommands}
            commandGroups={commandGroups}
            filter={commandFilter}
            expandedCommand={expandedCommand}
            commandArgs={commandArgs}
            onFilterChange={setCommandFilter}
            onExpandedCommandChange={setExpandedCommand}
            onArgChange={updateArg}
            onRunCommand={runCommand}
          />
        ) : null}

        {activeSection === "plugins" ? (
          <HubPlugins
            tab={pluginTab}
            search={pluginSearch}
            marketplaces={marketplaces}
            installedPlugins={installedPlugins}
            skills={skills}
            commands={commandCatalog.filter((command) => command.group === "plugins")}
            commandArgs={commandArgs}
            expandedCommand={expandedCommand}
            onTabChange={setPluginTab}
            onSearchChange={setPluginSearch}
            onArgChange={updateArg}
            onExpandedCommandChange={setExpandedCommand}
            onRunCommand={runCommand}
          />
        ) : null}

        {activeSection === "mcp" ? (
          <HubMcp
            search={mcpSearch}
            servers={mcpServers}
            commands={commandCatalog.filter((command) => command.group === "mcp")}
            commandArgs={commandArgs}
            expandedCommand={expandedCommand}
            onSearchChange={setMcpSearch}
            onArgChange={updateArg}
            onExpandedCommandChange={setExpandedCommand}
            onRunCommand={runCommand}
          />
        ) : null}

        {activeSection === "git" ? (
          <HubGit
            activeProject={activeProject}
            gitState={gitState}
            commands={commandCatalog.filter((command) => command.group === "git")}
            commandArgs={commandArgs}
            expandedCommand={expandedCommand}
            onArgChange={updateArg}
            onExpandedCommandChange={setExpandedCommand}
            onRunCommand={runCommand}
          />
        ) : null}

        {activeSection === "cloud" ? (
          <HubCloud
            commands={commandCatalog.filter((command) => command.group === "cloud")}
            commandArgs={commandArgs}
            expandedCommand={expandedCommand}
            onArgChange={updateArg}
            onExpandedCommandChange={setExpandedCommand}
            onRunCommand={runCommand}
          />
        ) : null}

        {activeSection === "debug" ? (
          <HubDebug
            search={debugSearch}
            capabilities={capabilities}
            diagnostics={diagnostics}
            features={features}
            timeline={timeline}
            realtimeStatus={realtimeStatus}
            commands={commandCatalog.filter((command) => command.group === "debug" || command.group === "setup")}
            commandArgs={commandArgs}
            expandedCommand={expandedCommand}
            onSearchChange={setDebugSearch}
            onArgChange={updateArg}
            onExpandedCommandChange={setExpandedCommand}
            onRunCommand={runCommand}
          />
        ) : null}

        {activeSection === "approvals" ? (
          <HubApprovals
            approvals={pendingApprovals}
            onApprovalDecision={onApprovalDecision}
            onSignOut={onSignOut}
          />
        ) : null}
      </SafeAreaView>
    </Modal>
  );
}

function HubSectionNav({ active, pendingCount, onChange }: { active: HubSectionId; pendingCount: number; onChange: (id: HubSectionId) => void }) {
  return (
    <View style={styles.navWrap}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.navContent}>
        {HUB_SECTIONS.map(({ id, label, Icon }) => {
          const selected = active === id;
          return (
            <Pressable key={id} style={[styles.navChip, selected && styles.navChipActive]} onPress={() => onChange(id)}>
              <Icon size={14} color={selected ? T.bg0 : T.tx2} />
              <Text style={[styles.navChipText, selected && styles.navChipTextActive]}>{label}</Text>
              {id === "approvals" && pendingCount > 0 ? (
                <View style={styles.navBadge}>
                  <Text style={styles.navBadgeText}>{pendingCount}</Text>
                </View>
              ) : null}
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

function HubOverview({
  codex,
  realtimeStatus,
  activeDevice,
  activeProject,
  devices,
  projects,
  capabilities,
  metrics,
  onPairing,
  onRefreshWorkspace,
  onRefreshCapabilities
}: {
  codex: DeviceCapabilities["capabilities"]["codex"];
  realtimeStatus: Props["realtimeStatus"];
  activeDevice: Device | null;
  activeProject: Project | null;
  devices: Device[];
  projects: Project[];
  capabilities: DeviceCapabilities["capabilities"];
  metrics: HubMetric[];
  onPairing: () => void;
  onRefreshWorkspace: () => void;
  onRefreshCapabilities: () => void;
}) {
  const usage = capabilities.codex_usage_limits;
  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <View style={styles.heroCard}>
        <View style={styles.heroTop}>
          <View>
            <Text style={styles.heroTitle}>Local Codex workspace</Text>
            <Text style={styles.heroSub}>{activeProject?.name || "No project selected"}</Text>
          </View>
          <StatusBadge label={statusLabel(realtimeStatus)} tone={realtimeStatus === "connected" ? "good" : realtimeStatus === "polling" ? "warn" : "neutral"} />
        </View>
        <View style={styles.infoGrid}>
          <InfoPill label="Device" value={activeDevice?.name || "Not paired"} />
          <InfoPill label="Codex" value={codex?.version || "Unknown"} />
          <InfoPill label="Login" value={codex?.login_status || "Unknown"} />
          <InfoPill label="Updated" value={shortDate(capabilities.collected_at)} />
        </View>
      </View>

      <MetricGrid metrics={metrics} />

      <View style={styles.card}>
        <SectionHeader title="Usage remaining" subtitle={usage?.source || "Codex telemetry"} />
        <UsageLine label="5h" limit={usage?.five_hour} />
        <UsageLine label="Weekly" limit={usage?.weekly} />
      </View>

      <View style={styles.actionGrid}>
        <ActionCard title="Refresh capabilities" description="Models, plugins, skills, MCP, Git and diagnostics." Icon={RefreshCw} onPress={onRefreshCapabilities} />
        <ActionCard title="Refresh workspace" description={`${devices.length} devices, ${projects.length} projects.`} Icon={Layers} onPress={onRefreshWorkspace} />
        <ActionCard title="Pairing and devices" description="Open CLI setup, pairing code and recovery commands." Icon={Settings} onPress={onPairing} />
      </View>
    </ScrollView>
  );
}

function HubWorkspaces({
  projects,
  workspaceAccount,
  workspaceRefreshing,
  workspaceError,
  activeProject,
  activeDevice,
  capabilities,
  onSelectProject,
  onRefreshWorkspace,
  onPairing
}: {
  projects: Project[];
  workspaceAccount?: { id: number; username: string } | null;
  workspaceRefreshing: boolean;
  workspaceError: string;
  activeProject: Project | null;
  activeDevice: Device | null;
  capabilities: DeviceCapabilities["capabilities"];
  onSelectProject: (id: string) => void;
  onRefreshWorkspace: () => void;
  onPairing: () => void;
}) {
  const renderProject = useCallback(({ item }: { item: Project }) => {
    const git = capabilities.project_git?.[item.id];
    const active = item.id === activeProject?.id;
    return (
      <Pressable style={[styles.projectCard, active && styles.projectCardActive]} onPress={() => onSelectProject(item.id)}>
        <View style={styles.projectHeader}>
          <View style={styles.projectIcon}>
            <GitBranch size={16} color={active ? T.ac1 : T.tx1} />
          </View>
          <View style={styles.projectText}>
            <Text style={styles.projectTitle}>{item.name}</Text>
            <Text style={styles.projectPath} numberOfLines={1}>{item.local_path}</Text>
          </View>
          {active ? <Check size={17} color={T.ac1} /> : null}
        </View>
        <View style={styles.projectMeta}>
          <StatusBadge label={git?.branch || "no branch"} tone={git?.dirty ? "warn" : "neutral"} />
          <StatusBadge label={git?.dirty ? "dirty" : "clean"} tone={git?.dirty ? "warn" : "good"} />
          <StatusBadge label={item.device_status || "unknown"} tone={item.device_status === "online" ? "good" : "neutral"} />
        </View>
      </Pressable>
    );
  }, [activeProject?.id, capabilities.project_git, onSelectProject]);

  return (
    <FlatList
      data={projects}
      keyExtractor={(item) => item.id}
      renderItem={renderProject}
      contentContainerStyle={styles.listContent}
      ListHeaderComponent={(
        <View style={styles.stack}>
          <SectionHeader title="Workspaces" subtitle={activeDevice ? `Active device: ${activeDevice.name}` : "No active device"} />
          <View style={styles.card}>
            <InfoPill label="Logged in" value={workspaceAccount?.username || "Unknown"} />
            <InfoPill label="Device owner" value={activeDevice?.owner_username || activeProject?.owner_username || "Unknown"} />
            {workspaceError ? <Text style={styles.errorText}>{workspaceError}</Text> : null}
            {workspaceAccount?.username && (activeDevice?.owner_username || activeProject?.owner_username) && workspaceAccount.username !== (activeDevice?.owner_username || activeProject?.owner_username) ? (
              <Text style={styles.warnText}>Mobile and CLI are using different accounts. Sign in or pair the CLI with the same user.</Text>
            ) : null}
          </View>
          <View style={styles.actionGrid}>
            <ActionCard title={workspaceRefreshing ? "Refreshing..." : "Refresh workspaces"} description="Reload devices, projects and latest sessions." Icon={RefreshCw} onPress={onRefreshWorkspace} />
            <ActionCard title="Pair CLI" description="Generate code and show devlink pair/connect commands." Icon={Terminal} onPress={onPairing} />
          </View>
        </View>
      )}
      ListEmptyComponent={<EmptyState title="No projects" body="Pair the CLI device, then run devlink projects add --path and refresh workspaces." action="Open pairing" onAction={onPairing} />}
    />
  );
}

function HubCommands({
  commands,
  slashCommands,
  commandGroups,
  filter,
  expandedCommand,
  commandArgs,
  onFilterChange,
  onExpandedCommandChange,
  onArgChange,
  onRunCommand
}: {
  commands: CodexCommandDefinition[];
  slashCommands: SlashCommandDefinition[];
  commandGroups: string[];
  filter: HubCommandFilter;
  expandedCommand: string | null;
  commandArgs: Record<string, Record<string, unknown>>;
  onFilterChange: (filter: HubCommandFilter) => void;
  onExpandedCommandChange: (id: string | null) => void;
  onArgChange: (commandId: string, name: string, value: unknown) => void;
  onRunCommand: (command: CodexCommandDefinition) => void;
}) {
  const renderCommand = useCallback(({ item }: { item: CodexCommandDefinition }) => (
    <CommandCard
      command={item}
      expanded={expandedCommand === item.id}
      values={commandArgs[item.id] || {}}
      onToggle={() => onExpandedCommandChange(expandedCommand === item.id ? null : item.id)}
      onChange={(name, value) => onArgChange(item.id, name, value)}
      onRun={() => onRunCommand(item)}
    />
  ), [commandArgs, expandedCommand, onArgChange, onExpandedCommandChange, onRunCommand]);

  return (
    <FlatList
      data={commands}
      keyExtractor={(item) => item.id}
      renderItem={renderCommand}
      contentContainerStyle={styles.listContent}
      ListHeaderComponent={(
        <View style={styles.stack}>
          <SectionHeader title="Command catalog" subtitle={`${commands.length} matching commands`} />
          <SearchBox value={filter.search} onChangeText={(search) => onFilterChange({ ...filter, search })} placeholder="Search commands, flags, groups..." />
          <ChipRow values={commandGroups} active={filter.group} onChange={(group) => onFilterChange({ ...filter, group })} />
          <ChipRow values={RISK_ORDER} active={filter.risk} onChange={(risk) => onFilterChange({ ...filter, risk })} />
        </View>
      )}
      ListFooterComponent={slashCommands.length > 0 ? (
        <View style={styles.card}>
          <SectionHeader title="Slash commands" subtitle={`${slashCommands.length} desktop commands visible in mobile`} />
          {slashCommands.map((command) => (
            <View key={command.id} style={styles.slashRow}>
              <Text style={styles.slashName}>{command.name}</Text>
              <Text style={styles.slashDesc} numberOfLines={2}>{command.description}</Text>
            </View>
          ))}
        </View>
      ) : null}
      ListEmptyComponent={<EmptyState title="No commands" body="Try another search, risk filter or command group." />}
    />
  );
}

function HubPlugins({
  tab,
  search,
  marketplaces,
  installedPlugins,
  skills,
  commands,
  commandArgs,
  expandedCommand,
  onTabChange,
  onSearchChange,
  onArgChange,
  onExpandedCommandChange,
  onRunCommand
}: {
  tab: HubInventoryTab;
  search: string;
  marketplaces: Array<{ id: string; name: string; path?: string; installed?: boolean }>;
  installedPlugins: Array<{ id: string; name: string; description?: string; marketplace?: string; path?: string; enabled?: boolean; installed?: boolean }>;
  skills: NonNullable<DeviceCapabilities["capabilities"]["skills"]>;
  commands: CodexCommandDefinition[];
  commandArgs: Record<string, Record<string, unknown>>;
  expandedCommand: string | null;
  onTabChange: (tab: HubInventoryTab) => void;
  onSearchChange: (value: string) => void;
  onArgChange: (commandId: string, name: string, value: unknown) => void;
  onExpandedCommandChange: (id: string | null) => void;
  onRunCommand: (command: CodexCommandDefinition) => void;
}) {
  const pluginSkills = skills.filter((skill) => skill.source === "plugin");
  const data = useMemo(() => {
    const q = search.trim().toLowerCase();
    const source = tab === "marketplaces" ? marketplaces : tab === "installed" ? installedPlugins : pluginSkills;
    return source.filter((item) => `${item.id} ${item.name} ${"description" in item ? item.description || "" : ""} ${"path" in item ? item.path || "" : ""}`.toLowerCase().includes(q));
  }, [installedPlugins, marketplaces, pluginSkills, search, tab]);

  const renderItem = useCallback(({ item }: { item: any }) => (
    <InventoryCard
      title={item.name || item.id}
      subtitle={item.description || item.marketplace || item.path || item.source || "plugin inventory"}
      badges={[item.enabled === false ? "disabled" : item.installed === false ? "available" : "installed"]}
      Icon={tab === "skills" ? Wrench : Package}
    />
  ), [tab]);

  return (
    <FlatList
      data={data}
      keyExtractor={(item: any) => item.id || item.name}
      renderItem={renderItem}
      contentContainerStyle={styles.listContent}
      ListHeaderComponent={(
        <View style={styles.stack}>
          <SectionHeader title="Plugins" subtitle={`${marketplaces.length} marketplaces, ${installedPlugins.length} installed, ${pluginSkills.length} plugin skills`} />
          <SearchBox value={search} onChangeText={onSearchChange} placeholder="Search marketplaces, plugins or skills..." />
          <ChipRow values={["installed", "marketplaces", "skills"]} active={tab} onChange={(value) => onTabChange(value as HubInventoryTab)} />
          <View style={styles.commandRail}>
            {commands.map((command) => (
              <MiniCommand key={command.id} command={command} onPress={() => onRunCommand(command)} />
            ))}
          </View>
        </View>
      )}
      ListEmptyComponent={<EmptyState title="No plugin data" body="Refresh capabilities or check Codex plugin cache/config diagnostics." />}
      ListFooterComponent={(
        <View style={styles.stack}>
          {commands.map((command) => expandedCommand === command.id ? (
            <CommandCard
              key={command.id}
              command={command}
              expanded
              values={commandArgs[command.id] || {}}
              onToggle={() => onExpandedCommandChange(null)}
              onChange={(name, value) => onArgChange(command.id, name, value)}
              onRun={() => onRunCommand(command)}
            />
          ) : null)}
        </View>
      )}
    />
  );
}

function HubMcp({
  search,
  servers,
  commands,
  commandArgs,
  expandedCommand,
  onSearchChange,
  onArgChange,
  onExpandedCommandChange,
  onRunCommand
}: {
  search: string;
  servers: NonNullable<DeviceCapabilities["capabilities"]["mcp_servers"]>;
  commands: CodexCommandDefinition[];
  commandArgs: Record<string, Record<string, unknown>>;
  expandedCommand: string | null;
  onSearchChange: (value: string) => void;
  onArgChange: (commandId: string, name: string, value: unknown) => void;
  onExpandedCommandChange: (id: string | null) => void;
  onRunCommand: (command: CodexCommandDefinition) => void;
}) {
  const filtered = servers.filter((server: any) => `${server.id} ${server.name} ${server.auth_status || ""} ${server.transport?.type || ""}`.toLowerCase().includes(search.toLowerCase()));
  return (
    <FlatList
      data={filtered}
      keyExtractor={(item: any) => item.id || item.name}
      contentContainerStyle={styles.listContent}
      renderItem={({ item }: { item: any }) => (
        <InventoryCard
          title={item.name || item.id}
          subtitle={item.auth_status || item.transport?.type || item.url || item.command || "configured server"}
          badges={[item.auth_status || "configured"]}
          Icon={Server}
        />
      )}
      ListHeaderComponent={(
        <View style={styles.stack}>
          <SectionHeader title="MCP servers" subtitle={`${servers.length} configured servers`} />
          <SearchBox value={search} onChangeText={onSearchChange} placeholder="Search MCP servers..." />
          <CommandRail commands={commands} onPress={onRunCommand} />
        </View>
      )}
      ListFooterComponent={(
        <View style={styles.stack}>
          {commands.map((command) => (
            <CommandCard
              key={command.id}
              command={command}
              expanded={expandedCommand === command.id}
              values={commandArgs[command.id] || {}}
              onToggle={() => onExpandedCommandChange(expandedCommand === command.id ? null : command.id)}
              onChange={(name, value) => onArgChange(command.id, name, value)}
              onRun={() => onRunCommand(command)}
            />
          ))}
        </View>
      )}
      ListEmptyComponent={<EmptyState title="No MCP servers" body="Use MCP add/login actions or refresh capabilities." />}
    />
  );
}

function HubGit({
  activeProject,
  gitState,
  commands,
  commandArgs,
  expandedCommand,
  onArgChange,
  onExpandedCommandChange,
  onRunCommand
}: {
  activeProject: Project | null;
  gitState: DeviceCapabilities["capabilities"]["project_git"] extends Record<string, infer G> ? G | undefined : any;
  commands: CodexCommandDefinition[];
  commandArgs: Record<string, Record<string, unknown>>;
  expandedCommand: string | null;
  onArgChange: (commandId: string, name: string, value: unknown) => void;
  onExpandedCommandChange: (id: string | null) => void;
  onRunCommand: (command: CodexCommandDefinition) => void;
}) {
  return (
    <FlatList
      data={commands}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.listContent}
      renderItem={({ item }) => (
        <CommandCard
          command={item}
          expanded={expandedCommand === item.id}
          values={commandArgs[item.id] || {}}
          onToggle={() => onExpandedCommandChange(expandedCommand === item.id ? null : item.id)}
          onChange={(name, value) => onArgChange(item.id, name, value)}
          onRun={() => onRunCommand(item)}
        />
      )}
      ListHeaderComponent={(
        <View style={styles.stack}>
          <SectionHeader title="Git workspace" subtitle={activeProject?.name || "No project"} />
          <View style={styles.card}>
            <InfoRow label="Branch" value={gitState?.branch || "--"} />
            <InfoRow label="Dirty" value={gitState?.dirty ? "yes" : "no"} tone={gitState?.dirty ? "warn" : "good"} />
            <InfoRow label="Upstream" value={gitState?.upstream || "--"} />
            <InfoRow label="Status" value={gitState?.status || "--"} />
          </View>
        </View>
      )}
      ListEmptyComponent={<EmptyState title="No Git commands" body="Command catalog did not return Git actions." />}
    />
  );
}

function HubCloud({
  commands,
  commandArgs,
  expandedCommand,
  onArgChange,
  onExpandedCommandChange,
  onRunCommand
}: {
  commands: CodexCommandDefinition[];
  commandArgs: Record<string, Record<string, unknown>>;
  expandedCommand: string | null;
  onArgChange: (commandId: string, name: string, value: unknown) => void;
  onExpandedCommandChange: (id: string | null) => void;
  onRunCommand: (command: CodexCommandDefinition) => void;
}) {
  return (
    <FlatList
      data={commands}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.listContent}
      renderItem={({ item }) => (
        <CommandCard
          command={item}
          expanded={expandedCommand === item.id}
          values={commandArgs[item.id] || {}}
          onToggle={() => onExpandedCommandChange(expandedCommand === item.id ? null : item.id)}
          onChange={(name, value) => onArgChange(item.id, name, value)}
          onRun={() => onRunCommand(item)}
        />
      )}
      ListHeaderComponent={(
        <View style={styles.stack}>
          <SectionHeader title="Codex Cloud" subtitle="Cloud list, execute and apply actions from the local bridge." />
          <View style={styles.noticeCard}>
            <Cloud size={18} color={T.ac2} />
            <Text style={styles.noticeText}>Cloud exec/apply can create remote tasks or change the local workspace, so risky actions always go through approval.</Text>
          </View>
        </View>
      )}
      ListEmptyComponent={<EmptyState title="No Cloud commands" body="Backend command catalog did not expose codex.cloud actions." />}
    />
  );
}

function HubDebug({
  search,
  capabilities,
  diagnostics,
  features,
  timeline,
  realtimeStatus,
  commands,
  commandArgs,
  expandedCommand,
  onSearchChange,
  onArgChange,
  onExpandedCommandChange,
  onRunCommand
}: {
  search: string;
  capabilities: DeviceCapabilities["capabilities"];
  diagnostics: Record<string, unknown>;
  features: NonNullable<DeviceCapabilities["capabilities"]["features"]>;
  timeline: TimelineItem[];
  realtimeStatus: Props["realtimeStatus"];
  commands: CodexCommandDefinition[];
  commandArgs: Record<string, Record<string, unknown>>;
  expandedCommand: string | null;
  onSearchChange: (value: string) => void;
  onArgChange: (commandId: string, name: string, value: unknown) => void;
  onExpandedCommandChange: (id: string | null) => void;
  onRunCommand: (command: CodexCommandDefinition) => void;
}) {
  const diagnosticRows = Object.entries(diagnostics).filter(([key, value]) => `${key} ${String(value)}`.toLowerCase().includes(search.toLowerCase()));
  const recentTimeline = timeline.slice(-12).reverse();
  return (
    <FlatList
      data={diagnosticRows}
      keyExtractor={([key]) => key}
      contentContainerStyle={styles.listContent}
      renderItem={({ item: [key, value] }) => <InfoRow label={key} value={String(value)} />}
      ListHeaderComponent={(
        <View style={styles.stack}>
          <SectionHeader title="Debug console" subtitle={`Realtime: ${statusLabel(realtimeStatus)}`} />
          <MetricGrid metrics={[
            { id: "socket", label: "Socket", value: statusLabel(realtimeStatus), tone: realtimeStatus === "connected" ? "good" : "warn" },
            { id: "models", label: "Models", value: String((capabilities.models || []).length), tone: (capabilities.models || []).length ? "good" : "warn" },
            { id: "features", label: "Features", value: String(features.length), tone: "neutral" },
            { id: "events", label: "Events", value: String(timeline.length), tone: timeline.length ? "good" : "neutral" }
          ]} />
          <SearchBox value={search} onChangeText={onSearchChange} placeholder="Filter diagnostics..." />
          <CommandRail commands={commands} onPress={onRunCommand} />
          <View style={styles.card}>
            <SectionHeader title="Recent events" subtitle="Last task/timeline events" />
            {recentTimeline.map((item) => (
              <View key={item.id} style={styles.eventRow}>
                <Text style={styles.eventKind}>{item.kind}</Text>
                <Text style={styles.eventText} numberOfLines={2}>{item.content || preview(item.payload)}</Text>
              </View>
            ))}
            {recentTimeline.length === 0 ? <Text style={styles.emptyInline}>No timeline events yet.</Text> : null}
          </View>
        </View>
      )}
      ListFooterComponent={(
        <View style={styles.stack}>
          {commands.map((command) => (
            <CommandCard
              key={command.id}
              command={command}
              expanded={expandedCommand === command.id}
              values={commandArgs[command.id] || {}}
              onToggle={() => onExpandedCommandChange(expandedCommand === command.id ? null : command.id)}
              onChange={(name, value) => onArgChange(command.id, name, value)}
              onRun={() => onRunCommand(command)}
            />
          ))}
        </View>
      )}
      ListEmptyComponent={<EmptyState title="No diagnostics" body="No diagnostics match the current filter." />}
    />
  );
}

function HubApprovals({ approvals, onApprovalDecision, onSignOut }: { approvals: ApprovalRequest[]; onApprovalDecision: (id: string, decision: "approve" | "reject") => void; onSignOut: () => void }) {
  const renderApproval = useCallback(({ item }: { item: ApprovalRequest }) => (
    <View style={styles.approvalCard}>
      <View style={styles.approvalHead}>
        <View style={styles.approvalIcon}>
          <Shield size={16} color={riskColor(item.risk_level)} />
        </View>
        <View style={styles.approvalText}>
          <Text style={styles.approvalTitle}>{item.command_id || item.action_type}</Text>
          <Text style={styles.approvalMeta}>{item.status} - {item.risk_level}</Text>
        </View>
        <StatusBadge label={item.status} tone={item.status === "pending" ? "warn" : item.status === "approved" ? "good" : "neutral"} />
      </View>
      {item.result_message ? <Text style={styles.cardDesc}>{item.result_message}</Text> : null}
      {item.error_message ? <Text style={styles.errorText}>{item.error_message}</Text> : null}
      {item.status === "pending" ? (
        <View style={styles.approvalActions}>
          <Pressable style={styles.rejectButton} onPress={() => onApprovalDecision(item.id, "reject")}>
            <X size={15} color="#fff" />
            <Text style={styles.rejectButtonText}>Reject</Text>
          </Pressable>
          <Pressable style={styles.approveButton} onPress={() => onApprovalDecision(item.id, "approve")}>
            <Check size={15} color={T.bg0} />
            <Text style={styles.approveButtonText}>Approve</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  ), [onApprovalDecision]);

  return (
    <FlatList
      data={approvals}
      keyExtractor={(item) => item.id}
      renderItem={renderApproval}
      contentContainerStyle={styles.listContent}
      ListHeaderComponent={(
        <View style={styles.stack}>
          <SectionHeader title="Approvals" subtitle={`${approvals.filter((item) => item.status === "pending").length} pending actions`} />
          <ActionCard title="Logout mobile" description="Sign out of this mobile app only." Icon={Shield} onPress={onSignOut} />
        </View>
      )}
      ListEmptyComponent={<EmptyState title="No approvals" body="Risky Codex, Git, Cloud, MCP and plugin actions will appear here." />}
    />
  );
}

const CommandCard = memo(function CommandCard({
  command,
  expanded,
  values,
  onToggle,
  onChange,
  onRun
}: {
  command: CodexCommandDefinition;
  expanded: boolean;
  values: Record<string, unknown>;
  onToggle: () => void;
  onChange: (name: string, value: unknown) => void;
  onRun: () => void;
}) {
  const risky = command.requires_approval || ["high", "critical"].includes(command.risk_level);
  return (
    <View style={styles.commandCard}>
      <View style={styles.commandTop}>
        <View style={styles.commandIcon}>
          <Command size={16} color={riskColor(command.risk_level)} />
        </View>
        <View style={styles.commandBody}>
          <Text style={styles.commandTitle}>{command.label}</Text>
          <Text style={styles.commandId}>{command.id}</Text>
          <Text style={styles.cardDesc} numberOfLines={2}>{command.description}</Text>
        </View>
        <View style={styles.commandSide}>
          <StatusBadge label={command.risk_level} tone={riskTone(command.risk_level)} />
          <StatusBadge label={command.maturity} tone={command.maturity === "stable" ? "good" : "neutral"} />
        </View>
      </View>
      <View style={styles.commandActions}>
        <Pressable style={styles.secondaryButton} onPress={onToggle}>
          <Settings size={14} color={T.tx1} />
          <Text style={styles.secondaryButtonText}>{expanded ? "Hide form" : command.args_schema.length ? "Configure" : "Details"}</Text>
        </Pressable>
        <Pressable style={[styles.primaryButton, risky && styles.requestButton]} onPress={onRun}>
          <Text style={[styles.primaryButtonText, risky && styles.requestButtonText]}>{risky ? "Request approval" : "Run"}</Text>
        </Pressable>
      </View>
      {expanded ? <CommandArgsForm command={command} values={values} onChange={onChange} /> : null}
    </View>
  );
});

function CommandArgsForm({ command, values, onChange }: { command: CodexCommandDefinition; values: Record<string, unknown>; onChange: (name: string, value: unknown) => void }) {
  if (command.args_schema.length === 0) {
    return <Text style={styles.emptyInline}>No arguments required.</Text>;
  }
  return (
    <View style={styles.argsForm}>
      {command.args_schema.map((arg) => {
        const value = values[arg.name];
        if (arg.type === "boolean") {
          return (
            <View key={arg.name} style={styles.argSwitchRow}>
              <View style={styles.argText}>
                <Text style={styles.argLabel}>{arg.name}{arg.required ? " *" : ""}</Text>
                {arg.approval_reason ? <Text style={styles.argHint}>{arg.approval_reason}</Text> : null}
              </View>
              <Switch value={Boolean(value)} onValueChange={(next) => onChange(arg.name, next)} trackColor={{ true: T.ac1 }} />
            </View>
          );
        }
        if (arg.type === "choice" && Array.isArray(arg.choices)) {
          return (
            <View key={arg.name} style={styles.argBlock}>
              <Text style={styles.argLabel}>{arg.name}{arg.required ? " *" : ""}</Text>
              <ChipRow values={arg.choices} active={String(value || "")} onChange={(next) => onChange(arg.name, next)} />
            </View>
          );
        }
        return (
          <View key={arg.name} style={styles.argBlock}>
            <Text style={styles.argLabel}>{arg.name}{arg.required ? " *" : ""}</Text>
            <TextInput
              style={styles.argInput}
              placeholder={arg.placeholder || arg.name}
              placeholderTextColor={T.tx2}
              value={String(value || "")}
              onChangeText={(text) => onChange(arg.name, text)}
              multiline={arg.type === "list"}
              autoCapitalize="none"
            />
            {arg.type === "list" ? <Text style={styles.argHint}>Separate values with commas or new lines.</Text> : null}
          </View>
        );
      })}
    </View>
  );
}

function CommandRail({ commands, onPress }: { commands: CodexCommandDefinition[]; onPress: (command: CodexCommandDefinition) => void }) {
  if (commands.length === 0) return null;
  return (
    <View style={styles.commandRail}>
      {commands.map((command) => <MiniCommand key={command.id} command={command} onPress={() => onPress(command)} />)}
    </View>
  );
}

function MiniCommand({ command, onPress }: { command: CodexCommandDefinition; onPress: () => void }) {
  const risky = command.requires_approval || ["high", "critical"].includes(command.risk_level);
  return (
    <Pressable style={[styles.miniCommand, risky && styles.miniCommandRisk]} onPress={onPress}>
      <Text style={[styles.miniCommandText, risky && styles.miniCommandRiskText]}>{command.label}</Text>
    </Pressable>
  );
}

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {subtitle ? <Text style={styles.sectionSub}>{subtitle}</Text> : null}
    </View>
  );
}

function MetricGrid({ metrics }: { metrics: HubMetric[] }) {
  return (
    <View style={styles.metricsGrid}>
      {metrics.map((metric) => (
        <View key={metric.id} style={styles.metricCard}>
          <Text style={[styles.metricValue, metric.tone ? { color: toneColor(metric.tone) } : undefined]}>{metric.value}</Text>
          <Text style={styles.metricLabel}>{metric.label}</Text>
        </View>
      ))}
    </View>
  );
}

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoPill}>
      <Text style={styles.infoPillLabel}>{label}</Text>
      <Text style={styles.infoPillValue} numberOfLines={1}>{value}</Text>
    </View>
  );
}

function InfoRow({ label, value, tone }: { label: string; value: string; tone?: "neutral" | "good" | "warn" | "danger" }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={[styles.infoValue, tone ? { color: toneColor(tone) } : undefined]} numberOfLines={2}>{value}</Text>
    </View>
  );
}

function ActionCard({ title, description, Icon, onPress }: { title: string; description: string; Icon: typeof Layers; onPress: () => void }) {
  return (
    <Pressable style={styles.actionCard} onPress={onPress}>
      <View style={styles.actionIcon}>
        <Icon size={16} color={T.tx0} />
      </View>
      <View style={styles.actionText}>
        <Text style={styles.actionTitle}>{title}</Text>
        <Text style={styles.actionDesc} numberOfLines={2}>{description}</Text>
      </View>
      <ChevronRight size={15} color={T.tx3} />
    </Pressable>
  );
}

function InventoryCard({ title, subtitle, badges, Icon }: { title: string; subtitle: string; badges: string[]; Icon: typeof Layers }) {
  return (
    <View style={styles.inventoryCard}>
      <View style={styles.inventoryIcon}>
        <Icon size={16} color={T.tx1} />
      </View>
      <View style={styles.inventoryBody}>
        <Text style={styles.inventoryTitle}>{title}</Text>
        <Text style={styles.inventorySub} numberOfLines={2}>{subtitle}</Text>
        <View style={styles.badgeRow}>
          {badges.filter(Boolean).map((badge) => <StatusBadge key={badge} label={badge} tone={badge === "disabled" ? "warn" : "neutral"} />)}
        </View>
      </View>
    </View>
  );
}

function SearchBox({ value, onChangeText, placeholder }: { value: string; onChangeText: (text: string) => void; placeholder: string }) {
  return (
    <View style={styles.searchBox}>
      <Search size={14} color={T.tx3} />
      <TextInput
        style={styles.searchInput}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={T.tx3}
        autoCapitalize="none"
        autoCorrect={false}
      />
    </View>
  );
}

function ChipRow({ values, active, onChange }: { values: string[]; active: string; onChange: (value: string) => void }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
      {values.map((value) => {
        const selected = value === active;
        return (
          <Pressable key={value} style={[styles.filterChip, selected && styles.filterChipActive]} onPress={() => onChange(value)}>
            <Text style={[styles.filterChipText, selected && styles.filterChipTextActive]}>{value}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: "neutral" | "good" | "warn" | "danger" }) {
  return (
    <View style={[styles.statusBadge, { borderColor: toneBorder(tone), backgroundColor: toneBackground(tone) }]}>
      <Text style={[styles.statusBadgeText, { color: toneColor(tone) }]}>{label}</Text>
    </View>
  );
}

function UsageLine({ label, limit }: { label: string; limit?: UsageWindow }) {
  const used = numberValue((limit as any)?.used_percent);
  const remaining = numberValue((limit as any)?.remaining_percent);
  const shownRemaining = remaining ?? (used === undefined ? undefined : Math.max(0, 100 - used));
  return (
    <View style={styles.usageLine}>
      <Text style={styles.usageLabel}>{label}</Text>
      <View style={styles.usageTrack}>
        <View style={[styles.usageFill, { width: `${shownRemaining ?? 0}%`, backgroundColor: usageColor(shownRemaining) }]} />
      </View>
      <Text style={styles.usageValue}>{shownRemaining === undefined ? "--" : `${Math.round(shownRemaining)}%`}</Text>
      <Text style={styles.usageReset}>{shortDate((limit as any)?.resets_at)}</Text>
    </View>
  );
}

function EmptyState({ title, body, action, onAction }: { title: string; body: string; action?: string; onAction?: () => void }) {
  return (
    <View style={styles.emptyState}>
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyBody}>{body}</Text>
      {action && onAction ? (
        <Pressable style={styles.emptyAction} onPress={onAction}>
          <Text style={styles.emptyActionText}>{action}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function normalizeSection(section: string): HubSectionId {
  if (section === "workspaces") return "workspace";
  if (HUB_SECTIONS.some((item) => item.id === section)) return section as HubSectionId;
  if (section === "settings" || section === "setup") return "overview";
  return "overview";
}

function statusLabel(status: Props["realtimeStatus"]) {
  return { connected: "Live", reconnecting: "Reconnecting", polling: "Polling", disconnected: "Offline" }[status];
}

function riskTone(risk: string): "neutral" | "good" | "warn" | "danger" {
  if (risk === "low") return "good";
  if (risk === "medium") return "neutral";
  if (risk === "high") return "warn";
  return "danger";
}

function riskColor(risk: string) {
  return toneColor(riskTone(risk));
}

function toneColor(tone: "neutral" | "good" | "warn" | "danger") {
  return { neutral: T.tx1, good: T.ac1, warn: T.ac2, danger: T.ac3 }[tone];
}

function toneBorder(tone: "neutral" | "good" | "warn" | "danger") {
  return { neutral: T.bd2, good: "#14532d", warn: "#78350f", danger: "#7f1d1d" }[tone];
}

function toneBackground(tone: "neutral" | "good" | "warn" | "danger") {
  return { neutral: T.bg3, good: "#052e1b", warn: "#2a1a05", danger: "#2a0a0a" }[tone];
}

function usageColor(value?: number) {
  if (value === undefined) return T.bd2;
  if (value < 15) return T.ac3;
  if (value < 40) return T.ac2;
  return T.ac1;
}

function numberValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function shortDate(value: unknown) {
  if (typeof value !== "string" || !value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function preview(payload: Record<string, unknown>) {
  try {
    return JSON.stringify(payload);
  } catch {
    return "";
  }
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: T.bg0 },
  header: { minHeight: 64, flexDirection: "row", alignItems: "center", gap: T.s10, paddingHorizontal: T.s16, paddingVertical: T.s12, borderBottomWidth: 1, borderBottomColor: T.bd0 },
  headerIcon: { width: 44, height: 44, borderRadius: T.r10, backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, alignItems: "center", justifyContent: "center" },
  headerText: { flex: 1 },
  eyebrow: { color: T.tx2, fontSize: T.f11, fontWeight: "800", letterSpacing: 0.8, textTransform: "uppercase" },
  title: { color: T.tx0, fontSize: T.f20, fontWeight: "800", marginTop: 1 },
  headerAction: { width: 44, height: 44, borderRadius: T.r10, backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, alignItems: "center", justifyContent: "center" },

  navWrap: { borderBottomWidth: 1, borderBottomColor: T.bd0 },
  navContent: { gap: T.s8, paddingHorizontal: T.s12, paddingVertical: T.s10 },
  navChip: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: T.s6, borderWidth: 1, borderColor: T.bd1, borderRadius: T.rFull, paddingHorizontal: T.s12, backgroundColor: T.bg1 },
  navChipActive: { backgroundColor: T.tx0, borderColor: T.tx0 },
  navChipText: { color: T.tx1, fontSize: T.f12, fontWeight: "700" },
  navChipTextActive: { color: T.bg0 },
  navBadge: { minWidth: 44, height: 44, borderRadius: 22, backgroundColor: T.ac3, alignItems: "center", justifyContent: "center", paddingHorizontal: 5 },
  navBadgeText: { color: "#fff", fontSize: T.f10, fontWeight: "800" },

  banner: { borderBottomWidth: 1, borderBottomColor: "#14532d", backgroundColor: "#052e1b", paddingHorizontal: T.s16, paddingVertical: T.s10 },
  bannerText: { color: "#86efac", fontSize: T.f13 },
  pendingStrip: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: T.s8, marginHorizontal: T.s12, marginTop: T.s10, paddingHorizontal: T.s12, borderRadius: T.r10, borderWidth: 1, borderColor: "#78350f", backgroundColor: "#1f1304" },
  pendingStripText: { flex: 1, color: T.ac2, fontSize: T.f13, fontWeight: "700" },

  content: { padding: T.s16, paddingBottom: T.s32, gap: T.s12 },
  listContent: { padding: T.s16, paddingBottom: T.s32, gap: T.s10 },
  stack: { gap: T.s12, marginBottom: T.s10 },
  heroCard: { backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, borderRadius: T.r12, padding: T.s16, gap: T.s14 },
  heroTop: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: T.s12 },
  heroTitle: { color: T.tx0, fontSize: T.f18, fontWeight: "800" },
  heroSub: { color: T.tx2, fontSize: T.f13, marginTop: 3 },
  infoGrid: { flexDirection: "row", flexWrap: "wrap", gap: T.s8 },
  infoPill: { width: "48%", minHeight: 54, borderRadius: T.r8, borderWidth: 1, borderColor: T.bd1, backgroundColor: T.bg1, paddingHorizontal: T.s10, paddingVertical: T.s8 },
  infoPillLabel: { color: T.tx3, fontSize: T.f10, fontWeight: "800", textTransform: "uppercase" },
  infoPillValue: { color: T.tx0, fontSize: T.f13, fontWeight: "700", marginTop: 4 },

  metricsGrid: { flexDirection: "row", flexWrap: "wrap", gap: T.s8 },
  metricCard: { width: "48%", backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, borderRadius: T.r10, padding: T.s12 },
  metricValue: { color: T.tx0, fontSize: T.f24, fontWeight: "900" },
  metricLabel: { color: T.tx2, fontSize: T.f12, fontWeight: "700", marginTop: 4 },

  card: { backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, borderRadius: T.r12, padding: T.s14, gap: T.s10 },
  sectionHeader: { gap: 3 },
  sectionTitle: { color: T.tx0, fontSize: T.f16, fontWeight: "800" },
  sectionSub: { color: T.tx2, fontSize: T.f12, lineHeight: 17 },
  actionGrid: { gap: T.s8 },
  actionCard: { minHeight: 58, flexDirection: "row", alignItems: "center", gap: T.s10, backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, borderRadius: T.r10, paddingHorizontal: T.s12, paddingVertical: T.s10 },
  actionIcon: { width: 44, height: 44, borderRadius: T.r8, backgroundColor: T.bg3, alignItems: "center", justifyContent: "center" },
  actionText: { flex: 1 },
  actionTitle: { color: T.tx0, fontSize: T.f14, fontWeight: "800" },
  actionDesc: { color: T.tx2, fontSize: T.f12, lineHeight: 16, marginTop: 2 },

  usageLine: { minHeight: 38, flexDirection: "row", alignItems: "center", gap: T.s8 },
  usageLabel: { color: T.tx1, fontSize: T.f13, fontWeight: "800", width: 58 },
  usageTrack: { flex: 1, height: 5, borderRadius: 3, backgroundColor: T.bg3, overflow: "hidden" },
  usageFill: { height: 5, borderRadius: 3 },
  usageValue: { color: T.tx1, fontSize: T.f12, width: 44, textAlign: "right" },
  usageReset: { color: T.tx3, fontSize: T.f11, width: 76, textAlign: "right" },

  projectCard: { backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, borderRadius: T.r12, padding: T.s14, gap: T.s10 },
  projectCardActive: { borderColor: T.ac1, backgroundColor: "#081f17" },
  projectHeader: { flexDirection: "row", alignItems: "center", gap: T.s10 },
  projectIcon: { width: 44, height: 44, borderRadius: T.r8, backgroundColor: T.bg3, alignItems: "center", justifyContent: "center" },
  projectText: { flex: 1 },
  projectTitle: { color: T.tx0, fontSize: T.f15, fontWeight: "800" },
  projectPath: { color: T.tx2, fontSize: T.f12, marginTop: 2 },
  projectMeta: { flexDirection: "row", flexWrap: "wrap", gap: T.s6 },

  searchBox: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: T.s8, backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, borderRadius: T.r10, paddingHorizontal: T.s12 },
  searchInput: { flex: 1, color: T.tx0, fontSize: T.f14, paddingVertical: Platform.OS === "ios" ? T.s10 : T.s6 },
  chipRow: { gap: T.s6, paddingVertical: 2 },
  filterChip: { minHeight: 44, justifyContent: "center", borderWidth: 1, borderColor: T.bd2, borderRadius: T.rFull, paddingHorizontal: T.s12 },
  filterChipActive: { backgroundColor: T.tx0, borderColor: T.tx0 },
  filterChipText: { color: T.tx2, fontSize: T.f12, fontWeight: "700" },
  filterChipTextActive: { color: T.bg0 },

  commandCard: { backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, borderRadius: T.r12, padding: T.s14, gap: T.s12 },
  commandTop: { flexDirection: "row", alignItems: "flex-start", gap: T.s10 },
  commandIcon: { width: 44, height: 44, borderRadius: T.r8, backgroundColor: T.bg3, alignItems: "center", justifyContent: "center" },
  commandBody: { flex: 1 },
  commandTitle: { color: T.tx0, fontSize: T.f14, fontWeight: "800" },
  commandId: { color: T.tx3, fontSize: T.f11, marginTop: 2, fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  cardDesc: { color: T.tx2, fontSize: T.f12, lineHeight: 17, marginTop: 5 },
  commandSide: { alignItems: "flex-end", gap: T.s6 },
  commandActions: { flexDirection: "row", gap: T.s8 },
  secondaryButton: { minHeight: 44, flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: T.s6, borderWidth: 1, borderColor: T.bd2, borderRadius: T.r10, paddingHorizontal: T.s10 },
  secondaryButtonText: { color: T.tx1, fontSize: T.f13, fontWeight: "800" },
  primaryButton: { minHeight: 44, flex: 1, alignItems: "center", justifyContent: "center", borderRadius: T.r10, backgroundColor: T.tx0, paddingHorizontal: T.s10 },
  primaryButtonText: { color: T.bg0, fontSize: T.f13, fontWeight: "900" },
  requestButton: { backgroundColor: "#3f1d1d", borderWidth: 1, borderColor: "#7f1d1d" },
  requestButtonText: { color: "#fca5a5" },
  argsForm: { borderTopWidth: 1, borderTopColor: T.bd0, paddingTop: T.s12, gap: T.s12 },
  argBlock: { gap: T.s6 },
  argSwitchRow: { minHeight: 48, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: T.s12 },
  argText: { flex: 1 },
  argLabel: { color: T.tx1, fontSize: T.f12, fontWeight: "800" },
  argHint: { color: T.tx3, fontSize: T.f11, marginTop: 4, lineHeight: 15 },
  argInput: { minHeight: 42, borderWidth: 1, borderColor: T.bd2, borderRadius: T.r8, backgroundColor: T.bg3, color: T.tx0, paddingHorizontal: T.s10, paddingVertical: T.s8, fontSize: T.f13 },

  slashRow: { paddingVertical: T.s10, borderTopWidth: 1, borderTopColor: T.bd0 },
  slashName: { color: T.tx0, fontSize: T.f13, fontWeight: "800", fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" },
  slashDesc: { color: T.tx2, fontSize: T.f12, lineHeight: 17, marginTop: 3 },
  commandRail: { flexDirection: "row", flexWrap: "wrap", gap: T.s8 },
  miniCommand: { minHeight: 44, justifyContent: "center", borderWidth: 1, borderColor: T.bd2, borderRadius: T.rFull, paddingHorizontal: T.s12, backgroundColor: T.bg2 },
  miniCommandRisk: { borderColor: "#7f1d1d", backgroundColor: "#2a0a0a" },
  miniCommandText: { color: T.tx1, fontSize: T.f12, fontWeight: "800" },
  miniCommandRiskText: { color: "#fca5a5" },

  inventoryCard: { flexDirection: "row", alignItems: "flex-start", gap: T.s10, backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, borderRadius: T.r12, padding: T.s14 },
  inventoryIcon: { width: 44, height: 44, borderRadius: T.r8, backgroundColor: T.bg3, alignItems: "center", justifyContent: "center" },
  inventoryBody: { flex: 1 },
  inventoryTitle: { color: T.tx0, fontSize: T.f14, fontWeight: "800" },
  inventorySub: { color: T.tx2, fontSize: T.f12, lineHeight: 17, marginTop: 3 },
  badgeRow: { flexDirection: "row", flexWrap: "wrap", gap: T.s6, marginTop: T.s8 },
  statusBadge: { minHeight: 28, justifyContent: "center", borderWidth: 1, borderRadius: T.rFull, paddingHorizontal: T.s8 },
  statusBadgeText: { fontSize: T.f11, fontWeight: "800" },

  noticeCard: { flexDirection: "row", alignItems: "flex-start", gap: T.s10, backgroundColor: "#1f1304", borderWidth: 1, borderColor: "#78350f", borderRadius: T.r10, padding: T.s12 },
  noticeText: { flex: 1, color: "#fcd34d", fontSize: T.f12, lineHeight: 17 },
  infoRow: { flexDirection: "row", justifyContent: "space-between", gap: T.s12, paddingVertical: T.s8, borderTopWidth: 1, borderTopColor: T.bd0 },
  infoLabel: { color: T.tx2, fontSize: T.f12, fontWeight: "800", flex: 1 },
  infoValue: { color: T.tx1, fontSize: T.f12, flex: 2, textAlign: "right" },
  eventRow: { paddingVertical: T.s8, borderTopWidth: 1, borderTopColor: T.bd0 },
  eventKind: { color: T.tx3, fontSize: T.f10, fontWeight: "900", textTransform: "uppercase" },
  eventText: { color: T.tx1, fontSize: T.f12, lineHeight: 17, marginTop: 3 },

  approvalCard: { backgroundColor: T.bg2, borderWidth: 1, borderColor: T.bd1, borderRadius: T.r12, padding: T.s14, gap: T.s12 },
  approvalHead: { flexDirection: "row", alignItems: "center", gap: T.s10 },
  approvalIcon: { width: 44, height: 44, borderRadius: T.r8, backgroundColor: T.bg3, alignItems: "center", justifyContent: "center" },
  approvalText: { flex: 1 },
  approvalTitle: { color: T.tx0, fontSize: T.f14, fontWeight: "800" },
  approvalMeta: { color: T.tx2, fontSize: T.f12, marginTop: 2 },
  approvalActions: { flexDirection: "row", gap: T.s8 },
  approveButton: { minHeight: 44, flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: T.s6, borderRadius: T.r10, backgroundColor: T.tx0 },
  approveButtonText: { color: T.bg0, fontSize: T.f13, fontWeight: "900" },
  rejectButton: { minHeight: 44, flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: T.s6, borderRadius: T.r10, backgroundColor: "#7f1d1d" },
  rejectButtonText: { color: "#fff", fontSize: T.f13, fontWeight: "900" },
  errorText: { color: "#fca5a5", fontSize: T.f12, lineHeight: 17 },
  warnText: { color: "#fbbf24", fontSize: T.f12, lineHeight: 17 },

  emptyState: { minHeight: 180, alignItems: "center", justifyContent: "center", padding: T.s24, gap: T.s8 },
  emptyTitle: { color: T.tx0, fontSize: T.f16, fontWeight: "800", textAlign: "center" },
  emptyBody: { color: T.tx2, fontSize: T.f13, lineHeight: 19, textAlign: "center" },
  emptyAction: { minHeight: 44, marginTop: T.s8, justifyContent: "center", borderRadius: T.r10, backgroundColor: T.tx0, paddingHorizontal: T.s16 },
  emptyActionText: { color: T.bg0, fontSize: T.f13, fontWeight: "900" },
  emptyInline: { color: T.tx3, fontSize: T.f12, lineHeight: 17, paddingVertical: T.s8 }
});
