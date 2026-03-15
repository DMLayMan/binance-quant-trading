import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  BarChart3,
  Brain,
  FlaskConical,
  Shield,
  Settings,
  Menu,
  X,
} from "lucide-react";
import { useState } from "react";

const links = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/market", label: "Market", icon: BarChart3 },
  { to: "/strategies", label: "Strategies", icon: Brain },
  { to: "/backtest", label: "Backtest", icon: FlaskConical },
  { to: "/risk", label: "Risk", icon: Shield },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

export default function Sidebar() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Mobile toggle */}
      <button
        className="fixed top-4 left-4 z-50 md:hidden rounded-lg bg-gray-800 p-2 text-gray-300"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Backdrop on mobile */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed z-40 md:static
          flex h-screen w-60 flex-col bg-gray-900 border-r border-gray-800
          transition-transform duration-200
          ${open ? "translate-x-0" : "-translate-x-full"}
          md:translate-x-0
        `}
      >
        {/* Brand */}
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="text-xl font-bold text-white tracking-tight">
            BQT
          </span>
          <span className="text-xs text-gray-500">Dashboard</span>
        </div>

        {/* Nav links */}
        <nav className="flex flex-col gap-1 px-3 mt-2">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-gray-800 text-white"
                    : "text-gray-400 hover:bg-gray-800/50 hover:text-gray-200"
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Bottom spacer */}
        <div className="mt-auto px-5 py-4 text-xs text-gray-600">
          Binance Quant Trading
        </div>
      </aside>
    </>
  );
}
