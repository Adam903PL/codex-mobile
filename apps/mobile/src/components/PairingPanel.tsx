import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { createPairingCode, Device, DeviceCapabilities, Project } from "../api/client";
import { usePreferences } from "../preferences/PreferencesContext";
import { T } from "../theme";

type PairingCodeState = {
  code: string;
  expires_at: string;
  created_at: string;
};

type Props = {
  accessToken: string | null;
  devices: Device[];
  projects: Project[];
  activeDevice: Device | null;
  capabilities: DeviceCapabilities["capabilities"];
  onRefreshWorkspace: () => void;
  onRefreshCapabilities: () => void;
};

export function PairingPanel({
  accessToken,
  devices,
  projects,
  activeDevice,
  capabilities,
  onRefreshWorkspace,
  onRefreshCapabilities
}: Props) {
  const { t } = usePreferences();
  const { width } = useWindowDimensions();
  const [pairing, setPairing] = useState<PairingCodeState | null>(null);
  const [now, setNow] = useState(Date.now());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const secondsLeft = useMemo(() => {
    if (!pairing) return 0;
    return Math.max(0, Math.ceil((new Date(pairing.expires_at).getTime() - now) / 1000));
  }, [now, pairing]);

  const isExpired = Boolean(pairing && secondsLeft <= 0);
  const code = pairing && !isExpired ? pairing.code : "CODE";
  const skills = capabilities.skills || [];
  const plugins = capabilities.installed_plugins || capabilities.plugins || [];
  const marketplaces = capabilities.plugin_marketplaces || [];
  const mcp = capabilities.mcp_servers || [];
  const isCompact = width < 430;

  async function handleCreateCode() {
    if (!accessToken) return;
    setIsLoading(true);
    setError("");
    try {
      setPairing(await createPairingCode(accessToken));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create pairing code.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <View style={styles.panel}>
      <View style={[styles.headerRow, isCompact && styles.headerRowCompact]}>
        <View style={styles.headerText}>
          <Text style={styles.eyebrow}>{t("settings.devices")}</Text>
          <Text style={styles.title}>{t("pairing.title")}</Text>
        </View>
        <Pressable style={styles.primaryButton} onPress={handleCreateCode} disabled={isLoading}>
          {isLoading ? <ActivityIndicator color="#0d0d0d" /> : <Text style={styles.primaryButtonText}>{t("pairing.generate")}</Text>}
        </Pressable>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <View style={styles.codeCard}>
        <Text style={styles.codeLabel}>Pairing code</Text>
        <Text style={[styles.code, isExpired ? styles.expired : null]}>{pairing ? pairing.code : "------"}</Text>
        <Text style={styles.muted}>
          {pairing
            ? isExpired
              ? t("pairing.expired")
              : `${t("pairing.expires")} ${secondsLeft}s`
            : t("pairing.hint")}
        </Text>
      </View>

      <View style={styles.commandCard}>
        <Text style={styles.sectionTitle}>{t("pairing.instructions")}</Text>
        <CommandLine value="devlink logout" />
        <CommandLine value={`devlink pair --force --code ${code} --name "Laptop"`} />
        <CommandLine value={`devlink projects add --path C:\\path\\to\\repo --name "My Project"`} />
        <CommandLine value="devlink connect" />
        <Text style={styles.muted}>Pairing connects this device to your account. Add any number of workspaces with projects add.</Text>
      </View>

      <View style={styles.actionsRow}>
        <Pressable style={styles.secondaryButton} onPress={onRefreshWorkspace}>
          <Text style={styles.secondaryButtonText}>Refresh workspaces</Text>
        </Pressable>
        <Pressable style={[styles.secondaryButton, !activeDevice && styles.secondaryButtonDisabled]} onPress={onRefreshCapabilities} disabled={!activeDevice}>
          <Text style={[styles.secondaryButtonText, !activeDevice && styles.secondaryButtonTextDisabled]}>Refresh capabilities</Text>
        </Pressable>
      </View>

      <View style={styles.infoCard}>
        <Text style={styles.sectionTitle}>Devices</Text>
        {devices.length === 0 ? <EmptyLine value={t("pairing.noDevices")} /> : null}
        {devices.map((device) => (
          <View key={device.id} style={styles.infoRow}>
            <View style={styles.infoMain}>
              <Text style={styles.infoName} numberOfLines={1}>{device.name}</Text>
              <Text style={styles.infoMeta}>{device.platform || "device"} / {device.project_count} proj.</Text>
            </View>
            <StatusPill value={device.status} active={device.id === activeDevice?.id} />
          </View>
        ))}
      </View>

      <View style={styles.infoCard}>
        <Text style={styles.sectionTitle}>Projects</Text>
        {projects.length === 0 ? <EmptyLine value={t("pairing.noProjects")} /> : null}
        {projects.map((project) => (
          <View key={project.id} style={styles.infoRow}>
            <View style={styles.infoMain}>
              <Text style={styles.infoName} numberOfLines={1}>{project.name}</Text>
              <Text style={styles.infoMeta} numberOfLines={1}>{project.local_path}</Text>
            </View>
            <StatusPill value={project.device_status} active={project.device === activeDevice?.id} />
          </View>
        ))}
      </View>

      <View style={styles.infoCard}>
        <Text style={styles.sectionTitle}>{t("pairing.inventory")}</Text>
        <Text style={styles.muted}>
          {skills.length} skills / {plugins.length} plugins / {marketplaces.length} marketplaces / {mcp.length} MCP
        </Text>
        <Text style={styles.muted}>Active device: {activeDevice ? `${activeDevice.name} (${activeDevice.status})` : "not paired"}</Text>
      </View>
    </View>
  );
}

function CommandLine({ value }: { value: string }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.commandLine} contentContainerStyle={styles.commandLineContent}>
      <Text style={styles.commandText}>{value}</Text>
    </ScrollView>
  );
}

