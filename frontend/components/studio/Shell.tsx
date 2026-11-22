"use client";

import { Studio } from "@/lib/useStudio";
import { ViewId } from "@/lib/studio-types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { AudioLines, FolderOpen, Mic, Settings, Sparkles, HelpCircle, FlaskConical, ExternalLink } from "lucide-react";

const NAV: { id: ViewId; label: string; icon: typeof Mic; hint: string }[] = [
  { id: "create", label: "Create", icon: Sparkles, hint: "Topic to episode" },
  { id: "library", label: "Library", icon: FolderOpen, hint: "Your episodes" },
  { id: "voicelab", label: "Voice Lab", icon: FlaskConical, hint: "Engines and cloning" },
];

export function Shell({
  studio,
  view,
  onView,
  onSettings,
  onHelp,
  children,
}: {
  studio: Studio;
  view: ViewId;
  onView: (view: ViewId) => void;
  onSettings: () => void;
  onHelp: () => void;
  children: React.ReactNode;
}) {
  const statusColor =
    studio.backendOnline === null ? "subtle" : studio.backendOnline ? "success" : "error";

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      {/* Sidebar */}
      <aside className="border-b lg:border-b-0 lg:border-r border-border bg-surface/60 lg:min-h-screen lg:sticky lg:top-0">
        <div className="px-5 py-5 flex lg:block items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-accent-2 flex items-center justify-center">
              <AudioLines className="w-5 h-5 text-slate-900" />
            </div>
            <div>
              <p className="text-sm font-bold leading-tight">Podcast Brain</p>
              <p className="text-[10px] text-muted uppercase tracking-widest">Studio</p>
            </div>
          </div>
          <div className="flex lg:hidden gap-1">
            <button onClick={onSettings} aria-label="Settings" className="p-2 text-muted hover:text-foreground">
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        <nav className="px-3 pb-4 flex lg:flex-col gap-1 overflow-x-auto" aria-label="Studio sections">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = view === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onView(item.id)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors shrink-0 lg:w-full",
                  active
                    ? "bg-accent/15 text-foreground border border-accent/30"
                    : "text-muted hover:text-foreground hover:bg-white/5 border border-transparent"
                )}
              >
                <Icon className={cn("w-4 h-4", active && "text-accent")} />
                <span className="text-sm font-medium">{item.label}</span>
                <span className="hidden lg:block text-[10px] text-muted ml-auto">{item.hint}</span>
              </button>
            );
          })}
        </nav>

        <div className="hidden lg:block px-5 py-4 mt-4 border-t border-border space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted">Backend</span>
            <Badge variant={statusColor} className="text-[10px]">
              {studio.backendOnline === null ? "Checking" : studio.backendOnline ? "Online" : "Offline"}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted">Device</span>
            <span className="text-[11px] font-medium uppercase">
              {studio.modelStatus?.limits?.device ?? studio.modelStatus?.system?.device ?? "—"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted">Longform</span>
            <span className="text-[11px] font-medium">
              {studio.modelStatus?.longform.loaded
                ? "Ready"
                : studio.modelStatus?.longform.cached
                  ? "On disk"
                  : "Not downloaded"}
            </span>
          </div>
          <div className="flex gap-1 pt-2">
            <button
              onClick={onSettings}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg border border-border px-2 py-1.5 text-[11px] text-muted hover:text-foreground"
            >
              <Settings className="w-3.5 h-3.5" /> Keys
            </button>
            <button
              onClick={onHelp}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg border border-border px-2 py-1.5 text-[11px] text-muted hover:text-foreground"
            >
              <HelpCircle className="w-3.5 h-3.5" /> Help
            </button>
          </div>
          <a
            href="/landing"
            className="flex items-center justify-center gap-1.5 rounded-lg border border-border px-2 py-1.5 text-[11px] text-muted hover:text-foreground"
          >
            <ExternalLink className="w-3.5 h-3.5" /> Marketing page
          </a>
        </div>
      </aside>

      {/* Main */}
      <main className="relative dot-grid">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-56 brand-glow" />
        <div className="relative max-w-5xl mx-auto px-4 sm:px-8 py-8">{children}</div>
        <footer className="relative border-t border-border px-8 py-5 text-center">
          <p className="text-[11px] text-muted">
            Local synthesis · cloud scripting on free tiers · MIT licensed ·{" "}
            <a href="/feed/podcast.rss" target="_blank" rel="noreferrer" className="text-accent hover:underline">
              RSS feed
            </a>
          </p>
        </footer>
      </main>
    </div>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle: string; action?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 mb-8">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">{title}</h1>
        <p className="text-sm text-muted mt-1">{subtitle}</p>
      </div>
      {action}
    </header>
  );
}

export function BackendOfflineBanner({ studio }: { studio: Studio }) {
  if (studio.backendOnline !== false) return null;
  return (
    <div className="mb-6 flex items-center gap-3 rounded-xl border border-warning/40 bg-warning/10 px-4 py-3">
      <Mic className="w-4 h-4 text-warning shrink-0" />
      <p className="text-xs text-muted flex-1">
        The backend is not responding. Start it with{" "}
        <code className="text-foreground">uvicorn main:app --port 8000</code> in{" "}
        <code className="text-foreground">voice-service/</code>, then refresh.
      </p>
      <button onClick={studio.refreshSystem} className="text-xs text-accent hover:underline shrink-0">
        Retry
      </button>
    </div>
  );
}
