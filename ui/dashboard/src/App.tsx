import { useState } from "react";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import Overview from "./views/Overview";
import Signals from "./views/Signals";
import Strategies from "./views/Strategies";
import Positions from "./views/Positions";
import RiskMonitor from "./views/RiskMonitor";
import Settings from "./views/Settings";

const views: Record<string, () => JSX.Element> = {
  overview: Overview,
  signals: Signals,
  strategies: Strategies,
  positions: Positions,
  risk: RiskMonitor,
  settings: Settings,
};

export default function App() {
  const [activeView, setActiveView] = useState("overview");
  const View = views[activeView] || Overview;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar active={activeView} onNavigate={setActiveView} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto p-6">
          <View />
        </main>
      </div>
    </div>
  );
}
