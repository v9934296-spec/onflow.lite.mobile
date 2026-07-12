/**
 * Raw EXPO_PUBLIC_API_URL from the build (EAS env or .env). Does not apply web LAN rewrite.
 */
export function getRawExpoApiUrl(): string {
  return (process.env.EXPO_PUBLIC_API_URL ?? "").trim();
}

export function isExpoApiUrlConfigured(): boolean {
  return getRawExpoApiUrl().length > 0;
}

/**
 * User-facing copy for API configuration (no fake data — connectivity only).
 */
export function missingApiBaseUserMessage(): string {
  if (typeof __DEV__ !== "undefined" && __DEV__) {
    return "API URL is not set. Add EXPO_PUBLIC_API_URL in .env and restart Expo with --clear.";
  }
  return "This build is missing the server address. Contact the team for an updated build.";
}

const STARTUP_GUARD_TAG = "[OnFlow API config]";

/**
 * Log when EXPO_PUBLIC_API_URL is missing so EAS/local misconfig is obvious at startup.
 * Call once from the root layout (skipped under test).
 */
export function guardApiBaseUrlAtStartup(): void {
  if (process.env.NODE_ENV === "test") {
    return;
  }
  if (isExpoApiUrlConfigured()) {
    if (typeof __DEV__ !== "undefined" && __DEV__) {
      console.info(STARTUP_GUARD_TAG, "EXPO_PUBLIC_API_URL", getRawExpoApiUrl());
    }
    return;
  }

  const hint =
    typeof __DEV__ !== "undefined" && __DEV__
      ? "Set EXPO_PUBLIC_API_URL in .env (see .env.example) or in the EAS dashboard for preview/production environments, then restart with `npx expo start -c`."
      : "This release build was compiled without EXPO_PUBLIC_API_URL. Rebuild with EAS environment variables configured.";

  console.error(STARTUP_GUARD_TAG, missingApiBaseUserMessage(), hint);

  if (typeof __DEV__ !== "undefined" && __DEV__) {
    console.error(
      `\n${STARTUP_GUARD_TAG} EXPO_PUBLIC_API_URL is missing.\n${missingApiBaseUserMessage()}\n${hint}\n`,
    );
  }
}
