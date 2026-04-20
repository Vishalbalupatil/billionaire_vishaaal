import { useEffect, useState } from "react";
import { api, type HealthResp, type PortfolioResp, type RiskStatus } from "./api";
import AskAI from "./components/AskAI";
import IntroSequence, { shouldShowIntro } from "./components/IntroSequence";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import Alerts from "./views/Alerts";
import Backtest from "./views/Backtest";
import Forecast from "./views/Forecast";
import OptionChain from "./views/OptionChain";
import Overview from "./views/Overview";
import Positions from "./views/Positions";
import RiskMonitor from "./views/RiskMonitor";
import Signals from "./views/Signals";
import Trades from "./views/Trades";
import Watchlist from "./views/Watchlist";

export type View =
  | "overview"
  | "forecast"
  | "watchlist"
  | "signals"
  | "positions"
  | "trades"
  | "risk"
  | "option"
  | "alerts"
  | "backtest";

export default function App() {
  const [view, setView] = useState<View>("overview");
  const [health, setHealth] = useState<HealthResp | null>(null);
  const [risk, setRisk] = useState<RiskStatus | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioResp | null>(null);
  const [askOpen, setAskOpen] = useState(false);
  const [introVisible, setIntroVisible] = useState(() => shouldShowIntro());

  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;
    async function tick() {
      try {
        const [h, r, p] = await Promise.all([api.health(), api.risk(), api.portfolio()]);
        setHealth(h);
        setRisk(r);
        setPortfolio(p);
      } catch {
        /* backend likely not up */
      }
    }
    tick();
    timer = setInterval(tick, 2500);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">B</div>
          <div className="name">Vishaaal</div>
        </div>
        <Sidebar view={view} onChange={setView} />
      </aside>
      <header className="topbar">
        <TopBar health={health} risk={risk} onAskAI={() => setAskOpen((o) => !o)} />
      </header>
      <main className="main">
        {view === "overview"  && <Overview health={health} risk={risk} portfolio={portfolio} />}
        {view === "forecast"  && <Forecast />}
        {view === "watchlist" && <Watchlist />}
        {view === "signals"   && <Signals />}
        {view === "positions" && <Positions portfolio={portfolio} />}
        {view === "trades"    && <Trades />}
        {view === "risk"      && <RiskMonitor risk={risk} />}
        {view === "option"    && <OptionChain />}
        {view === "alerts"    && <Alerts />}
        {view === "backtest"  && <Backtest />}
      </main>
      <AskAI
        open={askOpen}
        onClose={() => setAskOpen(false)}
        health={health}
        risk={risk}
        portfolio={portfolio}
      />
      {introVisible && <IntroSequence onDone={() => setIntroVisible(false)} />}
    </div>
  );
}
