import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Device, DeviceCapabilities, fetchDeviceCapabilities, fetchWorkspaceBootstrap, Project } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PairingPanel } from "../components/PairingPanel";
import { AppStackParamList } from "../navigation/AppNavigator";

type Props = NativeStackScreenProps<AppStackParamList, "Pairing">;

export function PairingScreen({ navigation }: Props) {
  const { accessToken } = useAuth();
  const [devices, setDevices] = useState<Device[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [capabilities, setCapabilities] = useState<DeviceCapabilities["capabilities"]>({});

  async function load() {
    if (!accessToken) return;
    const payload = await fetchWorkspaceBootstrap(accessToken);
    setDevices(payload.devices);
    setProjects(payload.projects);
    if (payload.devices[0]) {
      const nextCapabilities = await fetchDeviceCapabilities(accessToken, payload.devices[0].id);
      setCapabilities(nextCapabilities.capabilities || {});
    }
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, [accessToken]);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.notice}>Pairing now lives in App Settings. This compatibility screen uses the same panel.</Text>
        <PairingPanel
          accessToken={accessToken}
          devices={devices}
          projects={projects}
          activeDevice={devices[0] || null}
          capabilities={capabilities}
          onRefreshWorkspace={load}
          onRefreshCapabilities={load}
        />
        <Pressable style={styles.button} onPress={() => navigation.navigate("WorkspaceChat", { settingsSection: "devices" })}>
          <Text style={styles.buttonText}>Open App Settings</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#171717" },
  content: { padding: 16, gap: 14 },
  notice: { color: "#a1a1aa", backgroundColor: "#1f1f1f", borderRadius: 8, padding: 12 },
  button: { backgroundColor: "#f5f5f5", borderRadius: 8, padding: 12, alignItems: "center" },
  buttonText: { color: "#0d0d0d", fontWeight: "800" }
});
