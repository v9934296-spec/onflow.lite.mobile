import React from "react";
import { View, Text, StyleSheet } from "react-native";
import Svg, { Polyline, Circle, Line as SvgLine, Text as SvgText } from "react-native-svg";
import { C, F } from "./theme";
import { BreakdownItem } from "./types";

const CHART_W = 320;
const CHART_H = 120;
const PAD_L = 26;
const PAD_R = 12;
const PAD_T = 10;
const PAD_B = 20;

export function RatingLine({ ratings }: { ratings: number[] }) {
  const innerW = CHART_W - PAD_L - PAD_R;
  const innerH = CHART_H - PAD_T - PAD_B;
  const n = ratings.length;

  const x = (i: number) => PAD_L + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const y = (v: number) => PAD_T + innerH - (v / 10) * innerH;

  const points = ratings.map((v, i) => `${x(i)},${y(v)}`).join(" ");

  return (
    <Svg width={CHART_W} height={CHART_H}>
      {[0, 5, 10].map((tick) => (
        <React.Fragment key={tick}>
          <SvgLine
            x1={PAD_L}
            x2={CHART_W - PAD_R}
            y1={y(tick)}
            y2={y(tick)}
            stroke={C.charcoal3}
            strokeWidth={1}
            strokeDasharray="3 3"
          />
          <SvgText x={4} y={y(tick) + 4} fill={C.dim} fontSize={9} fontFamily={F.mono}>
            {tick}
          </SvgText>
        </React.Fragment>
      ))}
      {n > 1 && <Polyline points={points} fill="none" stroke={C.volt} strokeWidth={2} />}
      {ratings.map((v, i) => (
        <Circle key={i} cx={x(i)} cy={y(v)} r={4} fill={C.volt} stroke={C.charcoal} strokeWidth={2} />
      ))}
      {ratings.map((_, i) => (
        <SvgText key={i} x={x(i) - 6} y={CHART_H - 4} fill={C.dim} fontSize={9} fontFamily={F.mono}>
          C{i + 1}
        </SvgText>
      ))}
    </Svg>
  );
}

export function BreakdownBars({ items }: { items: BreakdownItem[] }) {
  return (
    <View style={{ gap: 8 }}>
      {items.map((b) => (
        <View key={b.k} style={s.barRow}>
          <Text style={s.barLabel}>{b.k}</Text>
          <View style={s.barTrack}>
            <View
              style={[
                s.barFill,
                { width: `${(b.v / 10) * 100}%`, backgroundColor: b.v < 6 ? C.red : C.volt },
              ]}
            />
          </View>
          <Text style={s.barValue}>{b.v.toFixed(1)}</Text>
        </View>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  barRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  barLabel: { fontFamily: F.mono, fontSize: 10, color: C.offwhite, width: 60 },
  barTrack: { flex: 1, height: 8, backgroundColor: C.charcoal3, borderRadius: 4, overflow: "hidden" },
  barFill: { height: "100%", borderRadius: 4 },
  barValue: { fontFamily: F.mono, fontSize: 10, color: C.dim, width: 26, textAlign: "right" },
});
