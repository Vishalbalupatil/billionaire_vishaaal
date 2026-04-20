/**
 * Cinematic homepage intro — black curtain → gilded door opens → welcome
 * text → fade to app. Pure SVG + framer-motion, no photo assets, no
 * Three.js (keeps the bundle lean and avoids Rolls-Royce / real-estate
 * licensing pitfalls for user-provided luxury imagery).
 *
 * Trigger rules:
 *   - Shown once per browser session by default (sessionStorage flag).
 *   - URL `?intro=1` forces a replay (handy for demos).
 *   - Respects `prefers-reduced-motion` → collapses to a 400 ms gilt fade.
 *   - Skip button (top-right) always dismisses immediately.
 *
 * The intro mounts above everything else (z-index 100, fixed). When the
 * sequence completes (or the user clicks Skip) it unmounts via onDone.
 */
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";

const STORAGE_KEY = "billionaire:intro-seen";

function shouldShowIntro(): boolean {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  if (params.get("intro") === "1") return true;
  if (params.get("intro") === "0") return false;
  try {
    return sessionStorage.getItem(STORAGE_KEY) !== "1";
  } catch {
    return true;
  }
}

function markIntroSeen() {
  try {
    sessionStorage.setItem(STORAGE_KEY, "1");
  } catch {
    /* storage blocked — intro will replay next mount, acceptable fallback */
  }
}

/* --------------------------------------------------------------------- */
/* Particles — deterministic random-ish dust with variable drift vectors. */
/* --------------------------------------------------------------------- */
function useDustParticles(count = 88) {
  return useMemo(() => {
    const rng = mulberry32(0xb4d7);
    return Array.from({ length: count }, () => {
      const left = rng() * 100;
      const top = 40 + rng() * 60; // start mid-lower area
      const dx = (rng() - 0.5) * 180;
      const dy = -160 - rng() * 480; // float upward, varied height
      const delay = rng() * 18;
      const duration = 8 + rng() * 14;
      const size = 1.2 + rng() * 4;
      const bright = rng() > 0.75; // 25% are brighter particles
      return { left, top, dx, dy, delay, duration, size, bright };
    });
  }, [count]);
}
function mulberry32(a: number) {
  return function () {
    let t = (a += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* --------------------------------------------------------------------- */
/* Skyline silhouette (mansion + jet + rolls — stylised SVG only).       */
/* --------------------------------------------------------------------- */
function SkylineSilhouettes() {
  return (
    <svg
      className="skyline"
      viewBox="0 0 1600 200"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden
    >
      {/* Mansion colonnade silhouette — centred behind the door stage. */}
      <g transform="translate(540 20)" opacity="0.55">
        {/* pediment */}
        <polygon points="0,60 260,60 130,0" fill="#0a0805" stroke="rgba(212,175,55,0.4)" strokeWidth="0.7" />
        {/* entablature */}
        <rect x="-6" y="58" width="272" height="10" fill="#0a0805" stroke="rgba(212,175,55,0.35)" strokeWidth="0.6" />
        {/* columns */}
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <rect
            key={i}
            x={8 + i * 48}
            y="68"
            width="14"
            height="110"
            fill="#0a0805"
            stroke="rgba(212,175,55,0.32)"
            strokeWidth="0.6"
          />
        ))}
        {/* base */}
        <rect x="-8" y="178" width="276" height="14" fill="#0a0805" stroke="rgba(212,175,55,0.4)" strokeWidth="0.6" />
      </g>

      {/* Rolls-Royce-style silhouette — left side, low to the ground. */}
      <g transform="translate(120 160)" opacity="0.62">
        <path
          d="M0 20 C 20 0, 60 -10, 120 -10 L 220 -10 C 260 -10, 300 5, 340 15 L 360 24 C 365 30, 360 32, 355 32 L 10 32 C 2 32, -2 28, 0 20 Z"
          fill="#0a0805"
          stroke="rgba(212,175,55,0.45)"
          strokeWidth="0.7"
        />
        {/* cabin line */}
        <path d="M80 -10 L 105 -30 L 230 -30 L 260 -10" fill="#0a0805" stroke="rgba(212,175,55,0.38)" strokeWidth="0.7" />
        {/* wheels */}
        <circle cx="80" cy="32" r="14" fill="#05040a" stroke="rgba(212,175,55,0.55)" strokeWidth="0.8" />
        <circle cx="280" cy="32" r="14" fill="#05040a" stroke="rgba(212,175,55,0.55)" strokeWidth="0.8" />
        {/* soft gold headlight gleam */}
        <circle cx="355" cy="10" r="3" fill="#f4d27a" opacity="0.8" />
      </g>

      {/* Private jet silhouette — right side, cruising low, subtle. */}
      <g transform="translate(1180 74)" opacity="0.5">
        <path
          d="M0 16 L 60 10 L 210 8 L 280 14 L 210 20 L 60 22 Z"
          fill="#0a0805"
          stroke="rgba(212,175,55,0.4)"
          strokeWidth="0.7"
        />
        {/* tail */}
        <path d="M230 -2 L 260 -2 L 250 14 L 220 14 Z" fill="#0a0805" stroke="rgba(212,175,55,0.4)" strokeWidth="0.7" />
        {/* wing */}
        <path d="M100 14 L 150 28 L 180 28 L 160 14 Z" fill="#0a0805" stroke="rgba(212,175,55,0.35)" strokeWidth="0.6" />
      </g>
    </svg>
  );
}

