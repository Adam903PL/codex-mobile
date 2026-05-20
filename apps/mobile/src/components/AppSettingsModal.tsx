import { ReactNode, useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Check, ChevronRight, Code, MessageSquare, Monitor, Palette, Shield, User, X } from "lucide-react-native";
import { Device, DeviceCapabilities, Project, testApiConnection } from "../api/client";
import { AppSettingsSection, usePreferences } from "../preferences/PreferencesContext";
import { PairingPanel } from "./PairingPanel";

const C = {
  bg0: "#0a0a0a",
  bg1: "#111111",
  bg2: "#181818",
  bg3: "#222222",
  tx0: "#f0f0f0",
  tx1: "#a0a0a0",
  tx2: "#606060",
  tx3: "#303030",
  ac1: "#10b981",
  ac3: "#ef4444",
  bd0: "#1a1a1a",
  bd1: "#252525",
  bd2: "#333333"
} as const;

type Props = {
  visible: boolean;
  section: AppSettingsSection;
  accessToken: string | null;
  devices: Device[];
  projects: Project[];
  activeDevice: Device | null;
  capabilities: DeviceCapabilities["capabilities"];
  actionMessage: string;
  sandboxDraft: string;
  approvalPolicyDraft: string;
  webSearchDraft: boolean;
  planModeDraft: boolean;
  onClose: () => void;
  onSectionChange: (section: AppSettingsSection) => void;
  onRefreshWorkspace: () => void;
  onRefreshCapabilities: () => void;
  onMobileLogout: () => void;
  onCodexLogout: () => void;
  onOpenDebug: () => void;
  onSandboxChange: (value: string) => void;
  onApprovalPolicyChange: (value: string) => void;
  onWebSearchChange: (value: boolean) => void;
  onPlanModeChange: (value: boolean) => void;
  onSaveSafety: () => void;
};

const SECTIONS: { id: AppSettingsSection; label: string; icon: ReactNode }[] = [
  { id: "account", label: "Account", icon: <User size={16} color={C.tx1} /> },
  { id: "devices", label: "Devices", icon: <Monitor size={16} color={C.tx1} /> },
  { id: "appearance", label: "Appearance", icon: <Palette size={16} color={C.tx1} /> },
  { id: "chat", label: "Chat", icon: <MessageSquare size={16} color={C.tx1} /> },
  { id: "safety", label: "Safety", icon: <Shield size={16} color={C.tx1} /> },
  { id: "developer", label: "Developer", icon: <Code size={16} color={C.tx1} /> }
];

