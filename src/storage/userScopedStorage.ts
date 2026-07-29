export function normalizeStorageUserId(userId: string | null | undefined): string | null {
  const trimmed = userId?.trim();
  return trimmed ? trimmed : null;
}

export function userScopedStorageKey(
  userId: string | null | undefined,
  domain: string,
  version = 1,
): string {
  const normalized = normalizeStorageUserId(userId);
  if (!normalized) {
    throw new Error(`Cannot access ${domain} storage without an authenticated user id`);
  }
  return `onflow.user.${encodeURIComponent(normalized)}.${domain}.v${version}`;
}
