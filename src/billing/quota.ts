/** Quota / upgrade detection for upload and analysis errors. */

export { PAYWALL_ROUTE } from "./constants";

export function isQuotaExceededMessage(message: string): boolean {
  const r = message.toLowerCase();
  return (
    r.includes("429") ||
    r.includes("quota") ||
    r.includes("rate_limit") ||
    r.includes("analysis limit") ||
    r.includes("high demand")
  );
}

export function isProTier(tier: string | null | undefined): boolean {
  if (!tier) return false;
  const t = tier.toLowerCase();
  return t === "pro" || t === "flow_plus";
}
