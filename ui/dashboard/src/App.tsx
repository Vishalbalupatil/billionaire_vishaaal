import { useEffect, useState } from "react";
import { api, type HealthResp, type PortfolioResp, type RiskStatus } from "./api";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import Overview from "./views/Overview";
import Watchlist from "./views/Watchlist";
import Signals from "./views/Signals";
import Positions from "./views/Positions";
import Trades from "./views/Trades";
import RiskMonitor from "./views/RiskMonitor";
import OptionChain from "./views/OptionChain";
import Alerts from "./views/Alerts";
import Backtest from "./views/Backtest";

export type View =
  | "overview"
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
        <div className="brand">BILLIONAIRE VISHAAAL</div>
        <Sidebar view={view} onChange={setView} />
      </aside>
      <header className="topbar">
        <TopBar health={health} risk={risk} />
      </header>
      <main className="main">
        {view === "overview" && <Overview health={health} risk={risk} portfolio={portfolio} />}
        {view === "watchlist" && <Watchlist />}
        {view === "signals" && <Signals />}
        {view === "positions" && <Positions portfolio={portfolio} />}
        {view === "trades" && <Trades />}
        {view === "risk" && <RiskMonitor risk={risk} />}
        {view === "option" && <OptionChain />}
        {view === "alerts" && <Alerts />}
        {view === "backtest" && <Backtest />}
      </main>
    </div>
  );
}
