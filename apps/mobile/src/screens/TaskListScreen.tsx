import { useFocusEffect } from "@react-navigation/native";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import { ActivityIndicator, Button, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { Device, fetchDevices, fetchProjects, fetchTasks, Paginated, Project, Task } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { AppStackParamList } from "../navigation/AppNavigator";

type Props = NativeStackScreenProps<AppStackParamList, "TaskList">;

const STATUS_FILTERS = ["", "queued", "running", "succeeded", "failed", "timed_out", "canceled"];
const AGENT_FILTERS = ["", "codex", "shell"];

export function TaskListScreen({ navigation, route }: Props) {
  const { accessToken } = useAuth();
  const [tasks, setTasks] = useState<Paginated<Task> | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [deviceFilter, setDeviceFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState(route.params?.sessionId ? "" : "");
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!accessToken) return;
    setIsLoading(true);
    setError("");
    try {
      const [nextTasks, nextDevices, nextProjects] = await Promise.all([
        fetchTasks(accessToken, {
          status: statusFilter,
          agent_type: agentFilter,
          device: route.params?.sessionId ? "" : deviceFilter,
          project: route.params?.sessionId ? "" : projectFilter,
          session: route.params?.sessionId,
          ordering: "-created_at",
          page
        }),
        fetchDevices(accessToken),
        fetchProjects(accessToken)
      ]);
      setTasks(nextTasks);
      setDevices(nextDevices);
      setProjects(nextProjects);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie pobrac historii zadan.");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, agentFilter, deviceFilter, page, projectFilter, route.params?.sessionId, statusFilter]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  function setFilter(update: () => void) {
    setPage(1);
    update();
  }

  const title = route.params?.title || "Historia zadan";

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{title}</Text>
        <Button title="Odswiez" onPress={load} />
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Text style={styles.filterTitle}>Status</Text>
      <View style={styles.chips}>
        {STATUS_FILTERS.map((status) => (
          <FilterChip
            key={status || "all"}
            label={status || "wszystkie"}
            active={statusFilter === status}
            onPress={() => setFilter(() => setStatusFilter(status))}
          />
        ))}
      </View>

      <Text style={styles.filterTitle}>Agent</Text>
      <View style={styles.chips}>
        {AGENT_FILTERS.map((agent) => (
          <FilterChip
            key={agent || "all"}
            label={agent || "wszyscy"}
            active={agentFilter === agent}
            onPress={() => setFilter(() => setAgentFilter(agent))}
          />
        ))}
      </View>

      {!route.params?.sessionId ? (
        <>
          <Text style={styles.filterTitle}>Komputer</Text>
          <View style={styles.chips}>
            <FilterChip label="wszystkie" active={!deviceFilter} onPress={() => setFilter(() => setDeviceFilter(""))} />
            {devices.map((device) => (
              <FilterChip
                key={device.id}
                label={device.name}
                active={deviceFilter === device.id}
                onPress={() => setFilter(() => setDeviceFilter(device.id))}
              />
            ))}
          </View>

          <Text style={styles.filterTitle}>Projekt</Text>
          <View style={styles.chips}>
            <FilterChip label="wszystkie" active={!projectFilter} onPress={() => setFilter(() => setProjectFilter(""))} />
            {projects.map((project) => (
              <FilterChip
                key={project.id}
                label={project.name}
                active={projectFilter === project.id}
                onPress={() => setFilter(() => setProjectFilter(project.id))}
              />
            ))}
          </View>
        </>
      ) : null}

      {isLoading && !tasks ? (
        <ActivityIndicator />
      ) : tasks && tasks.results.length === 0 ? (
        <EmptyState title="Brak zadan" message="Nie ma jeszcze zadan dla wybranych filtrow." />
      ) : (
        <FlatList
          data={tasks?.results ?? []}
          keyExtractor={(item) => item.id}
          ListHeaderComponent={tasks ? <Text style={styles.count}>Wyniki: {tasks.count}</Text> : null}
          renderItem={({ item }) => (
            <Pressable style={styles.taskRow} onPress={() => navigation.navigate("History", { taskId: item.id })}>
              <Text style={styles.taskTitle}>{item.project_name} - {item.status}</Text>
              <Text style={styles.meta}>{item.agent_type} / {item.device_name}</Text>
              {item.session_title ? <Text style={styles.meta}>Sesja: {item.session_title}</Text> : null}
              <Text style={styles.prompt} numberOfLines={3}>{item.prompt}</Text>
            </Pressable>
          )}
        />
      )}

      <View style={styles.pager}>
        <Button title="Poprzednia" disabled={!tasks?.previous || page <= 1} onPress={() => setPage((current) => Math.max(1, current - 1))} />
        <Text style={styles.page}>Strona {page}</Text>
        <Button title="Nastepna" disabled={!tasks?.next} onPress={() => setPage((current) => current + 1)} />
      </View>
    </View>
  );
}

function FilterChip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable style={[styles.chip, active ? styles.activeChip : null]} onPress={onPress}>
      <Text style={[styles.chipText, active ? styles.activeChipText : null]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: "#f8fafc",
    gap: 8
  },
  header: {
    gap: 8
  },
  title: {
    fontSize: 20,
    fontWeight: "800",
    color: "#111827"
  },
  filterTitle: {
    fontWeight: "700",
    color: "#374151"
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  chip: {
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 7,
    backgroundColor: "#ffffff"
  },
  activeChip: {
    borderColor: "#2563eb",
    backgroundColor: "#eff6ff"
  },
  chipText: {
    color: "#374151",
    fontWeight: "600"
  },
  activeChipText: {
    color: "#1d4ed8"
  },
  count: {
    color: "#6b7280",
    marginBottom: 8
  },
  taskRow: {
    padding: 12,
    borderRadius: 8,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    marginBottom: 8,
    gap: 5
  },
  taskTitle: {
    fontWeight: "800",
    color: "#111827"
  },
  meta: {
    color: "#374151"
  },
  prompt: {
    color: "#111827"
  },
  pager: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8
  },
  page: {
    color: "#374151",
    fontWeight: "700"
  },
  error: {
    color: "#b91c1c"
  }
});
