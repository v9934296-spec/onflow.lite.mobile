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
import { SessionProvider } from "../src/session";
import { C } from "../src/theme";

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
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: C.charcoal },
          animation: "fade",
        }}
      />
    </SessionProvider>
  );
}
