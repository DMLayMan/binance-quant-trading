import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar.tsx";
import OverviewPage from "./components/overview/OverviewPage.tsx";
import MarketPage from "./components/market/MarketPage.tsx";
import StrategiesPage from "./components/strategies/StrategiesPage.tsx";
import BacktestPage from "./components/backtest/BacktestPage.tsx";
import RiskPage from "./components/risk/RiskPage.tsx";
import SettingsPage from "./components/settings/SettingsPage.tsx";
import FundsPage from "./components/funds/FundsPage.tsx";
import InstancesPage from "./components/instances/InstancesPage.tsx";
import TradesPage from "./components/trades/TradesPage.tsx";

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-950 text-gray-100 font-[Inter,system-ui,sans-serif]">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/market" element={<MarketPage />} />
          <Route path="/funds" element={<FundsPage />} />
          <Route path="/instances" element={<InstancesPage />} />
          <Route path="/trades" element={<TradesPage />} />
          <Route path="/strategies" element={<StrategiesPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/risk" element={<RiskPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
