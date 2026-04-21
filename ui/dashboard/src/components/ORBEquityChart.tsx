import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EquityPoint } from "../api";

interface Props {
  combined: EquityPoint[];
  futures: EquityPoint[];
  options: EquityPoint[];
}

function fmtINR(n: number) {
  const sign = n < 0 ? "-" : "";
  const v = Math.abs(n);
  if (v >= 1e7) return `${sign}₹${(v / 1e7).toFixed(2)}Cr`;
  if (v >= 1e5) return `${sign}₹${(v / 1e5).toFixed(2)}L`;
  if (v >= 1e3) return `${sign}₹${(v / 1e3).toFixed(1)}k`;
  return `${sign}₹${v.toFixed(0)}`;
}

export default function ORBEquityChart({ combined, futures, options }: Props) {
  // Merge into a wide form so recharts can render three layers sharing one x-axis.
  const data = combined.map((c, i) => ({
    date: c.date,
    combined: c.equity,
    futures: futures[i]?.equity ?? 0,
    options: options[i]?.equity ?? 0,
  }));

  return (
    <div className="chart-wrap" style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <defs>
            <linearGradient id="orbCombined" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--neon-green, #3af58a)" stopOpacity={0.42} />
              <stop offset="100%" stopColor="var(--neon-green, #3af58a)" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="orbFutures" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#67b3ff" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#67b3ff" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="orbOptions" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#d6a3ff" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#d6a3ff" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            stroke="rgba(200,220,255,0.35)"
            tick={{ fontSize: 10 }}
            minTickGap={40}
          />
          <YAxis
            stroke="rgba(200,220,255,0.35)"
            tick={{ fontSize: 10 }}
            tickFormatter={(v: number) => fmtINR(v)}
            width={56}
          />
          <Tooltip
            contentStyle={{
              background: "rgba(10,12,24,0.95)",
              border: "1px solid rgba(120,180,255,0.25)",
              borderRadius: 8, fontSize: 12,
            }}
            labelStyle={{ color: "#a0c8ff" }}
            formatter={(v) => fmtINR(Number(v))}
          />
          <Area
            type="monotone" dataKey="futures" stroke="#67b3ff"
            fill="url(#orbFutures)" strokeWidth={1.2}
          />
          <Area
            type="monotone" dataKey="options" stroke="#d6a3ff"
            fill="url(#orbOptions)" strokeWidth={1.2}
          />
          <Area
            type="monotone" dataKey="combined" stroke="var(--neon-green, #3af58a)"
            fill="url(#orbCombined)" strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
