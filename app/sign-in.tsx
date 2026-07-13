import * as AppleAuthentication from "expo-apple-authentication";
import { useLocalSearchParams } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { createEmailSession, signInWithApple } from "../src/api/authApi";
import { isExpoApiUrlConfigured, missingApiBaseUserMessage } from "../src/api/config";
import { useAuth } from "../src/auth/authContext";
import { saveOnflowSession } from "../src/auth/onflowSession";
import { C, F } from "../src/theme";
import { Btn, Eyebrow, Field } from "../src/ui";

const ENABLE_EMAIL_AUTH = typeof __DEV__ !== "undefined" && __DEV__;
const IS_IOS = Platform.OS === "ios";

function queryParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function isValidEmail(value: string): boolean {
  const t = value.trim();
  return t.length >= 3 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t);
}

export default function SignInScreen() {
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ reason?: string | string[] }>();
  const reason = queryParam(params.reason);
  const { completeSignIn } = useAuth();

  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [appleAvailable, setAppleAvailable] = useState(false);

  useEffect(() => {
    if (!IS_IOS) return;
    void AppleAuthentication.isAvailableAsync().then(setAppleAvailable);
  }, []);

  const finishSignIn = useCallback(
    async (session: { token: string; userId: string; email: string }) => {
      await saveOnflowSession(session);
      const ok = await completeSignIn();
      if (!ok) {
        throw new Error("Signed in but could not load your account. Try again.");
      }
    },
    [completeSignIn],
  );

  const handleApple = useCallback(async () => {
    if (busy) return;
    if (!isExpoApiUrlConfigured()) {
      setError(missingApiBaseUserMessage());
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
        ],
      });
      if (!credential.identityToken) {
        throw new Error("Apple did not return an identity token.");
      }
      const fallbackEmail = credential.email ?? undefined;
      const result = await signInWithApple(credential.identityToken, fallbackEmail);
      if (!result.ok) {
        throw new Error(result.error.message);
      }
      await finishSignIn(result.data.session);
    } catch (e) {
      const code = (e as { code?: string }).code;
      if (code === "ERR_REQUEST_CANCELED") return;
      setError(e instanceof Error ? e.message : "Apple sign-in failed.");
    } finally {
      setBusy(false);
    }
  }, [busy, finishSignIn]);

  const handleEmail = useCallback(async () => {
    if (busy) return;
    if (!isExpoApiUrlConfigured()) {
      setError(missingApiBaseUserMessage());
      return;
    }
    if (!isValidEmail(email)) {
      setError("Enter a valid email address.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const result = await createEmailSession(email);
      if (!result.ok) {
        throw new Error(result.error.message);
      }
      await finishSignIn(result.data.session);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }, [busy, email, finishSignIn]);

  const showAndroidNotice = !IS_IOS && !ENABLE_EMAIL_AUTH;

  return (
    <KeyboardAvoidingView
      style={[s.screen, { paddingTop: insets.top + 24, paddingBottom: insets.bottom + 24 }]}
      behavior={IS_IOS ? "padding" : undefined}
    >
      <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
        <View style={s.header}>
          <Eyebrow>
            <Text style={{ color: C.red }}>■ </Text>ONFLOW
          </Eyebrow>
          <Text style={s.h1}>Sign in</Text>
          <Text style={s.sub}>Your session stays on this device until you sign out.</Text>
          {reason === "session_expired" ? (
            <Text style={s.warn}>Your session expired. Sign in again to continue.</Text>
          ) : null}
          {!isExpoApiUrlConfigured() ? (
            <Text style={s.warn}>{missingApiBaseUserMessage()}</Text>
          ) : null}
          {showAndroidNotice ? (
            <Text style={s.warn}>Sign-in is available on iOS. Android support is coming soon.</Text>
          ) : null}
        </View>

        {error ? <Text style={s.error}>{error}</Text> : null}

        {appleAvailable ? (
          <View pointerEvents={busy ? "none" : "auto"} style={{ opacity: busy ? 0.45 : 1 }}>
            <AppleAuthentication.AppleAuthenticationButton
              buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
              buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.WHITE}
              cornerRadius={10}
              style={s.appleBtn}
              onPress={() => void handleApple()}
            />
          </View>
        ) : IS_IOS && !appleAvailable ? (
          <Text style={s.warn}>Apple Sign-In is not available on this device.</Text>
        ) : null}

        {ENABLE_EMAIL_AUTH ? (
          <View style={s.emailBlock}>
            <Field
              label="Email (dev only)"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              keyboardType="email-address"
              autoComplete="email"
              placeholder="you@example.com"
              editable={!busy}
            />
            <Btn label="Continue with email" onPress={() => void handleEmail()} disabled={busy} />
          </View>
        ) : null}

        {busy ? <ActivityIndicator color={C.volt} style={{ marginTop: 16 }} /> : null}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  scroll: { paddingHorizontal: 24, gap: 16 },
  header: { gap: 8, marginBottom: 8 },
  h1: { fontFamily: F.heading, fontSize: 36, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.dim },
  warn: { fontFamily: F.body, fontSize: 13, lineHeight: 18, color: C.amber, marginTop: 4 },
  error: { fontFamily: F.body, fontSize: 13, lineHeight: 18, color: C.red, textAlign: "center" },
  appleBtn: { width: "100%", height: 48 },
  emailBlock: { gap: 12, marginTop: 8 },
});
