import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Button, FlatList, StyleSheet, Text, View } from "react-native";
import { cancelTask, fetchTask, fetchTaskEvents, Task, TaskEvent } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { AppStackParamList } from "../navigation/AppNavigator";

type Props = NativeStackScreenProps<AppStackParamList, "History">;

const TERMINAL_STATUSES = new Set(["succeeded", "failed", "timed_out", "canceled"]);
const CANCELABLE_STATUSES = new Set(["queued", "claimed", "running"]);

export function HistoryScreen({ route }: Props) {
  const { accessToken } = useAuth();
  const [task, setTask] = useState<Task | null>(null);
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCanceling, setIsCanceling] = useState(false);
  const [error, setError] = useState("");
  const lastSequenceRef = useRef(0);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setError("");
    try {
      const nextTask = await fetchTask(accessToken, route.params.taskId);
      const nextEvents = await fetchTaskEvents(accessToken, route.params.taskId, lastSequenceRef.current);
      setTask(nextTask);
      if (nextEvents.length > 0) {
        lastSequenceRef.current = Math.max(...nextEvents.map((event) => event.sequence), lastSequenceRef.current);
        setEvents((current) => [...current, ...nextEvents]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie pobrac historii.");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, route.params.taskId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (task && TERMINAL_STATUSES.has(task.status)) return;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [load, task]);

  async function handleCancel() {
    if (!accessToken || !task) return;
    setIsCanceling(true);
    setError("");
    try {
      const canceledTask = await cancelTask(accessToken, task.id);
      setTask(canceledTask);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie anulowac zadania.");
    } finally {
      setIsCanceling(false);
    }
  }

  const canCancel = Boolean(task && CANCELABLE_STATUSES.has(task.status));

  return (
    <View style={styles.container}>
      <View style={styles.actions}>
        <Button title="Odswiez" onPress={load} />
        <Button title="Anuluj" onPress={handleCancel} disabled={!canCancel || isCanceling} color="#b91c1c" />
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {isLoading && !task ? (
        <ActivityIndicator />
      ) : (
        <>
          <View style={styles.summary}>
            <Text style={styles.status}>Status: {task?.status ?? "-"}</Text>
            {task?.exit_code !== null && task?.exit_code !== undefined ? (
              <Text style={styles.meta}>Exit code: {task.exit_code}</Text>
            ) : null}
            {task?.error_code ? <Text style={styles.error}>Error: {task.error_code}</Text> : null}
            {task?.error_message ? <Text style={styles.error}>{task.error_message}</Text> : null}
          </View>
          {task?.final_output ? <Text style={styles.finalOutput}>{task.final_output}</Text> : null}
          <FlatList
            data={events}
            keyExtractor={(item) => item.id}
            renderItem={({ item }) => (
              <View style={[styles.event, item.event_type === "stderr" || item.event_type === "error" ? styles.errorEvent : null]}>
                <Text style={styles.eventType}>#{item.sequence} {item.event_type}</Text>
                <Text style={styles.message}>{item.message || JSON.stringify(item.payload)}</Text>
              </View>
            )}
          />
        </>
      )}
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
  summary: {
    padding: 12,
    borderRadius: 8,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#d1d5db",
    gap: 4
  },
  status: {
    fontSize: 18,
    fontWeight: "700",
    color: "#111827"
  },
  meta: {
    color: "#374151"
  },
  finalOutput: {
    padding: 12,
    borderRadius: 8,
    backgroundColor: "#ecfdf5",
    color: "#064e3b"
  },
  event: {
    padding: 12,
    borderRadius: 8,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    marginBottom: 8
  },
  errorEvent: {
    borderColor: "#fecaca",
    backgroundColor: "#fef2f2"
  },
  eventType: {
    fontWeight: "700",
    color: "#374151"
  },
  message: {
    color: "#111827",
    marginTop: 6
  },
  error: {
    color: "#b91c1c"
  }
});
