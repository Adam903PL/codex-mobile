import { useFocusEffect } from "@react-navigation/native";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import { ActivityIndicator, Button, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { AgentSession, closeSession, fetchSession, fetchTasks, forkSession, Task } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { AppStackParamList } from "../navigation/AppNavigator";

type Props = NativeStackScreenProps<AppStackParamList, "SessionDetails">;

export function SessionDetailsScreen({ navigation, route }: Props) {
  const { accessToken } = useAuth();
  const [session, setSession] = useState<AgentSession | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!accessToken) return;
    setIsLoading(true);
    setError("");
    try {
      const [nextSession, nextTasks] = await Promise.all([
        fetchSession(accessToken, route.params.sessionId),
        fetchTasks(accessToken, { session: route.params.sessionId, ordering: "-created_at" })
      ]);
      setSession(nextSession);
      setTasks(nextTasks.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie pobrac sesji.");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, route.params.sessionId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleClose() {
    if (!accessToken || !session) return;
    setIsBusy(true);
    setError("");
    try {
      setSession(await closeSession(accessToken, session.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie zamknac sesji.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleFork() {
    if (!accessToken || !session) return;
    setIsBusy(true);
    setError("");
    try {
      const child = await forkSession(accessToken, session.id);
      navigation.navigate("SessionDetails", { sessionId: child.id });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie utworzyc forka.");
    } finally {
      setIsBusy(false);
    }
  }

  const canContinue = Boolean(session && session.status === "open");

  return (
    <View style={styles.container}>
      <View style={styles.actions}>
        <Button title="Odswiez" onPress={load} />
        <Button
          title="Kontynuuj"
          disabled={!canContinue || isBusy}
          onPress={() => {
            if (!session) return;
            navigation.navigate("Task", {
              projectId: session.project,
              projectName: session.project_name,
              sessionId: session.id,
              sessionTitle: session.title || session.project_name
            });
          }}
        />
        <Button title="Fork" disabled={!session || isBusy} onPress={handleFork} />
        <Button title="Zamknij" disabled={!canContinue || isBusy} color="#b91c1c" onPress={handleClose} />
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      {isLoading && !session ? (
        <ActivityIndicator />
      ) : session ? (
        <>
          <View style={styles.panel}>
            <Text style={styles.title}>{session.title || session.project_name}</Text>
            <Text style={styles.meta}>Projekt: {session.project_name}</Text>
            <Text style={styles.meta}>Komputer: {session.device_name}</Text>
            <Text style={styles.meta}>Status: {session.status}</Text>
            <Text style={styles.meta}>Zadania: {session.task_count}</Text>
            {session.parent_session_title ? <Text style={styles.meta}>Fork z: {session.parent_session_title}</Text> : null}
            {session.codex_session_id ? <Text style={styles.codexId}>Codex session: {session.codex_session_id}</Text> : null}
          </View>

          {session.summary ? <Text style={styles.summary}>{session.summary}</Text> : null}

          <View style={styles.historyAction}>
            <Button
              title="Pelna historia tej sesji"
              onPress={() => navigation.navigate("TaskList", { sessionId: session.id, title: session.title || session.project_name })}
            />
          </View>

          <FlatList
            data={tasks}
            keyExtractor={(item) => item.id}
            ListEmptyComponent={<EmptyState title="Brak zadan" message="Kontynuuj sesje, zeby dodac pierwsze zadanie." />}
            renderItem={({ item }) => (
              <Pressable style={styles.taskRow} onPress={() => navigation.navigate("History", { taskId: item.id })}>
                <Text style={styles.taskTitle}>{item.status} - {item.agent_type}</Text>
                <Text style={styles.prompt} numberOfLines={3}>{item.prompt}</Text>
              </Pressable>
            )}
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
    backgroundColor: "#f8fafc",
    gap: 10
  },
  actions: {
    gap: 8
  },
  panel: {
    padding: 14,
    borderRadius: 8,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#d1d5db",
    gap: 5
  },
  title: {
    fontSize: 20,
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
  summary: {
    padding: 12,
    borderRadius: 8,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    color: "#111827"
  },
  historyAction: {
    gap: 8
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
  prompt: {
    color: "#111827"
  },
  error: {
    color: "#b91c1c"
  }
});
