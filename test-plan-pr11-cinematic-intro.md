# Test plan — PR #11: cinematic video backdrop + photographic vignettes

**Repo**: Vishalbalupatil/billionaire_vishaaal (state: PR #11 merged into `main`)
**Primary claim to prove**: The intro overlay now layers 3 actual `<video>` loops and 5 photographic `<img>` vignettes behind the gilded SVG door — not just the SVG-only silhouettes that shipped in PR #10.

Evidence grounded in code:
- `ui/dashboard/src/components/IntroSequence.tsx`:
  - `CinemaBackdrop` renders three `<motion.video>` elements with `src="/intro/mansion_bg.mp4"`, `"/intro/skyline.mp4"`, `"/intro/golddust.mp4"` (lines 346-415, all `autoPlay muted playsInline`)
  - `Vignettes` renders a `<div className="vignettes">` wrapping 5 `<motion.div className="vignette">` each with a child `<img src="/intro/{chandelier,car,jet,mansion,goldbg}.jpg">` (lines 428-493)
  - Orchestrator mounts `<CinemaBackdrop phase={phase} />` and `<Vignettes phase={phase} />` above the existing `.backdrop`/`.halo`/`.rays`/`.skyline`/`.door-stage` (lines 534-538)
  - Timeline: `setPhase("open")` at 3200ms, `finish` at 10500ms (lines 514-519)
- `ui/dashboard/src/index.css`:
  - `.intro .cinema-layer`, `.intro .cinema-tint`, `.intro .cinema-vignette` (lines 928-978)
  - `.intro .vignette`, `.intro .vignette img`, `@keyframes ken-burns` (lines 980-1018)
- `ui/dashboard/public/intro/` contains `mansion_bg.mp4 (739 KB)`, `skyline.mp4 (183 KB)`, `golddust.mp4 (434 KB)` and 5 JPGs.
- App mounts intro via `shouldShowIntro()` — sessionStorage flag, `?intro=1` force-replay. The mount point is `src/App.tsx` (intro overlay renders above everything else at z-index 100).

## Primary flow (one continuous recording)

### Setup (not in the recording)
- Backend running on :8000 (`broker: paper-only` from `/api/health`)
- Vite dev server on :5173
- Chrome open with devtools console ready
- SessionStorage cleared so intro plays

### Steps and assertions

**Step 1**: Navigate to `http://127.0.0.1:5173/?intro=1`. Maximize Chrome.
- **Expected**: `.intro` overlay visible, door SVG centred, welcome text "Welcome, Billionaire Vishal" appears around the 5-8 second mark.

**Step 2** (3-4s into the intro, while the intro is still on screen): Open devtools console, run:
```js
JSON.stringify({
  videos: Array.from(document.querySelectorAll('.intro .cinema video')).map(v => ({
    src: new URL(v.currentSrc || v.src).pathname,
    readyState: v.readyState,
    currentTime: +v.currentTime.toFixed(2),
    paused: v.paused,
    muted: v.muted
  })),
  vignettes: Array.from(document.querySelectorAll('.intro .vignette img')).map(i => ({
    src: new URL(i.currentSrc || i.src).pathname,
    naturalWidth: i.naturalWidth,
    complete: i.complete
  })),
  doorPanels: document.querySelectorAll('.intro .door-panel').length
})
```

- **Pass/fail**:
  - `videos.length === 3` AND every entry has `readyState >= 2`, `currentTime > 0`, `paused === false`, `muted === true`
  - Paths exactly: `/intro/mansion_bg.mp4`, `/intro/skyline.mp4`, `/intro/golddust.mp4`
  - `vignettes.length === 5` AND every entry has `naturalWidth > 0`, `complete === true`
  - Paths exactly: `/intro/chandelier.jpg`, `/intro/car.jpg`, `/intro/jet.jpg`, `/intro/mansion.jpg`, `/intro/goldbg.jpg`
  - `doorPanels === 2` (confirms door still renders)

  *Broken-state witness*: If the intro were reverted to PR #10, `.cinema video` → 0 and `.vignette img` → 0. The exact path + `currentTime > 0` also rules out silent fallback to `poster`.

**Step 3** (screenshot at ~4s, 7s): Visual confirmation. Expected:
- Mansion aerial video visible behind the door at low opacity
- Chandelier vignette top-centre, car bottom-left, jet bottom-right, estate mid-left, goldbg mid-right — each in a gilt-bordered frame
- Door panels open outward revealing light spill

**Step 4**: Wait for intro to end (~10.5s total). Expected: overlay fades out, dashboard visible with `NIFTY 50 · AI OVERVIEW` eyebrow.

**Step 5**: Refresh the page (F5) without the `?intro=1` param. Expected: intro does NOT replay (sessionStorage flag holds). Dashboard shows immediately.

## Regression label (not primary)

- One screenshot of Overview showing `NIFTY 50 · AI OVERVIEW` eyebrow heading is kept to prove the amplified-luxury look (PR #10) is still rendering after the intro dismisses.

## Out of scope

- Live-mode / Kite WebSocket verification (market closed, no access token on VM)
- iOS Safari autoplay — can't simulate from Linux VM; relies on `muted + playsInline` per spec
- Reduced-motion branch — will not record; it just collapses to a 400ms fade and skips the feature being demonstrated

## Artifacts produced

- One annotated browser recording (~20-25s) covering the intro + dashboard reveal
- Devtools console JSON screenshot proving the DOM assertions
- `test-report-pr11.md` with both of the above embedded
- One GitHub comment on PR #11 with collapsed summary + Devin session link