/* --------------------------------------------------------------------- */
/* The golden door itself — pure SVG, with doors that rotate open in 3D. */
/* --------------------------------------------------------------------- */
function GoldenDoor({ opening }: { opening: boolean }) {
  const doorVariants = (side: "left" | "right") => ({
    closed: { rotateY: 0 },
    open: {
      rotateY: side === "left" ? -82 : 82,
      transition: { duration: 4.2, ease: [0.42, 0.04, 0.2, 1] as const },
    },
  });

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        perspective: "1600px",
        display: "grid",
        placeItems: "center",
      }}
    >
      {/* Warm light spill from inside the frame — becomes visible as the
          doors swing outward. Layered beneath the doors, above the stage. */}
      <motion.div
        initial={{ opacity: 0, scale: 0.3 }}
        animate={{
          opacity: opening ? 1 : 0,
          scale: opening ? 2.0 : 0.4,
        }}
        transition={{ duration: 4.2, ease: "easeOut", delay: opening ? 1.1 : 0 }}
        style={{
          position: "absolute",
          width: "96%",
          height: "96%",
          background:
            "radial-gradient(ellipse at center, rgba(255,246,221,1) 0%, rgba(255,240,200,0.85) 12%, rgba(244,210,122,0.65) 28%, rgba(212,175,55,0.35) 52%, transparent 78%)",
          filter: "blur(8px)",
          mixBlendMode: "screen",
          pointerEvents: "none",
        }}
      />
      {/* Secondary outer light burst — extends the glow beyond the door frame. */}
      <motion.div
        initial={{ opacity: 0, scale: 0.5 }}
        animate={{
          opacity: opening ? 0.8 : 0,
          scale: opening ? 3 : 0.5,
        }}
        transition={{ duration: 5, ease: "easeOut", delay: opening ? 1.6 : 0 }}
        style={{
          position: "absolute",
          width: "120%",
          height: "130%",
          background:
            "radial-gradient(ellipse at center, rgba(244,210,122,0.25) 0%, rgba(212,175,55,0.08) 40%, transparent 70%)",
          filter: "blur(24px)",
          mixBlendMode: "screen",
          pointerEvents: "none",
        }}
      />

      {/* Door frame — the stone jamb + gilt lintel. */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "2% 2% 0 0 / 3% 3% 0 0",
          background:
            "linear-gradient(180deg, #0b0905 0%, #14100a 50%, #07050a 100%)",
          border: "1px solid rgba(212,175,55,0.25)",
          boxShadow:
            "0 40px 80px rgba(0,0,0,0.6), inset 0 0 0 8px rgba(212,175,55,0.08), inset 0 0 0 12px rgba(0,0,0,0.4), inset 0 0 0 14px rgba(212,175,55,0.12)",
        }}
      />

      {/* Decorative arch medallion at top of frame. */}
      <svg
        viewBox="0 0 200 40"
        style={{
          position: "absolute",
          top: "2%",
          left: "10%",
          right: "10%",
          width: "80%",
          height: "5%",
          pointerEvents: "none",
        }}
        aria-hidden
      >
        <defs>
          <linearGradient id="arch-g" x1="0" x2="200" y1="0" y2="0">
            <stop offset="0" stopColor="#9a7b2a" />
            <stop offset="0.5" stopColor="#f4d27a" />
            <stop offset="1" stopColor="#9a7b2a" />
          </linearGradient>
        </defs>
        <path
          d="M0 38 L 20 18 Q 100 -10 180 18 L 200 38"
          fill="none"
          stroke="url(#arch-g)"
          strokeWidth="1.2"
          opacity="0.8"
        />
        <circle cx="100" cy="10" r="4" fill="#f4d27a" />
      </svg>

      {/* Both door panels share these SVG decorations. */}
      {(["left", "right"] as const).map((side) => (
        <motion.div
          key={side}
          className="door-panel"
          variants={doorVariants(side)}
          initial="closed"
          animate={opening ? "open" : "closed"}
          style={{
            position: "absolute",
            top: "4%",
            bottom: "4%",
            [side === "left" ? "left" : "right"]: "5%",
            width: "44%",
            transformOrigin: side === "left" ? "left center" : "right center",
            transformStyle: "preserve-3d",
            borderRadius:
              side === "left" ? "6% 1% 1% 6% / 3% 1% 1% 3%" : "1% 6% 6% 1% / 1% 3% 3% 1%",
            background:
              "linear-gradient(145deg, #2a1f0a 0%, #1a1205 40%, #0a0805 100%)",
            boxShadow:
              side === "left"
                ? "inset -12px 0 22px rgba(0,0,0,0.7), inset 10px 0 20px rgba(212,175,55,0.10), 0 24px 48px rgba(0,0,0,0.6)"
                : "inset 12px 0 22px rgba(0,0,0,0.7), inset -10px 0 20px rgba(212,175,55,0.10), 0 24px 48px rgba(0,0,0,0.6)",
            overflow: "hidden",
            backfaceVisibility: "hidden",
          }}
        >
          <svg
            viewBox="0 0 200 480"
            preserveAspectRatio="none"
            style={{ width: "100%", height: "100%", display: "block" }}
            aria-hidden
          >
            <defs>
              <linearGradient id={`panel-g-${side}`} x1="0" x2="200" y1="0" y2="0">
                <stop offset="0" stopColor="#6b5020" />
                <stop offset="0.5" stopColor="#d4af37" />
                <stop offset="1" stopColor="#6b5020" />
              </linearGradient>
              <radialGradient id={`medallion-${side}`} cx="50%" cy="50%" r="50%">
                <stop offset="0" stopColor="#fff6dd" />
                <stop offset="0.3" stopColor="#f4d27a" />
                <stop offset="0.8" stopColor="#9a7b2a" />
                <stop offset="1" stopColor="#3a2a10" />
              </radialGradient>
            </defs>

            {/* Double gilt border. */}
            <rect x="10" y="10" width="180" height="460" fill="none" stroke={`url(#panel-g-${side})`} strokeWidth="1.4" opacity="0.9" />
            <rect x="18" y="18" width="164" height="444" fill="none" stroke={`url(#panel-g-${side})`} strokeWidth="0.8" opacity="0.6" />

            {/* Upper decorative cartouche. */}
            <g transform="translate(100 90)">
              <circle r="36" fill="none" stroke={`url(#panel-g-${side})`} strokeWidth="1.2" opacity="0.85" />
              <circle r="28" fill="none" stroke={`url(#panel-g-${side})`} strokeWidth="0.6" opacity="0.6" />
              {/* fleur-de-lis-ish flourish */}
              <path
                d="M0 -22 C -6 -10, -6 0, 0 8 C 6 0, 6 -10, 0 -22 Z M 0 8 L 0 22 M -12 10 C -6 14, 6 14, 12 10"
                fill="none"
                stroke={`url(#panel-g-${side})`}
                strokeWidth="1"
              />
            </g>

            {/* Mid-panel recessed rectangle (mouldings). */}
            <rect x="30" y="148" width="140" height="200" fill="none" stroke={`url(#panel-g-${side})`} strokeWidth="0.8" opacity="0.55" />
            <rect x="38" y="156" width="124" height="184" fill="none" stroke={`url(#panel-g-${side})`} strokeWidth="0.4" opacity="0.4" />

            {/* Lower diamond ornament. */}
            <g transform="translate(100 390)" opacity="0.75">
              <path d="M-20 0 L 0 -16 L 20 0 L 0 16 Z" fill="none" stroke={`url(#panel-g-${side})`} strokeWidth="0.9" />
              <path d="M-10 0 L 0 -8 L 10 0 L 0 8 Z" fill="none" stroke={`url(#panel-g-${side})`} strokeWidth="0.5" />
            </g>

            {/* Handle — jewelled medallion on the centre edge with shimmer. */}
            <g
              transform={side === "left" ? "translate(186 240)" : "translate(14 240)"}
            >
              <circle r="9" fill={`url(#medallion-${side})`} />
              <circle r="4" fill="#fff6dd" opacity="0.85">
                <animate attributeName="opacity" values="0.4;1;0.4" dur="3.2s" repeatCount="indefinite" />
                <animate attributeName="r" values="3;4.5;3" dur="3.2s" repeatCount="indefinite" />
              </circle>
              <rect x="-2" y="8" width="4" height="34" fill={`url(#panel-g-${side})`} opacity="0.9" />
            </g>

            {/* Additional embossed quatrefoil detail — mid panel. */}
            <g transform="translate(100 250)" opacity="0.4">
              <path d="M0 -12 C 6 -12, 12 -6, 12 0 C 12 6, 6 12, 0 12 C -6 12, -12 6, -12 0 C -12 -6, -6 -12, 0 -12 Z" fill="none" stroke={`url(#panel-g-${side})`} strokeWidth="0.5" />
              <path d="M0 0 L 8 -8 M 0 0 L -8 -8 M 0 0 L 8 8 M 0 0 L -8 8" stroke={`url(#panel-g-${side})`} strokeWidth="0.4" />
            </g>
          </svg>
        </motion.div>
      ))}
    </div>
  );
}

