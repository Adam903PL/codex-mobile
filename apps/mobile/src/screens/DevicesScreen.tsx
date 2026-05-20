import { useFocusEffect } from "@react-navigation/native";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, Button, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { Device, fetchDevices, fetchProjects, Project } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { AppStackParamList } from "../navigation/AppNavigator";

type Props = NativeStackScreenProps<AppStackParamList, "Devices">;

export function DevicesScreen({ navigation }: Props) {
  const { accessToken, signOut } = useAuth();
  const [devices, setDevices] = useState<Device[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const projectsByDevice = useMemo(() => {
    return projects.reduce<Record<string, Project[]>>((acc, project) => {
      acc[project.device] = [...(acc[project.device] ?? []), project];
      return acc;
    }, {});
  }, [projects]);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setIsLoading(true);
    setError("");
    try {
      const [nextDevices, nextProjects] = await Promise.all([
        fetchDevices(accessToken),
        fetchProjects(accessToken)
      ]);
      setDevices(nextDevices);
      setProjects(nextProjects);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie pobrac komputerow.");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  return (
    <View style={styles.container}>
      <View style={styles.actions}>
        <Button title="Odswiez" onPress={load} />
        <Button title="Nowy kod" onPress={() => navigation.navigate("WorkspaceChat", { settingsSection: "devices" })} />
        <Button title="Historia" onPress={() => navigation.navigate("TaskList")} />
        <Button title="Sesje" onPress={() => navigation.navigate("Sessions")} />
        <Button title="Wyloguj" onPress={signOut} />
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {isLoading ? (
        <ActivityIndicator />
      ) : devices.length === 0 ? (
        <EmptyState title="Brak komputerow" message="Wygeneruj kod i sparuj lokalne CLI DevLink." />
      ) : (
        <FlatList
          data={devices}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => {
            const deviceProjects = projectsByDevice[item.id] ?? [];
            return (
              <View style={styles.deviceBlock}>
                <Pressable
                  style={styles.deviceHeader}
                  onPress={() => navigation.navigate("DeviceDetails", { deviceId: item.id })}
                >
                  <View>
                    <Text style={styles.deviceName}>{item.name}</Text>
                    <Text style={styles.deviceMeta}>
                      {item.platform || "Unknown"} - {item.status} - {item.project_count} proj.
                    </Text>
                  </View>
                  <Text style={styles.details}>Szczegoly</Text>
                </Pressable>
                {deviceProjects.map((project) => (
                  <Pressable
                    key={project.id}
                    style={styles.projectRow}
                    onPress={() => navigation.navigate("ProjectDetails", { projectId: project.id })}
                  >
                    <Text style={styles.projectName}>{project.name}</Text>
                    <Text style={styles.path}>{project.local_path}</Text>
                  </Pressable>
                ))}
              </View>
            );
          }}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: "#f8fafc"
  },
  actions: {
    gap: 8,
    marginBottom: 12
  },
  deviceBlock: {
    marginBottom: 14
  },
  deviceHeader: {
    padding: 14,
    borderRadius: 8,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#d1d5db",
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12
  },
  deviceName: {
    fontSize: 17,
    fontWeight: "700",
    color: "#111827"
  },
  deviceMeta: {
    color: "#374151",
    marginTop: 4
  },
  details: {
    color: "#2563eb",
    fontWeight: "700"
  },
  projectRow: {
    marginTop: 8,
    marginLeft: 12,
    padding: 12,
    borderRadius: 8,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#e5e7eb"
  },
  projectName: {
    fontSize: 16,
    fontWeight: "700",
    color: "#111827"
  },
  path: {
    color: "#6b7280",
    marginTop: 6,
    fontSize: 12
  },
  error: {
    color: "#b91c1c",
    marginBottom: 8
  }
});
