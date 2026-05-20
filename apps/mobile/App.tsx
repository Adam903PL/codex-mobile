import { NavigationContainer } from "@react-navigation/native";
import { AuthProvider, useAuth } from "./src/auth/AuthContext";
import { AppNavigator } from "./src/navigation/AppNavigator";
import { AuthNavigator } from "./src/navigation/AuthNavigator";
import { PreferencesProvider, usePreferences } from "./src/preferences/PreferencesContext";

function Root() {
  const { accessToken, isLoading } = useAuth();
  const { isLoading: preferencesLoading } = usePreferences();

  if (isLoading || preferencesLoading) {
    return null;
  }

  return (
    <NavigationContainer>
      {accessToken ? <AppNavigator /> : <AuthNavigator />}
    </NavigationContainer>
  );
}

export default function App() {
  return (
    <PreferencesProvider>
      <AuthProvider>
        <Root />
      </AuthProvider>
    </PreferencesProvider>
  );
}
