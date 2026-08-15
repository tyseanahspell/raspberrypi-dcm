import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Box, LayoutDashboard, Package, Radio, Search, Settings, TerminalSquare } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useLive } from "../context/LiveContext";
import { SearchModal } from "./SearchModal";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/remotes", label: "Remotes", icon: Radio },
  { to: "/containers", label: "Containers", icon: Box },
  { to: "/updates", label: "Updates", icon: Package },
  { to: "/tasks", label: "Tasks", icon: TerminalSquare },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Layout() {
  const { username, logout } = useAuth();
  const { connected } = useLive();
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-col border-r border-white/10 bg-ink-900/90">
        <div className="border-b border-white/10 px-5 py-5">
          <p className="text-[11px] uppercase tracking-[0.2em] text-berry-400">RPDM</p>
          <h1 className="mt-1 text-lg font-semibold leading-tight">Pi Datacenter Manager</h1>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                  isActive ? "bg-berry-600/20 text-white" : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
                }`
              }
            >
              <link.icon className="h-4 w-4" />
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-white/10 p-4 text-xs text-slate-500">
          <p>Signed in as {username}</p>
          <button onClick={logout} className="mt-2 text-berry-400 hover:text-berry-300">
            Sign out
          </button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-white/10 bg-ink-900/70 px-6 py-3">
          <button
            onClick={() => setSearchOpen(true)}
            className="flex w-full max-w-xl items-center gap-3 rounded-lg border border-white/10 bg-ink-800 px-3 py-2 text-sm text-slate-400"
          >
            <Search className="h-4 w-4" />
            Search remotes, containers, updates…
            <span className="ml-auto rounded border border-white/10 px-1.5 py-0.5 text-[10px]">Ctrl K</span>
          </button>
          <div className="ml-4 flex items-center gap-2 text-xs text-slate-400">
            <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-amber-400"}`} />
            {connected ? "Live" : "Reconnecting"}
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
