interface SidebarProps {
  active: string;
  onNavigate: (view: string) => void;
}

const items = [
  { id: "overview", label: "Overview", icon: "📊" },
  { id: "signals", label: "AI Signals", icon: "🧠" },
  { id: "strategies", label: "Strategies", icon: "📈" },
  { id: "positions", label: "Positions", icon: "💼" },
  { id: "risk", label: "Risk Monitor", icon: "🛡️" },
  { id: "settings", label: "Settings", icon: "⚙️" },
];

export default function Sidebar({ active, onNavigate }: SidebarProps) {
  return (
    <aside className="w-64 bg-dark-800 border-r border-dark-600/50 flex flex-col">
      <div className="p-6">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-neon-green to-neon-blue bg-clip-text text-transparent">
          AI Trader
        </h1>
        <p className="text-xs text-gray-500 mt-1">Nifty 50 Options</p>
      </div>
      <nav className="flex-1 px-3">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-all mb-1
              ${active === item.id
                ? "bg-dark-600 text-neon-green neon-glow-green"
                : "text-gray-400 hover:text-white hover:bg-dark-700"
              }`}
          >
            <span className="text-lg">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>
      <div className="p-4 mx-3 mb-3 glass-card text-center">
        <p className="text-xs text-gray-500">Not Financial Advice</p>
        <p className="text-xs text-gray-600 mt-1">Paper trade first</p>
      </div>
    </aside>
  );
}
