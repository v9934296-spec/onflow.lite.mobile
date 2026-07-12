import React from "react";
import { Text, View } from "react-native";

import { isExpoApiUrlConfigured, missingApiBaseUserMessage } from "../api/config";
import { C, F } from "../theme";

/** Persistent banner when EXPO_PUBLIC_API_URL was not baked into the build. */
export function ApiConfigBanner() {
  if (isExpoApiUrlConfigured()) {
    return null;
  }

  return (
    <View
      style={{
        backgroundColor: C.amber,
        paddingVertical: 8,
        paddingHorizontal: 16,
      }}
    >
      <Text style={{ color: C.charcoal, fontFamily: F.bold, fontSize: 13 }}>API not configured</Text>
      <Text style={{ color: C.charcoal, fontFamily: F.body, fontSize: 12, marginTop: 4, lineHeight: 16 }}>
        {missingApiBaseUserMessage()}
      </Text>
    </View>
  );
}