/* --------------------------------------------------------------------- */
/* Main orchestrator.                                                     */
/* --------------------------------------------------------------------- */
export default function IntroSequence({ onDone }: { onDone: () => void }) {
  const reduced = useReducedMotion();
  const [phase, setPhase] = useState<"curtain" | "open" | "exit">("curtain");
  const doneRef = useRef(false);
  const particles = useDustParticles(92);

  const finish = () => {
    if (doneRef.current) return;
    doneRef.current = true;
    markIntroSeen();
    setPhase("exit");
    // Let the exit fade play before unmounting.
    window.setTimeout(onDone, reduced ? 150 : 1200);
  };

  useEffect(() => {
    if (reduced) {
      // Reduced motion: show a 400 ms gilt fade then exit.
      const t = window.setTimeout(finish, 400);
      return () => window.clearTimeout(t);
    }
    // Choreographed timeline — slower, more dramatic. Every beat breathes.
    const t1 = window.setTimeout(() => setPhase("open"), 2200); // start door opening
    const t2 = window.setTimeout(finish, 8800); // extended cinematic window
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduced]);

  return (
    <AnimatePresence>
      <motion.div
        key="intro"
        className={`intro ${phase === "exit" ? "exit" : ""}`}
        initial={{ opacity: 1 }}
        animate={{ opacity: phase === "exit" ? 0 : 1 }}
        transition={{ duration: phase === "exit" ? 0.9 : 0, ease: "easeInOut" }}
        aria-label="Welcome sequence"
      >
        {/* Ambient layers — marble floor, warm halo, fan of rays. */}
        <div className="backdrop" />
        <div className="halo" />
        <div className="rays" />
        <SkylineSilhouettes />
        <div className="floor" />

        {/* Particles layer — golden dust drifting upward, with bright sparks. */}
        <div className="particles" aria-hidden>
          {particles.map((p, i) => (
            <span
              key={i}
              className={`p ${p.bright ? "bright" : ""}`}
              style={{
                left: `${p.left}%`,
                top: `${p.top}%`,
                width: `${p.size}px`,
                height: `${p.size}px`,
                animationDelay: `${p.delay}s`,
                animationDuration: `${p.duration}s`,
                // CSS custom props consumed by .dust keyframes.
                ["--dx" as string]: `${p.dx}px`,
                ["--dy" as string]: `${p.dy}px`,
              }}
            />
          ))}
        </div>

        {/* Camera push — the whole door stage slightly approaches as it opens. */}
        <motion.div
          className="door-stage"
          initial={{ scale: 0.86, opacity: 0 }}
          animate={{
            scale: phase === "open" ? 1.18 : 0.96,
            opacity: 1,
          }}
          transition={{ duration: 4.4, ease: [0.2, 0.8, 0.2, 1] }}
        >
          <GoldenDoor opening={phase === "open"} />
        </motion.div>

        {/* Welcome copy — eases in once the doors start parting. */}
        <motion.div
          className="welcome"
          initial={{ opacity: 0, y: 24, scale: 0.96 }}
          animate={{
            opacity: phase === "open" ? 1 : 0,
            y: phase === "open" ? 0 : 24,
            scale: phase === "open" ? 1 : 0.96,
          }}
          transition={{ duration: 2.2, delay: phase === "open" ? 2.0 : 0, ease: [0.22, 0.8, 0.2, 1] }}
        >
          <div className="eyebrow">Private · Decision Support</div>
          <h1>Welcome, Billionaire Vishal</h1>
          <p>Enter a world of power, vision &amp; luxury</p>
        </motion.div>

        <button
          className="skip"
          onClick={finish}
          aria-label="Skip intro"
        >
          Skip
        </button>
      </motion.div>
    </AnimatePresence>
  );
}

export { shouldShowIntro };
