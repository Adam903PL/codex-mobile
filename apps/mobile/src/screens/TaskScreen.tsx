import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useState } from "react";
import { ActivityIndicator, Button, StyleSheet, Text, TextInput, View } from "react-native";
import { createTask } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { AppStackParamList } from "../navigation/AppNavigator";

type Props = NativeStackScreenProps<AppStackParamList, "Task">;

export function TaskScreen({ navigation, route }: Props) {
  const { accessToken } = useAuth();
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    if (!accessToken) return;
    setError("");
    setIsSubmitting(true);
    try {
      const task = await createTask(accessToken, route.params.projectId, prompt, "codex", route.params.sessionId);
      navigation.navigate("History", { taskId: task.id });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nie udało się utworzyć zadania.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.project}>{route.params.projectName}</Text>
      {route.params.sessionTitle ? <Text style={styles.session}>Sesja: {route.params.sessionTitle}</Text> : null}
      <TextInput
        style={styles.prompt}
        placeholder="Napisz prompt dla lokalnego Codex CLI"
        value={prompt}
        onChangeText={setPrompt}
        multiline
        textAlignVertical="top"
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {isSubmitting ? <ActivityIndicator /> : <Button title="Wyślij zadanie" onPress={handleSubmit} disabled={!prompt.trim()} />}
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
  project: {
    fontSize: 18,
    fontWeight: "700",
    color: "#111827"
  },
  session: {
    color: "#374151",
    fontWeight: "600"
  },
  prompt: {
    minHeight: 220,
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 8,
    padding: 12,
    backgroundColor: "#ffffff"
  },
  error: {
    color: "#b91c1c"
  }
});
