/**
 * Tiny Recharts sparkline used in table rows and KPI cards.
 *
 * Deterministic from the ``seed`` prop so that server-driven rows don't
 * flicker every refresh. The series is synthetic — until the backend
 * exposes per-symbol candle history, this is decorative.
 */

import { Area, AreaChart, ResponsiveContainer } from "recharts";

function mulberry32(a: number) {
  return function () {
    let t = (a += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashSeed(key: string): number {
  let h = 2166136261;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export default function Sparkline({
  seed,
  positive = true,
  points = 24,
  height = 28,
}: {
  seed: string;
  positive?: boolean;
  points?: number;
  height?: number;
}) {
  const rand = mulberry32(hashSeed(seed));
  let v = 100;
  const data: { x: number; y: number }[] = [];
  for (let i = 0; i < points; i++) {
    v += (rand() - 0.5) * 2.4 + (positive ? 0.12 : -0.12);
    data.push({ x: i, y: v });
  }
  const stroke = positive ? "#6bff9e" : "#ff5474";
  const gradId = `spark-${positive ? "up" : "dn"}-${seed.length}`;

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="y"
            stroke={stroke}
            strokeWidth={1.4}
            fill={`url(#${gradId})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
