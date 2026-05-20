import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { DeviceDetailsScreen } from "../screens/DeviceDetailsScreen";
import { DevicesScreen } from "../screens/DevicesScreen";
import { HistoryScreen } from "../screens/HistoryScreen";
import { PairingScreen } from "../screens/PairingScreen";
import { ProjectDetailsScreen } from "../screens/ProjectDetailsScreen";
import { SessionDetailsScreen } from "../screens/SessionDetailsScreen";
import { SessionsScreen } from "../screens/SessionsScreen";
import { TaskListScreen } from "../screens/TaskListScreen";
import { TaskScreen } from "../screens/TaskScreen";
import { WorkspaceChatScreen } from "../screens/WorkspaceChatScreen";
import { AppSettingsSection } from "../preferences/PreferencesContext";

export type AppStackParamList = {
  WorkspaceChat: { settingsSection?: AppSettingsSection } | undefined;
  Devices: undefined;
  Pairing: undefined;
  DeviceDetails: { deviceId: string };
  ProjectDetails: { projectId: string };
  Sessions: { projectId?: string; projectName?: string } | undefined;
  SessionDetails: { sessionId: string };
  Task: { projectId: string; projectName: string; sessionId?: string; sessionTitle?: string };
  TaskList: { sessionId?: string; title?: string } | undefined;
  History: { taskId: string };
};

const Stack = createNativeStackNavigator<AppStackParamList>();

export function AppNavigator() {
  return (
    <Stack.Navigator initialRouteName="WorkspaceChat">
      <Stack.Screen name="WorkspaceChat" component={WorkspaceChatScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Devices" component={DevicesScreen} options={{ title: "Komputery i projekty" }} />
      <Stack.Screen name="Pairing" component={PairingScreen} options={{ title: "CLI pairing" }} />
      <Stack.Screen name="DeviceDetails" component={DeviceDetailsScreen} options={{ title: "Szczegoly komputera" }} />
      <Stack.Screen name="ProjectDetails" component={ProjectDetailsScreen} options={{ title: "Szczegoly projektu" }} />
      <Stack.Screen name="Sessions" component={SessionsScreen} options={{ title: "Sesje" }} />
      <Stack.Screen name="SessionDetails" component={SessionDetailsScreen} options={{ title: "Szczegoly sesji" }} />
      <Stack.Screen name="TaskList" component={TaskListScreen} options={{ title: "Historia zadan" }} />
      <Stack.Screen name="Task" component={TaskScreen} options={{ title: "Nowe zadanie" }} />
      <Stack.Screen name="History" component={HistoryScreen} options={{ title: "Historia zadania" }} />
    </Stack.Navigator>
  );
}
