import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import Purchases, { type CustomerInfo, type PurchasesOffering } from "react-native-purchases";

import { useAccount } from "../auth/accountContext";
import { presentCustomerCenter, presentProPaywall, type PaywallFlowResult } from "./paywallPresentation";
import {
  configureRevenueCat,
  fetchCurrentOffering,
  fetchCustomerInfo,
  hasActiveProEntitlement,
  identifyRevenueCatUser,
  purchasePackageByKind,
  purchaseReUpPack,
  resolveOfferingPackages,
  restorePurchases,
  resetRevenueCatUser,
} from "./revenueCat";
import type { RcPackageKind } from "./constants";
import { syncCustomerInfoToBackend } from "./sync";

type PurchasesContextValue = {
  ready: boolean;
  customerInfo: CustomerInfo | null;
  offering: PurchasesOffering | null;
  isProEntitled: boolean;
  packages: ReturnType<typeof resolveOfferingPackages>;
  refresh: () => Promise<void>;
  showPaywall: () => Promise<PaywallFlowResult>;
  showCustomerCenter: () => Promise<{ ok: boolean; message?: string }>;
  restore: () => Promise<CustomerInfo | null>;
  purchasePackage: (kind: RcPackageKind) => Promise<CustomerInfo | null>;
  purchaseReUp: () => Promise<CustomerInfo | null>;
};

const PurchasesContext = createContext<PurchasesContextValue | null>(null);

export function PurchasesProvider({ children }: { children: React.ReactNode }) {
  const { user, refreshUser } = useAccount();
  const [ready, setReady] = useState(false);
  const [customerInfo, setCustomerInfo] = useState<CustomerInfo | null>(null);
  const [offering, setOffering] = useState<PurchasesOffering | null>(null);

  const applyInfo = useCallback(async (info: CustomerInfo, syncBackend: boolean) => {
    setCustomerInfo(info);
    if (syncBackend) {
      await syncCustomerInfoToBackend(info);
      await refreshUser();
    }
  }, [refreshUser]);

  const refresh = useCallback(async () => {
    try {
      const ok = await configureRevenueCat();
      if (!ok) {
        setReady(false);
        return;
      }
      const [info, currentOffering] = await Promise.all([
        fetchCustomerInfo(),
        fetchCurrentOffering(),
      ]);
      setCustomerInfo(info);
      setOffering(currentOffering);
      setReady(true);
    } catch (error) {
      console.warn("[revenuecat] refresh failed", error);
      setReady(false);
    }
  }, []);

  // Configure + listen for entitlement changes
  useEffect(() => {
    let cancelled = false;
    const listener = (info: CustomerInfo) => {
      if (!cancelled) setCustomerInfo(info);
    };

    void (async () => {
      await configureRevenueCat();
      if (cancelled) return;
      Purchases.addCustomerInfoUpdateListener(listener);
      await refresh();
    })();

    return () => {
      cancelled = true;
      Purchases.removeCustomerInfoUpdateListener(listener);
    };
  }, [refresh]);

  // Keep RC app user id aligned with OnFlow account
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (user?.user_id) {
        const info = await identifyRevenueCatUser(user.user_id);
        if (!cancelled && info) {
          setCustomerInfo(info);
          await syncCustomerInfoToBackend(info);
        }
      } else {
        await resetRevenueCatUser();
        if (!cancelled) await refresh();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.user_id, refresh]);

  const showPaywall = useCallback(async () => {
    const result = await presentProPaywall();
    if (result.status === "purchased" || result.status === "restored") {
      await applyInfo(result.customerInfo, true);
    } else {
      await refresh();
    }
    return result;
  }, [applyInfo, refresh]);

  const showCustomerCenter = useCallback(async () => {
    const result = await presentCustomerCenter();
    try {
      const info = await fetchCustomerInfo();
      await applyInfo(info, true);
    } catch {
      await refresh();
      await refreshUser();
    }
    return result;
  }, [applyInfo, refresh, refreshUser]);

  const restore = useCallback(async () => {
    try {
      const info = await restorePurchases();
      await applyInfo(info, true);
      return info;
    } catch (error) {
      console.warn("[revenuecat] restore failed", error);
      return null;
    }
  }, [applyInfo]);

  const purchasePackage = useCallback(
    async (kind: RcPackageKind) => {
      try {
        const info = await purchasePackageByKind(kind);
        await applyInfo(info, true);
        return info;
      } catch (error) {
        console.warn("[revenuecat] purchasePackage failed", error);
        throw error;
      }
    },
    [applyInfo],
  );

  const purchaseReUp = useCallback(async () => {
    try {
      const info = await purchaseReUpPack();
      await applyInfo(info, true);
      return info;
    } catch (error) {
      console.warn("[revenuecat] purchaseReUp failed", error);
      throw error;
    }
  }, [applyInfo]);

  const value = useMemo<PurchasesContextValue>(
    () => ({
      ready,
      customerInfo,
      offering,
      isProEntitled: hasActiveProEntitlement(customerInfo),
      packages: resolveOfferingPackages(offering),
      refresh,
      showPaywall,
      showCustomerCenter,
      restore,
      purchasePackage,
      purchaseReUp,
    }),
    [
      ready,
      customerInfo,
      offering,
      refresh,
      showPaywall,
      showCustomerCenter,
      restore,
      purchasePackage,
      purchaseReUp,
    ],
  );

  return <PurchasesContext.Provider value={value}>{children}</PurchasesContext.Provider>;
}

export function usePurchases(): PurchasesContextValue {
  const ctx = useContext(PurchasesContext);
  if (!ctx) {
    throw new Error("usePurchases must be used within PurchasesProvider");
  }
  return ctx;
}
