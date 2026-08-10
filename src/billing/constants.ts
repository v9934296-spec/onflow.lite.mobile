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

/** One-time Re-Up pack Store product id (must match ONFLOW_RC_PRODUCT_REUP_PACK). */
export const RC_PRODUCT_REUP = "onflow_reup_pack_399";

/** Fallback identifiers when looking up the Re-Up Store product. */
export const RC_PRODUCT_REUP_ALIASES = [
  RC_PRODUCT_REUP,
  "reup",
  "re_up",
  "re-up",
  "onflow_reup_pack",
] as const;

export const PAYWALL_ROUTE = "/paywall" as const;
export const PAYWALL_REUP_ROUTE = "/paywall?mode=reup" as const;
