import { useFocusEffect } from "@react-navigation/native";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import { ActivityIndicator, Button, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { AgentSession, createSession, fetchProjects, fetchSessions, Paginated, Project } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { AppStackParamList } from "../navigation/AppNavigator";

type Props = NativeStackScreenProps<AppStackParamList, "Sessions">;

const STATUS_FILTERS = ["", "open", "closed"];

export function SessionsScreen({ navigation, route }: Props) {
  const { accessToken } = useAuth();
  const [sessions, setSessions] = useState<Paginated<AgentSession> | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectFilter, setProjectFilter] = useState(route.params?.projectId || "");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!accessToken) return;
    setIsLoading(true);
    setError("");
    try {
      const [nextSessions, nextProjects] = await Promise.all([
        fetchSessions(accessToken, {
          project: projectFilter,
          status: statusFilter,
          ordering: "-last_activity_at",
          page
        }),
        fetchProjects(accessToken)
      ]);
      setSessions(nextSessions);
      setProjects(nextProjects);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie pobrac sesji.");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, page, projectFilter, statusFilter]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleCreate() {
    if (!accessToken || !projectFilter) return;
    setIsCreating(true);
    setError("");
    try {
      const session = await createSession(accessToken, projectFilter);
      navigation.navigate("SessionDetails", { sessionId: session.id });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie utworzyc sesji.");
    } finally {
      setIsCreating(false);
    }
  }

  function setFilter(update: () => void) {
    setPage(1);
    update();
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{route.params?.projectName ? `Sesje: ${route.params.projectName}` : "Sesje"}</Text>
        <Button title="Odswiez" onPress={load} />
        <Button title="Nowa sesja" onPress={handleCreate} disabled={!projectFilter || isCreating} />
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

      {!route.params?.projectId ? (
        <>
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

      {isLoading && !sessions ? (
        <ActivityIndicator />
      ) : sessions && sessions.results.length === 0 ? (
        <EmptyState title="Brak sesji" message="Utworz sesje dla projektu, zeby kontynuowac prace Codexa." />
      ) : (
        <FlatList
          data={sessions?.results ?? []}
          keyExtractor={(item) => item.id}
          ListHeaderComponent={sessions ? <Text style={styles.count}>Wyniki: {sessions.count}</Text> : null}
          renderItem={({ item }) => (
            <Pressable style={styles.sessionRow} onPress={() => navigation.navigate("SessionDetails", { sessionId: item.id })}>
              <Text style={styles.sessionTitle}>{item.title || item.project_name}</Text>
              <Text style={styles.meta}>{item.project_name} / {item.device_name}</Text>
              <Text style={styles.meta}>{item.status} - zadania: {item.task_count}</Text>
              {item.codex_session_id ? <Text style={styles.codexId}>Codex: {item.codex_session_id}</Text> : null}
            </Pressable>
          )}
        />
      )}

      <View style={styles.pager}>
        <Button title="Poprzednia" disabled={!sessions?.previous || page <= 1} onPress={() => setPage((current) => Math.max(1, current - 1))} />
        <Text style={styles.page}>Strona {page}</Text>
        <Button title="Nastepna" disabled={!sessions?.next} onPress={() => setPage((current) => current + 1)} />
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
  sessionRow: {
    padding: 12,
    borderRadius: 8,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    marginBottom: 8,
    gap: 5
  },
  sessionTitle: {
    fontWeight: "800",
    color: "#111827"
  },
  meta: {
    color: "#374151"
  },
  codexId: {
    color: "#6b7280",
    fontSize: 12
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
