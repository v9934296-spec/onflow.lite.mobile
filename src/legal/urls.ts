export const LEGAL_BASE = (
  process.env.EXPO_PUBLIC_LEGAL_BASE_URL?.trim().replace(/\/$/, "") ||
  "https://onflow-legal.pages.dev"
);

export const PRIVACY_URL = `${LEGAL_BASE}/privacy`;
export const TERMS_URL = `${LEGAL_BASE}/terms`;
export const DELETE_ACCOUNT_INFO_URL = `${LEGAL_BASE}/delete-account`;
