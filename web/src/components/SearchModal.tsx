import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Box, Package, Radio, Search, TerminalSquare } from "lucide-react";
import { api } from "../lib/api";
import type { SearchHit } from "../types";
import { StatusPill } from "./StatusDot";

const icons = {
  remote: Radio,
  container: Box,
  update: Package,
  task: TerminalSquare,
};

export function SearchModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [active, setActive] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) {
      setQuery("");
      setHits([]);
      setActive(0);
    }
  }, [open]);

  useEffect(() => {
    if (!open || query.trim().length < 1) {
      setHits([]);
      return;
    }
    const handle = window.setTimeout(() => {
      api<{ hits: SearchHit[] }>(`/api/v1/search?q=${encodeURIComponent(query.trim())}`)
        .then((result) => {
          setHits(result.hits);
          setActive(0);
        })
        .catch(() => setHits([]));
    }, 120);
    return () => window.clearTimeout(handle);
  }, [query, open]);

  const grouped = useMemo(() => {
    return hits.reduce<Record<string, SearchHit[]>>((acc, hit) => {
      acc[hit.kind] = acc[hit.kind] || [];
      acc[hit.kind].push(hit);
      return acc;
    }, {});
  }, [hits]);

  if (!open) return null;

  function go(hit: SearchHit) {
    navigate(hit.href);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-[12vh]" onClick={onClose}>
      <div className="panel w-full max-w-2xl overflow-hidden" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
          <Search className="h-4 w-4 text-slate-400" />
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") onClose();
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setActive((value) => Math.min(value + 1, hits.length - 1));
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setActive((value) => Math.max(value - 1, 0));
              }
              if (event.key === "Enter" && hits[active]) go(hits[active]);
            }}
            placeholder="Search remotes, containers, updates, and tasks"
            className="w-full bg-transparent text-sm outline-none placeholder:text-slate-500"
          />
          <kbd className="rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-slate-500">ESC</kbd>
        </div>
        <div className="max-h-[50vh] overflow-auto p-2">
          {query && hits.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-slate-500">No matches for “{query}”</p>
          )}
          {!query && (
            <p className="px-3 py-8 text-center text-sm text-slate-500">
              Type to search the fleet. Try a hostname, image, package, or task type.
            </p>
          )}
          {Object.entries(grouped).map(([kind, items]) => (
            <div key={kind} className="mb-2">
              <p className="px-3 py-1 text-[11px] uppercase tracking-wide text-slate-500">{kind}s</p>
              {items.map((hit) => {
                const index = hits.findIndex((item) => item.id === hit.id && item.kind === hit.kind);
                const Icon = icons[hit.kind as keyof typeof icons] || Search;
                return (
                  <button
                    key={`${hit.kind}-${hit.id}`}
                    onClick={() => go(hit)}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left ${
                      index === active ? "bg-berry-600/20" : "hover:bg-white/5"
                    }`}
                  >
                    <Icon className="h-4 w-4 text-slate-400" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{hit.title}</p>
                      <p className="truncate text-xs text-slate-500">{hit.subtitle}</p>
                    </div>
                    {hit.status && <StatusPill status={hit.status} />}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
