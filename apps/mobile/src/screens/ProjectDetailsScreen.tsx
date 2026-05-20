import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Button, StyleSheet, Text, View } from "react-native";
import { fetchProject, Project } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { AppStackParamList } from "../navigation/AppNavigator";

type Props = NativeStackScreenProps<AppStackParamList, "ProjectDetails">;

export function ProjectDetailsScreen({ navigation, route }: Props) {
  const { accessToken } = useAuth();
  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!accessToken) return;
    setIsLoading(true);
    setError("");
    try {
      setProject(await fetchProject(accessToken, route.params.projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie pobrac projektu.");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, route.params.projectId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <View style={styles.container}>
      <Button title="Odswiez" onPress={load} />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {isLoading && !project ? (
        <ActivityIndicator />
      ) : project ? (
        <>
          <View style={styles.panel}>
            <Text style={styles.name}>{project.name}</Text>
            <Text style={styles.meta}>Komputer: {project.device_name} ({project.device_status})</Text>
            <Text style={styles.meta}>Status projektu: {project.is_active ? "aktywny" : "nieaktywny"}</Text>
            <Text style={styles.path}>{project.local_path}</Text>
          </View>
          <View style={styles.panel}>
            <Text style={styles.sectionTitle}>Ustawienia Codexa</Text>
            <Text style={styles.meta}>Model: {project.default_model || "domyslny"}</Text>
            <Text style={styles.meta}>Profil: {project.default_profile || "domyslny"}</Text>
            <Text style={styles.meta}>Sandbox: {project.default_sandbox}</Text>
            <Text style={styles.meta}>Approval: {project.default_approval_policy}</Text>
          </View>
          <Button
            title="Nowe zadanie"
            onPress={() => navigation.navigate("Task", { projectId: project.id, projectName: project.name })}
            disabled={!project.is_active || project.device_status === "revoked"}
          />
          <Button
            title="Sesje projektu"
            onPress={() => navigation.navigate("Sessions", { projectId: project.id, projectName: project.name })}
            disabled={!project.is_active || project.device_status === "revoked"}
          />
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    gap: 12,
    backgroundColor: "#f8fafc"
  },
  panel: {
    padding: 16,
    borderRadius: 8,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#d1d5db",
    gap: 6
  },
  name: {
    fontSize: 20,
    fontWeight: "800",
    color: "#111827"
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#111827"
  },
  meta: {
    color: "#374151"
  },
  path: {
    color: "#6b7280",
    fontSize: 12
  },
  error: {
    color: "#b91c1c"
  }
});
