import type { CustomerInfo } from "react-native-purchases";
import Purchases from "react-native-purchases";

import { syncBillingToBackend } from "../api/billingApi";
import { hasActiveProEntitlement } from "./revenueCat";

/** Push RC entitlement state to OnFlow backend after purchase / restore / identity. */
export async function syncCustomerInfoToBackend(info: CustomerInfo): Promise<boolean> {
  const hasPro = hasActiveProEntitlement(info);
  let rcAppUserId: string | null = null;
  try {
    rcAppUserId = await Purchases.getAppUserID();
  } catch {
    rcAppUserId = null;
  }

  const result = await syncBillingToBackend({
    has_pro: hasPro,
    sync_tier: hasPro ? "pro" : null,
    rc_app_user_id: rcAppUserId,
  });

  if (!result.ok) {
    console.warn("[revenuecat] billing sync failed", result.error.message);
    return false;
  }
  return true;
}
