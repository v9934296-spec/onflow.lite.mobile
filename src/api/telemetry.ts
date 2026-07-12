import Constants from "expo-constants";
import { Platform } from "react-native";

/** Sent on authenticated OnFlow API requests for support / triage (no PII). */
export function getApiTelemetryHeaders(): Record<string, string> {
  const appVersion = Constants.expoConfig?.version ?? "unknown";
  const nativeBuild = Constants.nativeBuildVersion;
  let buildNumber: string;
  if (nativeBuild != null && String(nativeBuild).trim()) {
    buildNumber = String(nativeBuild).trim();
  } else {
    const iosBn = (Constants.expoConfig?.ios as { buildNumber?: string } | undefined)?.buildNumber;
    const androidVc = Constants.expoConfig?.android?.versionCode;
    buildNumber =
      iosBn != null && String(iosBn).trim()
        ? String(iosBn).trim()
        : androidVc != null
          ? String(androidVc)
          : "0";
  }
  return {
    "X-App-Version": appVersion,
    "X-Build-Number": buildNumber,
    "X-Platform": Platform.OS,
  };
}

export function mergeApiTelemetryHeaders(authHeaders: Record<string, string>): Record<string, string> {
  return { ...getApiTelemetryHeaders(), ...authHeaders };
}
