import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Button, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { deleteDevice, DeviceDetail, fetchDevice } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { AppStackParamList } from "../navigation/AppNavigator";

type Props = NativeStackScreenProps<AppStackParamList, "DeviceDetails">;

export function DeviceDetailsScreen({ navigation, route }: Props) {
  const { accessToken } = useAuth();
  const [device, setDevice] = useState<DeviceDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!accessToken) return;
    setIsLoading(true);
    setError("");
    try {
      setDevice(await fetchDevice(accessToken, route.params.deviceId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie pobrac komputera.");
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, route.params.deviceId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDelete() {
    if (!accessToken || !device) return;
    setIsDeleting(true);
    setError("");
    try {
      await deleteDevice(accessToken, device.id);
      navigation.navigate("Devices");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udalo sie odlaczyc komputera.");
    } finally {
      setIsDeleting(false);
    }
  }

  function confirmDelete() {
    Alert.alert(
      "Odlaczyc komputer?",
      "Lokalne CLI straci dostep do zadan po kolejnym zapytaniu backendu.",
      [
        { text: "Anuluj", style: "cancel" },
        { text: "Odlacz", style: "destructive", onPress: handleDelete }
      ]
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.actions}>
        <Button title="Odswiez" onPress={load} />
        <Button title="Odlacz komputer" onPress={confirmDelete} disabled={!device || isDeleting} color="#b91c1c" />
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {isLoading && !device ? (
        <ActivityIndicator />
      ) : device ? (
        <>
          <View style={styles.summary}>
            <Text style={styles.name}>{device.name}</Text>
            <Text style={styles.meta}>Platforma: {device.platform || "Unknown"}</Text>
            <Text style={styles.meta}>Status: {device.status}</Text>
            <Text style={styles.meta}>Ostatnie polaczenie: {device.last_seen_at ?? "-"}</Text>
            <Text style={styles.meta}>Aktywne projekty: {device.project_count}</Text>
          </View>
          <FlatList
            data={device.projects}
            keyExtractor={(item) => item.id}
            ListEmptyComponent={<Text style={styles.meta}>Brak aktywnych projektow.</Text>}
            renderItem={({ item }) => (
              <Pressable
                style={styles.project}
                onPress={() => navigation.navigate("ProjectDetails", { projectId: item.id })}
              >
                <Text style={styles.projectName}>{item.name}</Text>
                <Text style={styles.path}>{item.local_path}</Text>
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
    gap: 12,
    backgroundColor: "#f8fafc"
  },
  actions: {
    gap: 8
  },
  summary: {
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
  meta: {
    color: "#374151"
  },
  project: {
    padding: 12,
    borderRadius: 8,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    marginBottom: 8
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
    color: "#b91c1c"
  }
});
