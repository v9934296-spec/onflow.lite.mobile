import React from "react";
import { Stack } from "expo-router";
import {
  useFonts,
  Archivo_400Regular,
  Archivo_700Bold,
  Archivo_800ExtraBold,
} from "@expo-google-fonts/archivo";
import { SpaceMono_400Regular } from "@expo-google-fonts/space-mono";
import { View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { SessionProvider, useSession } from "../src/session";
import { StorageWarningBanner } from "../src/ui";
import { C } from "../src/theme";

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
    Archivo_400Regular,
    Archivo_700Bold,
    Archivo_800ExtraBold,
    SpaceMono_400Regular,
  });

  if (!loaded) return <View style={{ flex: 1, backgroundColor: C.charcoal }} />;

  return (
    <SessionProvider>
      <RootLayout />
    </SessionProvider>
  );
}
