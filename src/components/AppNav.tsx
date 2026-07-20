import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { usePathname, useRouter } from "expo-router";
import { C, F } from "../theme";

type NavItem = {
  label: "HOME" | "FEED" | "FLOW" | "PTE";
  href: string;
  match: string[];
  accent: string;
};

const ITEMS: NavItem[] = [
  { label: "HOME", href: "/", match: ["/"], accent: C.volt },
  { label: "FEED", href: "/feed", match: ["/feed"], accent: C.offwhite },
  {
    label: "FLOW",
    href: "/flow",
    match: ["/flow", "/trick", "/capture", "/analyzing", "/result", "/recap"],
    accent: C.red,
  },
  { label: "PTE", href: "/pte", match: ["/pte", "/history"], accent: C.volt },
];

export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <View style={s.wrap} accessibilityRole="tablist">
      {ITEMS.map((item) => {
        const active = item.match.some((prefix) =>
          prefix === "/" ? pathname === "/" : pathname.startsWith(prefix),
        );

        return (
          <Pressable
            key={item.href}
            accessibilityRole="tab"
            accessibilityLabel={`${item.label} tab`}
            accessibilityState={{ selected: active }}
            onPress={() => router.replace(item.href as never)}
            style={({ pressed }) => [s.item, pressed && s.pressed]}
          >
            <View style={[s.rail, active && { backgroundColor: item.accent }]} />
            <Text style={[s.label, active && { color: item.accent }]}>{item.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    backgroundColor: C.charcoal,
    borderTopWidth: 1,
    borderTopColor: C.charcoal3,
    paddingTop: 0,
    paddingBottom: 2,
  },
  item: {
    flex: 1,
    minHeight: 52,
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
  },
  rail: {
    position: "absolute",
    top: 0,
    left: 12,
    right: 12,
    height: 2,
    backgroundColor: "transparent",
  },
  label: {
    fontFamily: F.bold,
    fontSize: 10,
    letterSpacing: 1.4,
    color: C.dim,
  },
  pressed: { opacity: 0.62 },
});