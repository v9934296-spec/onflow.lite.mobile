import { describe, expect, it } from "vitest";

import { RC_ENTITLEMENT_PRO } from "../../billing/constants";
import { hasActiveProEntitlement, resolveOfferingPackages } from "../../billing/entitlements";

describe("hasActiveProEntitlement", () => {
  it("detects onflow-lite Pro entitlement", () => {
    expect(hasActiveProEntitlement(null)).toBe(false);
    expect(hasActiveProEntitlement({ entitlements: { active: {} } })).toBe(false);
    expect(
      hasActiveProEntitlement({
        entitlements: { active: { [RC_ENTITLEMENT_PRO]: { identifier: RC_ENTITLEMENT_PRO } } },
      }),
    ).toBe(true);
  });
});

describe("resolveOfferingPackages", () => {
  it("maps lifetime / yearly / monthly by identifier or package type", () => {
    const resolved = resolveOfferingPackages({
      availablePackages: [
        { identifier: "lifetime", packageType: "LIFETIME" },
        { identifier: "$rc_annual", packageType: "ANNUAL" },
        { identifier: "monthly", packageType: "MONTHLY" },
      ],
    });
    expect(resolved.lifetime?.identifier).toBe("lifetime");
    expect(resolved.yearly?.identifier).toBe("$rc_annual");
    expect(resolved.monthly?.identifier).toBe("monthly");
  });

  it("returns nulls when offering is empty", () => {
    expect(resolveOfferingPackages(null)).toEqual({
      lifetime: null,
      yearly: null,
      monthly: null,
    });
  });
});
