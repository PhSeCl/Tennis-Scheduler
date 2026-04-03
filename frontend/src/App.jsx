import { useMemo, useState } from "react";
import Layout from "./components/Layout.jsx";
import { LanguageProvider } from "./contexts/LanguageContext.jsx";
import DrawManager from "./pages/DrawManager.jsx";
import PlayerManager from "./pages/PlayerManager.jsx";
import SchedulerConsole from "./pages/SchedulerConsole.jsx";

const pageMap = {
  players: PlayerManager,
  draws: DrawManager,
  scheduler: SchedulerConsole
};

function App() {
  const [activeTab, setActiveTab] = useState("players");
  const ActivePage = useMemo(() => pageMap[activeTab] || PlayerManager, [activeTab]);

  return (
    <LanguageProvider>
      <Layout activeTab={activeTab} onTabChange={setActiveTab}>
        <ActivePage />
      </Layout>
    </LanguageProvider>
  );
}

export default App;
