/**
 * Pure-SVG forecast chart. Renders:
 *   - A single projected-price line (the model's mean path).
 *   - A 95% confidence band as a shaded polygon behind it.
 *   - A horizontal "last price" reference line.
 *
 * Deliberately tiny. No deps. If we ever want candles / axes / tooltips
 * we can swap in lightweight-charts later; this keeps the bundle small
 * and the render predictable for demos.
 */

import type { ForecastPoint } from "../api";

export default function ForecastChart({
  points,
  lastPrice,
  width = 760,
  height = 260,
  bias,
}: {
  points: ForecastPoint[];
  lastPrice: number;
  width?: number;
  height?: number;
  bias: "BULLISH" | "BEARISH" | "NEUTRAL";
}) {
  if (points.length === 0) {
    return (
      <div className="chart-wrap" style={{ display: "grid", placeItems: "center" }}>
        <span className="muted tiny">No projected path (bias-only mode).</span>
      </div>
    );
  }

  const padX = 36;
  const padY = 24;
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;

  const allYs = [lastPrice, ...points.flatMap((p) => [p.lower, p.upper])];
  const yMin = Math.min(...allYs);
  const yMax = Math.max(...allYs);
  const yPad = (yMax - yMin) * 0.08 || 1;
  const lo = yMin - yPad;
  const hi = yMax + yPad;

  const xOf = (i: number) =>
    padX + (innerW * i) / Math.max(points.length - 1, 1);
  const yOf = (v: number) =>
    padY + innerH - ((v - lo) / (hi - lo)) * innerH;

  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xOf(i).toFixed(1)} ${yOf(p.price).toFixed(1)}`)
    .join(" ");

  // Band polygon: walk upper edge forward, lower edge back.
  const upper = points.map((p, i) => `${xOf(i).toFixed(1)} ${yOf(p.upper).toFixed(1)}`);
  const lower = points
    .slice()
    .reverse()
    .map((p, ri) => {
      const i = points.length - 1 - ri;
      return `${xOf(i).toFixed(1)} ${yOf(p.lower).toFixed(1)}`;
    });
  const bandPath = `M ${upper.join(" L ")} L ${lower.join(" L ")} Z`;

  const stroke =
    bias === "BULLISH" ? "#6bff9e" : bias === "BEARISH" ? "#ff5474" : "#ffd36b";
  const bandFill =
    bias === "BULLISH"
      ? "rgba(107,255,158,0.14)"
      : bias === "BEARISH"
      ? "rgba(255,84,116,0.14)"
      : "rgba(255,211,107,0.12)";

  const lastY = yOf(lastPrice);
  const firstProjY = yOf(points[points.length - 1].price);

  // A few horizontal price gridlines.
  const ticks = 4;
  const tickYs = Array.from({ length: ticks + 1 }, (_, i) => lo + ((hi - lo) * i) / ticks);

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="line-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.55" />
            <stop offset="100%" stopColor={stroke} stopOpacity="1" />
          </linearGradient>
        </defs>

        {/* gridlines */}
        {tickYs.map((v, i) => (
          <g key={i}>
            <line
              x1={padX}
              x2={width - padX}
              y1={yOf(v)}
              y2={yOf(v)}
              stroke="rgba(130,200,255,0.08)"
              strokeDasharray="2 4"
            />
            <text
              x={width - padX + 6}
              y={yOf(v) + 3}
              fontSize="10"
              fontFamily="JetBrains Mono, monospace"
              fill="rgba(130,200,255,0.5)"
            >
              {v.toFixed(1)}
            </text>
          </g>
        ))}

        {/* confidence band */}
        <path d={bandPath} fill={bandFill} stroke="none" />

        {/* last-price reference */}
        <line
          x1={padX}
          x2={width - padX}
          y1={lastY}
          y2={lastY}
          stroke="rgba(130,200,255,0.35)"
          strokeDasharray="4 4"
        />
        <text
          x={padX + 6}
          y={lastY - 6}
          fontSize="10"
          fontFamily="JetBrains Mono, monospace"
          fill="rgba(229,237,251,0.75)"
        >
          NOW · {lastPrice.toFixed(2)}
        </text>

        {/* projected line */}
        <path
          d={linePath}
          fill="none"
          stroke="url(#line-grad)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* endpoint marker */}
        <circle cx={xOf(points.length - 1)} cy={firstProjY} r={4} fill={stroke} />
        <circle
          cx={xOf(points.length - 1)}
          cy={firstProjY}
          r={9}
          fill="none"
          stroke={stroke}
          opacity={0.4}
        >
          <animate attributeName="r" from="6" to="14" dur="1.6s" repeatCount="indefinite" />
          <animate attributeName="opacity" from="0.55" to="0" dur="1.6s" repeatCount="indefinite" />
        </circle>

        {/* "PROJECTION" watermark so no one mistakes this for real history */}
        <text
          x={width - padX - 6}
          y={padY + 12}
          textAnchor="end"
          fontSize="10"
          fontFamily="Orbitron, sans-serif"
          letterSpacing="3"
          fill="rgba(255,211,107,0.55)"
        >
          PROJECTION · NOT ACTUAL PRICE
        </text>
      </svg>
    </div>
  );
}
