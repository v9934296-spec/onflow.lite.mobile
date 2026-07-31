/** RevenueCat dashboard identifiers — keep in sync with offerings / entitlement. */

/** Entitlement that unlocks Pro features (exact RC identifier). */
export const RC_ENTITLEMENT_PRO = "onflow-lite Pro";

/**
 * Package identifiers on the current Offering.
 * Prefer these custom IDs; RevenueCat `$rc_*` aliases are accepted as fallbacks.
 */
export const RC_PACKAGE_IDS = {
  lifetime: "lifetime",
  yearly: "yearly",
  monthly: "monthly",
} as const;

export type RcPackageKind = keyof typeof RC_PACKAGE_IDS;

/** Common RevenueCat built-in package aliases (fallback matching). */
export const RC_PACKAGE_ALIASES: Record<RcPackageKind, readonly string[]> = {
  lifetime: ["lifetime", "$rc_lifetime", "Lifetime"],
  yearly: ["yearly", "$rc_annual", "annual", "year"],
  monthly: ["monthly", "$rc_monthly", "month"],
};

export const PAYWALL_ROUTE = "/paywall" as const;
