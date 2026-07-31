import RevenueCatUI, { PAYWALL_RESULT } from "react-native-purchases-ui";
import type { CustomerInfo } from "react-native-purchases";

import { RC_ENTITLEMENT_PRO } from "./constants";
import {
  configureRevenueCat,
  fetchCustomerInfo,
  hasActiveProEntitlement,
  isNativeStorePlatform,
} from "./revenueCat";
import { syncCustomerInfoToBackend } from "./sync";

export type PaywallFlowResult =
  | { status: "purchased" | "restored"; customerInfo: CustomerInfo }
  | { status: "cancelled" | "error" | "not_presented" | "unsupported"; message?: string };

async function customerInfoAfterPaywall(
  result: PAYWALL_RESULT,
): Promise<PaywallFlowResult> {
  if (result === PAYWALL_RESULT.PURCHASED || result === PAYWALL_RESULT.RESTORED) {
    const customerInfo = await fetchCustomerInfo();
    await syncCustomerInfoToBackend(customerInfo);
    return {
      status: result === PAYWALL_RESULT.PURCHASED ? "purchased" : "restored",
      customerInfo,
    };
  }
  if (result === PAYWALL_RESULT.CANCELLED) return { status: "cancelled" };
  if (result === PAYWALL_RESULT.NOT_PRESENTED) return { status: "not_presented" };
  return { status: "error", message: "Paywall closed with an error." };
}

/** Present the dashboard-configured RevenueCat Paywall for the current offering. */
export async function presentProPaywall(): Promise<PaywallFlowResult> {
  if (!isNativeStorePlatform()) {
    return {
      status: "unsupported",
      message: "In-app purchases require an iOS or Android build (not web).",
    };
  }

  const ok = await configureRevenueCat();
  if (!ok) {
    return { status: "error", message: "RevenueCat failed to configure." };
  }

  try {
    const result = await RevenueCatUI.presentPaywall({ displayCloseButton: true });
    return customerInfoAfterPaywall(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not present paywall.";
    return { status: "error", message };
  }
}

/** Present paywall only when `onflow-lite Pro` is missing. */
export async function presentProPaywallIfNeeded(): Promise<PaywallFlowResult> {
  if (!isNativeStorePlatform()) {
    return {
      status: "unsupported",
      message: "In-app purchases require an iOS or Android build (not web).",
    };
  }

  const ok = await configureRevenueCat();
  if (!ok) {
    return { status: "error", message: "RevenueCat failed to configure." };
  }

  try {
    const info = await fetchCustomerInfo();
    if (hasActiveProEntitlement(info)) {
      return { status: "not_presented", message: "Already entitled to onflow-lite Pro." };
    }

    const result = await RevenueCatUI.presentPaywallIfNeeded({
      requiredEntitlementIdentifier: RC_ENTITLEMENT_PRO,
      displayCloseButton: true,
    });
    return customerInfoAfterPaywall(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not present paywall.";
    return { status: "error", message };
  }
}

/** Self-serve manage / cancel / restore UI (Pro & Enterprise RC plans). */
export async function presentCustomerCenter(): Promise<{ ok: boolean; message?: string }> {
  if (!isNativeStorePlatform()) {
    return { ok: false, message: "Customer Center requires an iOS or Android build." };
  }

  const ok = await configureRevenueCat();
  if (!ok) return { ok: false, message: "RevenueCat failed to configure." };

  try {
    await RevenueCatUI.presentCustomerCenter({
      callbacks: {
        onRestoreCompleted: ({ customerInfo }) => {
          void syncCustomerInfoToBackend(customerInfo);
        },
      },
    });
    return { ok: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not open Customer Center.";
    return { ok: false, message };
  }
}
