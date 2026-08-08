import React from "react";
import { View, Text, StyleSheet, useWindowDimensions } from "react-native";
import Svg, { Polyline, Circle, Line as SvgLine, Text as SvgText } from "react-native-svg";
import { C, F, RADIUS } from "./theme";
import { BreakdownItem } from "./types";

const CHART_H = 132;
const PAD_L = 28;
const PAD_R = 36;
const PAD_T = 12;
const PAD_B = 22;

function sessionLabel(i: number): string {
  return `S${String(i + 1).padStart(2, "0")}`;
}

/** PTE / session telemetry — paint stroke, latest marker only, S01 labels. */
export function RatingLine({ ratings, width }: { ratings: number[]; width?: number }) {
  const { width: screenW } = useWindowDimensions();
  const CHART_W = width ?? Math.max(280, screenW - 48);
  const innerW = CHART_W - PAD_L - PAD_R;
  const innerH = CHART_H - PAD_T - PAD_B;
  const n = ratings.length;

  const x = (i: number) => PAD_L + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const y = (v: number) => PAD_T + innerH - (v / 10) * innerH;

  const points = ratings.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const last = n > 0 ? ratings[n - 1]! : null;
  const lastI = n - 1;

  return (
    <Svg width={CHART_W} height={CHART_H} viewBox={`0 0 ${CHART_W} ${CHART_H}`}>
      {[0, 5, 10].map((tick) => (
        <React.Fragment key={tick}>
          <SvgLine
            x1={PAD_L}
            x2={CHART_W - PAD_R}
            y1={y(tick)}
            y2={y(tick)}
            stroke={C.charcoal4}
            strokeWidth={1}
            opacity={tick === 5 ? 0.55 : 0.35}
          />
          <SvgText x={4} y={y(tick) + 3} fill={C.dim} fontSize={9} fontFamily={F.mono}>
            {tick}
          </SvgText>
        </React.Fragment>
      ))}

      {ratings.map((_, i) => (
        <SvgLine
          key={`tick-${i}`}
          x1={x(i)}
          x2={x(i)}
          y1={PAD_T + innerH}
          y2={PAD_T + innerH + 4}
          stroke={C.charcoal5}
          strokeWidth={1}
        />
      ))}

      {n > 1 ? (
        <Polyline
          points={points}
          fill="none"
          stroke={C.volt}
          strokeWidth={2.75}
          strokeLinejoin="miter"
          strokeLinecap="butt"
        />
      ) : null}

      {last != null && lastI >= 0 ? (
        <>
          <Circle cx={x(lastI)} cy={y(last)} r={3.5} fill={C.volt} />
          <SvgText
            x={x(lastI) + 8}
            y={y(last) + 4}
            fill={C.offwhite}
            fontSize={11}
            fontFamily={F.monoBold}
          >
            {last.toFixed(1)}
          </SvgText>
        </>
      ) : null}

      {ratings.map((_, i) => (
        <SvgText
          key={`lbl-${i}`}
          x={x(i) - 10}
          y={CHART_H - 4}
          fill={i === lastI ? C.offwhite : C.dim}
          fontSize={9}
          fontFamily={F.mono}
        >
          {sessionLabel(i)}
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
  barTrack: {
    flex: 1,
    height: 6,
    backgroundColor: C.charcoal3,
    borderRadius: RADIUS.xs,
    overflow: "hidden",
  },
  barFill: { height: "100%", borderRadius: RADIUS.xs },
  barValue: { fontFamily: F.mono, fontSize: 10, color: C.dim, width: 26, textAlign: "right" },
});
