import React, { useEffect } from "react";
import { Stack } from "expo-router";
import {
  Rubik_400Regular,
  Rubik_500Medium,
  Rubik_700Bold,
  Rubik_800ExtraBold,
} from "@expo-google-fonts/rubik";
import { JetBrainsMono_500Medium, JetBrainsMono_700Bold } from "@expo-google-fonts/jetbrains-mono";
import { useFonts } from "expo-font";
import { View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { checkHealth, guardApiBaseUrlAtStartup } from "../src/api";
import { AccountProvider } from "../src/auth/accountContext";
import { AuthProvider } from "../src/auth/authContext";
import { PurchasesProvider } from "../src/billing";
import { SkateSessionProvider } from "../src/skateSession/skateSessionContext";
import { ApiConfigBanner } from "../src/components/ApiConfigBanner";
import { SessionProvider, useSession } from "../src/session";
import { StorageWarningBanner } from "../src/ui";
import { C } from "../src/theme";

function ApiStartupEffects() {
  useEffect(() => {
    guardApiBaseUrlAtStartup();

    if (typeof __DEV__ !== "undefined" && __DEV__) {
      void checkHealth()
        .then((result) => {
          if (result.ok) {
            console.info("[api] health check passed", result.data.status);
          } else {
            console.warn("[api] health check failed", result.error.kind, result.error.message);
          }
        })
        .catch((error) => {
          console.warn("[api] health check failed", error);
        });
    }
  }, []);

  return null;
}

function ApiConfigOverlay() {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ position: "absolute", top: insets.top, left: 0, right: 0, zIndex: 99 }}>
      <ApiConfigBanner />
    </View>
  );
}

function StorageWarningOverlay() {
  const { storageWarning, dismissStorageWarning } = useSession();
  const insets = useSafeAreaInsets();
  if (!storageWarning) return null;
  return (
    <View style={{ position: "absolute", top: insets.top + 8, left: 16, right: 16, zIndex: 100 }}>
      <StorageWarningBanner message={storageWarning} onDismiss={dismissStorageWarning} />
    </View>
  );
}

function RootLayout() {
  const { isHydrated } = useSession();

  if (!isHydrated) {
    return (
      <View style={{ flex: 1, backgroundColor: C.charcoal }}>
        <StatusBar style="light" />
      </View>
    );
  }

  return (
    <>
      <StatusBar style="light" />
      <ApiStartupEffects />
      <ApiConfigOverlay />
      <StorageWarningOverlay />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: C.charcoal },
          animation: "fade",
        }}
      />
    </>
  );
}

export default function Layout() {
  const [loaded] = useFonts({
    Rubik_400Regular,
    Rubik_500Medium,
    Rubik_700Bold,
    Rubik_800ExtraBold,
    JetBrainsMono_500Medium,
    JetBrainsMono_700Bold,
  });

  if (!loaded) return <View style={{ flex: 1, backgroundColor: C.charcoal }} />;

  return (
    <AccountProvider>
      <PurchasesProvider>
        <AuthProvider>
          <SessionProvider>
            <SkateSessionProvider>
              <RootLayout />
            </SkateSessionProvider>
          </SessionProvider>
        </AuthProvider>
      </PurchasesProvider>
    </AccountProvider>
  );
}