function EmptyLine({ value }: { value: string }) {
  return <Text style={styles.emptyLine}>{value}</Text>;
}

function StatusPill({ value, active }: { value: string; active?: boolean }) {
  return (
    <View style={[styles.statusPill, active && styles.statusPillActive]}>
      <Text style={[styles.statusPillText, active && styles.statusPillTextActive]}>{active ? "active" : value || "unknown"}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { gap: T.s12 },
  headerRow: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: T.s12 },
  headerRowCompact: { flexDirection: "column", alignItems: "stretch" },
  headerText: { flex: 1, minWidth: 0 },
  eyebrow: { color: T.tx2, fontSize: T.f11, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.8 },
  title: { color: T.tx0, fontSize: T.f20, fontWeight: "800", marginTop: 2 },
  primaryButton: { minHeight: 44, backgroundColor: T.tx0, borderRadius: T.r8, paddingHorizontal: T.s14, paddingVertical: T.s10, minWidth: 136, alignItems: "center", justifyContent: "center" },
  primaryButtonText: { color: T.bg0, fontSize: T.f13, fontWeight: "800" },
  secondaryButton: { minHeight: 44, flexGrow: 1, borderWidth: 1, borderColor: T.bd2, borderRadius: T.r8, paddingHorizontal: T.s12, paddingVertical: T.s10, alignItems: "center", justifyContent: "center" },
  secondaryButtonDisabled: { opacity: 0.45 },
  secondaryButtonText: { color: T.tx0, fontSize: T.f13, fontWeight: "700" },
  secondaryButtonTextDisabled: { color: T.tx3 },
  codeCard: { borderWidth: 1, borderColor: T.bd1, borderRadius: T.r10, padding: T.s14, backgroundColor: T.bg2 },
  codeLabel: { color: T.tx2, fontSize: T.f11, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.8 },
  code: { color: T.tx0, fontSize: T.f24, fontWeight: "900", letterSpacing: 0, marginTop: T.s4 },
  expired: { color: T.tx3 },
  muted: { color: T.tx1, fontSize: T.f13, lineHeight: 19 },
  error: { color: "#fca5a5", backgroundColor: "#3f1d1d", borderWidth: 1, borderColor: "#7f1d1d", borderRadius: T.r8, padding: T.s10, fontSize: T.f13 },
  commandCard: { borderWidth: 1, borderColor: T.bd1, borderRadius: T.r10, padding: T.s12, gap: T.s8, backgroundColor: T.bg2 },
  sectionTitle: { color: T.tx0, fontSize: T.f14, fontWeight: "800", marginBottom: T.s4 },
  commandLine: { maxWidth: "100%", backgroundColor: T.bg1, borderRadius: T.r8, borderWidth: 1, borderColor: T.bd0 },
  commandLineContent: { paddingHorizontal: T.s10, paddingVertical: T.s8 },
  commandText: { color: T.tx0, fontFamily: "monospace", fontSize: T.f12 },
  actionsRow: { flexDirection: "row", flexWrap: "wrap", gap: T.s10 },
  infoCard: { borderWidth: 1, borderColor: T.bd1, borderRadius: T.r10, padding: T.s12, backgroundColor: T.bg2, gap: T.s4 },
  infoRow: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: T.s10, paddingVertical: T.s8, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: T.bd0 },
  infoMain: { flex: 1, minWidth: 0 },
  infoName: { color: T.tx0, fontSize: T.f14, fontWeight: "700" },
  infoMeta: { color: T.tx2, fontSize: T.f12, marginTop: 2 },
  statusPill: { minHeight: 28, maxWidth: 92, borderWidth: 1, borderColor: T.bd2, borderRadius: T.rFull, paddingHorizontal: T.s10, alignItems: "center", justifyContent: "center" },
  statusPillActive: { borderColor: T.ac1, backgroundColor: "#062418" },
  statusPillText: { color: T.tx2, fontSize: T.f11, fontWeight: "800" },
  statusPillTextActive: { color: T.ac1 },
  emptyLine: { color: T.tx2, fontSize: T.f13, lineHeight: 19, paddingVertical: T.s8 }
});