export function AppSettingsModal({
  visible,
  section,
  accessToken,
  devices,
  projects,
  activeDevice,
  capabilities,
  actionMessage,
  sandboxDraft,
  approvalPolicyDraft,
  webSearchDraft,
  planModeDraft,
  onClose,
  onSectionChange,
  onRefreshWorkspace,
  onRefreshCapabilities,
  onMobileLogout,
  onCodexLogout,
  onOpenDebug,
  onSandboxChange,
  onApprovalPolicyChange,
  onWebSearchChange,
  onPlanModeChange,
  onSaveSafety
}: Props) {
  const { preferences, updatePreferences, t } = usePreferences();
  const [apiUrlDraft, setApiUrlDraft] = useState(preferences.apiUrl);
  const [apiStatus, setApiStatus] = useState("");

  useEffect(() => {
    if (visible) {
      setApiUrlDraft(preferences.apiUrl);
      setApiStatus("");
    }
  }, [preferences.apiUrl, visible]);

  async function saveApiUrl() {
    await updatePreferences({ apiUrl: apiUrlDraft });
    setApiStatus("Saved.");
  }

  async function handleTestApi() {
    setApiStatus("Testing...");
    try {
      const result = await testApiConnection(apiUrlDraft);
      setApiStatus(result.ok ? `Connected (${result.status})` : `Error (${result.status})`);
    } catch (err) {
      setApiStatus(err instanceof Error ? err.message : "Failed.");
    }
  }

  const activeSection = SECTIONS.find((item) => item.id === section);

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={styles.root}>
        <View style={styles.header}>
          <View>
            <Text style={styles.headerEyebrow}>DevLink</Text>
            <Text style={styles.headerTitle}>Settings</Text>
          </View>
          <Pressable style={styles.closeBtn} onPress={onClose} hitSlop={8}>
            <X size={16} color={C.tx1} />
          </Pressable>
        </View>

        {actionMessage ? (
          <View style={styles.banner}>
            <Text style={styles.bannerText}>{actionMessage}</Text>
          </View>
        ) : null}

        <View style={styles.body}>
          <View style={styles.nav}>
            {SECTIONS.map((item) => {
              const active = section === item.id;
              return (
                <Pressable
                  key={item.id}
                  style={[styles.navItem, active && styles.navItemActive]}
                  onPress={() => onSectionChange(item.id)}
                >
                  <View style={styles.navIcon}>{item.icon}</View>
                  <Text style={[styles.navLabel, active && styles.navLabelActive]} numberOfLines={1}>
                    {item.label}
                  </Text>
                  {active ? <ChevronRight size={13} color={C.tx2} /> : null}
                </Pressable>
              );
            })}
          </View>

          <ScrollView style={styles.content} contentContainerStyle={styles.contentInner} showsVerticalScrollIndicator={false}>
            {activeSection ? <Text style={styles.sectionTitle}>{activeSection.label}</Text> : null}

            {section === "account" ? (
              <View style={styles.stack}>
                <SettingCard>
                  <SettingRow label="Mobile session" description="Log out of this mobile app">
                    <DangerButton label="Logout" onPress={onMobileLogout} />
                  </SettingRow>
                  <SettingRow label="Local CLI auth" description="Remove Codex auth token from your laptop">
                    <SecondaryButton label="Logout CLI" onPress={onCodexLogout} />
                  </SettingRow>
                </SettingCard>
              </View>
            ) : null}

            {section === "devices" ? (
              <PairingPanel
                accessToken={accessToken}
                devices={devices}
                projects={projects}
                activeDevice={activeDevice}
                capabilities={capabilities}
                onRefreshWorkspace={onRefreshWorkspace}
                onRefreshCapabilities={onRefreshCapabilities}
              />
            ) : null}

            {section === "appearance" ? (
              <View style={styles.stack}>
                <SettingCard>
                  <SegmentRow
                    label={t("settings.language")}
                    value={preferences.language}
                    options={[
                      ["pl", "Polski"],
                      ["en", "English"]
                    ]}
                    onChange={(value) => updatePreferences({ language: value as "pl" | "en" })}
                  />
                  <SegmentRow
                    label={t("settings.theme")}
                    value={preferences.theme}
                    options={[
                      ["dark", "Dark"],
                      ["oled", "OLED"]
                    ]}
                    onChange={(value) => updatePreferences({ theme: value as "dark" | "oled" })}
                  />
                  <SegmentRow
                    label={t("settings.density")}
                    value={preferences.density}
                    options={[
                      ["comfortable", "Comfortable"],
                      ["compact", "Compact"]
                    ]}
                    onChange={(value) => updatePreferences({ density: value as "comfortable" | "compact" })}
                  />
                </SettingCard>
              </View>
            ) : null}

            {section === "chat" ? (
              <View style={styles.stack}>
                <SettingCard>
                  <SegmentRow
                    label={t("settings.runLog")}
                    value={preferences.runLogDefault}
                    options={[
                      ["collapsed", "Collapsed"],
                      ["expanded", "Expanded"]
                    ]}
                    onChange={(value) => updatePreferences({ runLogDefault: value as "collapsed" | "expanded" })}
                  />
                  <SegmentRow
                    label={t("settings.startBehavior")}
                    value={preferences.startBehavior}
                    options={[
                      ["last-chat", "Last chat"],
                      ["new-chat", "New chat"]
                    ]}
                    onChange={(value) => updatePreferences({ startBehavior: value as "last-chat" | "new-chat" })}
                  />
                  <SwitchSettingRow
                    label={t("settings.autoRefresh")}
                    description="Refresh capabilities on app start"
                    value={preferences.autoRefreshCapabilities}
                    onChange={(value) => updatePreferences({ autoRefreshCapabilities: value })}
                  />
                </SettingCard>
              </View>
            ) : null}

            {section === "safety" ? (
              <View style={styles.stack}>
                <SettingCard>
                  <SegmentRow
                    label="Sandbox"
                    value={sandboxDraft}
                    options={[
                      ["read-only", "Read only"],
                      ["workspace-write", "Write"],
                      ["danger-full-access", "Full access"]
                    ]}
                    onChange={onSandboxChange}
                  />
                  <SegmentRow
                    label="Approval policy"
                    value={approvalPolicyDraft}
                    options={[
                      ["untrusted", "Untrusted"],
                      ["on-request", "On request"],
                      ["never", "Never"]
                    ]}
                    onChange={onApprovalPolicyChange}
                  />
                  <SwitchSettingRow label="Web search" value={webSearchDraft} onChange={onWebSearchChange} />
                  <SwitchSettingRow label="Planning mode" value={planModeDraft} onChange={onPlanModeChange} />
                </SettingCard>
                <Text style={styles.hint}>Full access and approval=never go through approval flow before execution.</Text>
                <Pressable style={styles.saveBtn} onPress={onSaveSafety}>
                  <Text style={styles.saveBtnText}>Save safety settings</Text>
                </Pressable>
              </View>
            ) : null}

            {section === "developer" ? (
              <View style={styles.stack}>
                <SettingCard>
                  <View style={styles.fieldBlock}>
                    <Text style={styles.fieldLabel}>{t("settings.apiUrl")}</Text>
                    <TextInput
                      style={styles.input}
                      value={apiUrlDraft}
                      onChangeText={setApiUrlDraft}
                      autoCapitalize="none"
                      autoCorrect={false}
                      placeholder="http://127.0.0.1:8000/api"
                      placeholderTextColor={C.tx2}
                    />
                    <View style={styles.fieldActions}>
                      <Pressable style={styles.fieldBtn} onPress={handleTestApi}>
                        <Text style={styles.fieldBtnText}>Test</Text>
                      </Pressable>
                      <Pressable style={[styles.fieldBtn, styles.fieldBtnPrimary]} onPress={saveApiUrl}>
                        <Text style={[styles.fieldBtnText, styles.fieldBtnPrimaryText]}>Save</Text>
                      </Pressable>
                    </View>
                    {apiStatus ? <Text style={styles.apiStatus}>{apiStatus}</Text> : null}
                  </View>
                </SettingCard>

                <SettingCard>
                  <SettingRow label="Developer console" description="Inspect events, capabilities, and diagnostics">
                    <SecondaryButton label="Open" onPress={onOpenDebug} />
                  </SettingRow>
                </SettingCard>

                <SettingCard>
                  <Text style={styles.capLine}>
                    {(capabilities.skills || []).length} skills · {(capabilities.installed_plugins || capabilities.plugins || []).length} plugins · {(capabilities.mcp_servers || []).length} MCP
                  </Text>
                  {Object.entries(capabilities.diagnostics || {}).slice(0, 8).map(([key, value]) => (
                    <View key={key} style={styles.diagRow}>
                      <Text style={styles.diagKey}>{key}</Text>
                      <Text style={styles.diagVal} numberOfLines={1}>{String(value)}</Text>
                    </View>
                  ))}
                </SettingCard>
              </View>
            ) : null}
          </ScrollView>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

function SettingCard({ children }: { children: ReactNode }) {
  return <View style={styles.card}>{children}</View>;
}

function SettingRow({ label, description, children }: { label: string; description?: string; children: ReactNode }) {
  return (
    <View style={styles.settingRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.settingRowLabel}>{label}</Text>
        {description ? <Text style={styles.settingRowDesc}>{description}</Text> : null}
      </View>
      {children}
    </View>
  );
}

function SegmentRow({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <View style={styles.segmentBlock}>
      <Text style={styles.segmentLabel}>{label}</Text>
      <View style={styles.segmentRow}>
        {options.map(([optionValue, labelText]) => {
          const active = value === optionValue;
          return (
            <Pressable
              key={optionValue}
              style={[styles.segmentChip, active && styles.segmentChipActive]}
              onPress={() => onChange(optionValue)}
            >
              {active ? <Check size={11} color={C.bg0} /> : null}
              <Text style={[styles.segmentChipText, active && styles.segmentChipTextActive]}>{labelText}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function SwitchSettingRow({
  label,
  description,
  value,
  onChange
}: {
  label: string;
  description?: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <View style={styles.switchRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.settingRowLabel}>{label}</Text>
        {description ? <Text style={styles.settingRowDesc}>{description}</Text> : null}
      </View>
      <Switch value={value} onValueChange={onChange} trackColor={{ true: C.ac1 }} />
    </View>
  );
}

function DangerButton({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable style={styles.dangerBtn} onPress={onPress}>
      <Text style={styles.dangerBtnText}>{label}</Text>
    </Pressable>
  );
}

function SecondaryButton({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable style={styles.secondaryBtn} onPress={onPress}>
      <Text style={styles.secondaryBtnText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg0 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: C.bd0
  },
  headerEyebrow: { color: C.tx2, fontSize: 11, fontWeight: "700", letterSpacing: 1, textTransform: "uppercase" },
  headerTitle: { color: C.tx0, fontSize: 24, fontWeight: "700", marginTop: 2 },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: C.bg2,
    alignItems: "center",
    justifyContent: "center"
  },
  banner: { backgroundColor: "#0a2a1a", borderBottomWidth: 1, borderBottomColor: "#1a4a2a", paddingHorizontal: 16, paddingVertical: 10 },
  bannerText: { color: "#6ee7b7", fontSize: 13 },
  body: { flex: 1, flexDirection: "row" },
  nav: { width: 120, borderRightWidth: 1, borderRightColor: C.bd0, paddingVertical: 12 },
  navItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
    borderRadius: 8,
    marginHorizontal: 6,
    marginBottom: 2
  },
  navItemActive: { backgroundColor: C.bg2 },
  navIcon: { width: 20, alignItems: "center" },
  navLabel: { flex: 1, color: C.tx1, fontSize: 13, fontWeight: "500" },
  navLabelActive: { color: C.tx0 },
  content: { flex: 1 },
  contentInner: { padding: 16, paddingBottom: 40 },
  sectionTitle: { color: C.tx0, fontSize: 20, fontWeight: "700", marginBottom: 16 },
  stack: { gap: 12 },
  card: { backgroundColor: C.bg2, borderRadius: 12, borderWidth: 1, borderColor: C.bd1, overflow: "hidden" },
  settingRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: C.bd0
  },
  settingRowLabel: { color: C.tx0, fontSize: 14, fontWeight: "500" },
  settingRowDesc: { color: C.tx2, fontSize: 12, marginTop: 2 },
  segmentBlock: { paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: C.bd0 },
  segmentLabel: { color: C.tx1, fontSize: 12, fontWeight: "600", marginBottom: 10 },
  segmentRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  segmentChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderWidth: 1,
    borderColor: C.bd2,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 7
  },
  segmentChipActive: { backgroundColor: C.tx0, borderColor: C.tx0 },
  segmentChipText: { color: C.tx1, fontSize: 13, fontWeight: "600" },
  segmentChipTextActive: { color: C.bg0 },
  switchRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: C.bd0
  },
  hint: { color: C.tx2, fontSize: 12, lineHeight: 18, paddingHorizontal: 4 },
  saveBtn: { backgroundColor: C.tx0, borderRadius: 10, paddingVertical: 14, alignItems: "center" },
  saveBtnText: { color: C.bg0, fontSize: 15, fontWeight: "700" },
  fieldBlock: { padding: 16 },
  fieldLabel: { color: C.tx1, fontSize: 12, fontWeight: "600", marginBottom: 8 },
  input: {
    borderWidth: 1,
    borderColor: C.bd2,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: C.tx0,
    backgroundColor: C.bg3,
    fontSize: 14
  },
  fieldActions: { flexDirection: "row", gap: 8, marginTop: 10 },
  fieldBtn: { flex: 1, borderWidth: 1, borderColor: C.bd2, borderRadius: 8, paddingVertical: 9, alignItems: "center" },
  fieldBtnText: { color: C.tx0, fontSize: 13, fontWeight: "600" },
  fieldBtnPrimary: { backgroundColor: C.tx0, borderColor: C.tx0 },
  fieldBtnPrimaryText: { color: C.bg0 },
  apiStatus: { color: C.tx2, fontSize: 12, marginTop: 8 },
  capLine: { paddingHorizontal: 16, paddingVertical: 12, color: C.tx1, fontSize: 13, borderBottomWidth: 1, borderBottomColor: C.bd0 },
  diagRow: { flexDirection: "row", paddingHorizontal: 16, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: C.bd0, gap: 12 },
  diagKey: { color: C.tx2, fontSize: 12, flex: 1 },
  diagVal: { color: C.tx1, fontSize: 12, flex: 2, textAlign: "right" },
  dangerBtn: { backgroundColor: "#3f1d1d", borderWidth: 1, borderColor: "#7f1d1d", borderRadius: 8, paddingHorizontal: 14, paddingVertical: 8 },
  dangerBtnText: { color: "#fca5a5", fontSize: 13, fontWeight: "700" },
  secondaryBtn: { borderWidth: 1, borderColor: C.bd2, borderRadius: 8, paddingHorizontal: 14, paddingVertical: 8 },
  secondaryBtnText: { color: C.tx0, fontSize: 13, fontWeight: "600" }
});
