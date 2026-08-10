import { Platform } from "react-native";
import Purchases, {
  LOG_LEVEL,
  PURCHASES_ERROR_CODE,
  type CustomerInfo,
  type PurchasesError,
  type PurchasesOffering,
  type PurchasesPackage,
} from "react-native-purchases";

import {
  RC_PACKAGE_IDS,
  RC_PRODUCT_REUP,
  RC_PRODUCT_REUP_ALIASES,
  type RcPackageKind,
} from "./constants";
import { resolveOfferingPackages as resolveOfferingPackagesBase } from "./entitlements";

export {
  getProEntitlement,
  hasActiveProEntitlement,
  resolveOfferingPackages,
} from "./entitlements";

/** Public SDK key (safe for client). Must be set via EXPO_PUBLIC_REVENUECAT_API_KEY. */
let configurePromise: Promise<boolean> | null = null;

export function getRevenueCatApiKey(): string {
  return (process.env.EXPO_PUBLIC_REVENUECAT_API_KEY ?? "").trim();
}

/** True when native IAP / Paywalls are expected to work (not plain web). */
export function isNativeStorePlatform(): boolean {
  return Platform.OS === "ios" || Platform.OS === "android";
}

/**
 * Configure Purchases once at app start.
 * Expo Go uses Preview API Mode (mock); real purchases need a dev/production build.
 */
export function configureRevenueCat(): Promise<boolean> {
  if (configurePromise) return configurePromise;

  configurePromise = (async () => {
    try {
      if (await Purchases.isConfigured()) return true;

      const apiKey = getRevenueCatApiKey();
      if (!apiKey) {
        console.warn("[revenuecat] Missing EXPO_PUBLIC_REVENUECAT_API_KEY");
        return false;
      }

      await Purchases.setLogLevel(__DEV__ ? LOG_LEVEL.DEBUG : LOG_LEVEL.INFO);
      Purchases.configure({ apiKey });
      return true;
    } catch (error) {
      console.warn("[revenuecat] configure failed", error);
      return false;
    }
  })();

  return configurePromise;
}

export async function fetchCustomerInfo(): Promise<CustomerInfo> {
  const ok = await configureRevenueCat();
  if (!ok) throw new Error("RevenueCat is not configured.");
  return Purchases.getCustomerInfo();
}

export async function fetchCurrentOffering(): Promise<PurchasesOffering | null> {
  const ok = await configureRevenueCat();
  if (!ok) throw new Error("RevenueCat is not configured.");
  const offerings = await Purchases.getOfferings();
  return offerings.current ?? null;
}

export async function purchasePackageByKind(kind: RcPackageKind): Promise<CustomerInfo> {
  const offering = await fetchCurrentOffering();
  if (!offering) {
    throw new Error("No current RevenueCat offering. Create an Offering with lifetime/yearly/monthly.");
  }
  const packages = resolveOfferingPackagesBase(offering);
  const selected = packages[kind] as PurchasesPackage | null;
  if (!selected) {
    throw new Error(
      `Package "${RC_PACKAGE_IDS[kind]}" not found on current offering. Check RevenueCat dashboard package IDs.`,
    );
  }
  const { customerInfo } = await Purchases.purchasePackage(selected);
  return customerInfo;
}

/** One-time +10 analyses pack (Store product, not a subscription package). */
export async function purchaseReUpPack(): Promise<CustomerInfo> {
  const ok = await configureRevenueCat();
  if (!ok) throw new Error("RevenueCat is not configured.");

  const products = await Purchases.getProducts([...RC_PRODUCT_REUP_ALIASES]);
  const product =
    products.find((p) => RC_PRODUCT_REUP_ALIASES.some((id) => id === p.identifier)) ?? products[0];
  if (!product) {
    throw new Error(
      `Re-Up product "${RC_PRODUCT_REUP}" not found. Add it in App Store Connect / Play and RevenueCat.`,
    );
  }
  const { customerInfo } = await Purchases.purchaseStoreProduct(product);
  return customerInfo;
}

export async function restorePurchases(): Promise<CustomerInfo> {
  const ok = await configureRevenueCat();
  if (!ok) throw new Error("RevenueCat is not configured.");
  return Purchases.restorePurchases();
}

/** Alias the store customer to our backend user id after sign-in. */
export async function identifyRevenueCatUser(appUserId: string): Promise<CustomerInfo | null> {
  const ok = await configureRevenueCat();
  if (!ok) return null;
  const id = appUserId.trim();
  if (!id) return null;
  try {
    const { customerInfo } = await Purchases.logIn(id);
    return customerInfo;
  } catch (error) {
    console.warn("[revenuecat] logIn failed", error);
    return null;
  }
}

/** Reset to anonymous RC user on sign-out. */
export async function resetRevenueCatUser(): Promise<void> {
  try {
    if (!(await Purchases.isConfigured())) return;
    await Purchases.logOut();
  } catch (error) {
    // Already anonymous is fine.
    console.warn("[revenuecat] logOut skipped", error);
  }
}

export function isPurchaseCancelledError(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const e = error as Partial<PurchasesError>;
  if (e.userCancelled === true) return true;
  return e.code === PURCHASES_ERROR_CODE.PURCHASE_CANCELLED_ERROR;
}

export function purchasesErrorMessage(error: unknown, fallback = "Purchase failed."): string {
  if (isPurchaseCancelledError(error)) return "Purchase cancelled.";
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}
