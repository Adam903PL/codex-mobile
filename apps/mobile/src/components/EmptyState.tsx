import { StyleSheet, Text, View } from "react-native";

type Props = {
  title: string;
  message: string;
};

export function EmptyState({ title, message }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.message}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    gap: 8
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
    color: "#111827"
  },
  message: {
    fontSize: 14,
    color: "#4b5563",
    lineHeight: 20
  }
});

