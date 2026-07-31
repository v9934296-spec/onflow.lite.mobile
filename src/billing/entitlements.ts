import {
  RC_ENTITLEMENT_PRO,
  RC_PACKAGE_ALIASES,
  type RcPackageKind,
} from "./constants";

/** Minimal shapes so helpers stay testable without native Purchases. */
export type EntitlementInfoLike = {
  entitlements: {
    active: Record<string, unknown>;
  };
};

export type PackageLike = {
  identifier: string;
  packageType: string;
};

export type OfferingLike = {
  availablePackages: PackageLike[];
};

export function hasActiveProEntitlement(info: EntitlementInfoLike | null | undefined): boolean {
  if (!info) return false;
  return typeof info.entitlements.active[RC_ENTITLEMENT_PRO] !== "undefined";
}

export function getProEntitlement(info: EntitlementInfoLike | null | undefined) {
  if (!info) return undefined;
  return info.entitlements.active[RC_ENTITLEMENT_PRO];
}

function packageMatchesKind(pkg: PackageLike, kind: RcPackageKind): boolean {
  const aliases = RC_PACKAGE_ALIASES[kind];
  const id = pkg.identifier.toLowerCase();
  if (aliases.some((alias) => alias.toLowerCase() === id)) return true;

  const type = String(pkg.packageType).toUpperCase();
  if (kind === "lifetime" && type === "LIFETIME") return true;
  if (kind === "yearly" && (type === "ANNUAL" || type === "YEARLY")) return true;
  if (kind === "monthly" && type === "MONTHLY") return true;
  return false;
}

/** Resolve lifetime / yearly / monthly packages from the current (or provided) offering. */
export function resolveOfferingPackages(offering: OfferingLike | null): {
  lifetime: PackageLike | null;
  yearly: PackageLike | null;
  monthly: PackageLike | null;
} {
  const packages = offering?.availablePackages ?? [];
  const find = (kind: RcPackageKind) => packages.find((pkg) => packageMatchesKind(pkg, kind)) ?? null;
  return {
    lifetime: find("lifetime"),
    yearly: find("yearly"),
    monthly: find("monthly"),
  };
}
