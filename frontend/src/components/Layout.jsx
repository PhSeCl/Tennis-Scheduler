import { FileSpreadsheet, PlaySquare, Users } from "lucide-react";
import { useTranslation } from "../contexts/LanguageContext.jsx";

const navItems = [
  {
    id: "players",
    label: "Players",
    icon: Users
  },
  {
    id: "draws",
    label: "Draws",
    icon: FileSpreadsheet
  },
  {
    id: "scheduler",
    label: "Scheduler",
    icon: PlaySquare
  }
];

function Layout({ activeTab, onTabChange, children }) {
  const { lang, setLang, t } = useTranslation();

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50">
      <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col flex-shrink-0">
        <div className="px-6 py-6 border-b border-slate-800">
          <p className="text-lg font-semibold tracking-wide">Tennis Scheduler</p>
          <p className="text-xs text-slate-400 mt-1">Local desktop console</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.id === activeTab;
            const label = t(item.id);
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onTabChange(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition ${
                  isActive
                    ? "bg-slate-800 text-white"
                    : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span className="text-sm font-medium">{label}</span>
              </button>
            );
          })}
        </nav>
        <div className="px-3 mt-auto">
          <button
            type="button"
            onClick={() => setLang(lang === "zh" ? "en" : "zh")}
            className="mb-4 w-full text-xs font-medium bg-slate-800 text-slate-300 py-1.5 px-3 rounded hover:bg-slate-700 transition-colors"
          >
            {lang === "zh" ? "🌐 Switch to English" : "🌐 切换至中文"}
          </button>
        </div>
        <div className="px-6 py-4 border-t border-slate-800 text-xs text-slate-500">
          Powered by Eel + React
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="min-h-full">{children}</div>
      </main>
    </div>
  );
}

export default Layout;
