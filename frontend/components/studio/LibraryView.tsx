"use client";

import { Studio } from "@/lib/useStudio";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorBanner, TextInput } from "./ui";
import { formatBytes, formatDate } from "@/lib/utils";
import { Download, FolderOpen, Pencil, Play, RefreshCcw, RotateCcw, Rss, Search, Trash2 } from "lucide-react";

export function LibraryView({ studio, onEdit }: { studio: Studio; onEdit: () => void }) {
  return (
    <div className="space-y-4">
      <div className="panel p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-muted" />
          <TextInput
            value={studio.historySearch}
            onChange={(e) => studio.setHistorySearch(e.target.value)}
            placeholder="Search by topic, filename, language..."
            aria-label="Search episodes"
            className="pl-9"
          />
        </div>
        <Button variant="ghost" size="sm" onClick={studio.refreshHistory}>
          <RotateCcw className="w-4 h-4" /> Refresh
        </Button>
        <Button variant="secondary" size="sm" asChild>
          <a href="/feed/podcast.rss" target="_blank" rel="noreferrer">
            <Rss className="w-4 h-4" /> Feed
          </a>
        </Button>
      </div>

      {studio.audioUrl && (
        <div className="panel p-4">
          <p className="text-xs font-medium mb-2 break-all">{studio.audioFilename}</p>
          <audio key={studio.audioUrl} controls className="w-full" src={studio.audioUrl} />
        </div>
      )}

      {studio.historyError && (
        <ErrorBanner message={studio.historyError} onDismiss={() => studio.setHistoryError(null)} />
      )}

      {studio.filteredHistory.length === 0 ? (
        <EmptyState
          icon={<FolderOpen className="w-6 h-6" />}
          title={studio.historySearch ? "No episodes match that search" : "No episodes yet"}
          body="Episodes you render are saved on this machine with their metadata, transcript and loudness measurement."
        />
      ) : (
        <div className="space-y-2">
          {studio.filteredHistory.map((item) => (
            <article key={item.filename} className="panel p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  {studio.renamingFile === item.filename ? (
                    <form
                      className="flex gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const stem = studio.renameValue.trim().replace(/\.wav$/i, "");
                        if (stem) studio.renameFile(item.filename, `${stem}.wav`);
                      }}
                    >
                      <TextInput
                        value={studio.renameValue}
                        onChange={(e) => studio.setRenameValue(e.target.value)}
                        aria-label="New episode name"
                        autoFocus
                      />
                      <Button variant="primary" size="sm" type="submit">
                        Save
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => studio.setRenamingFile(null)}>
                        Cancel
                      </Button>
                    </form>
                  ) : (
                    <>
                      <h3 className="text-sm font-semibold truncate">
                        {item.topic || item.title || item.filename.replace(/\.wav$/, "").replace(/_/g, " ")}
                      </h3>
                      <p className="text-[11px] text-muted mt-1 break-all">{item.filename}</p>
                    </>
                  )}
                  <div className="flex flex-wrap gap-2 mt-2">
                    {item.format && <Badge variant="subtle">{item.format}</Badge>}
                    {item.language && <Badge variant="subtle">{item.language}</Badge>}
                    {item.engine && <Badge variant="accent">{item.engine}</Badge>}
                    <Badge variant="subtle">{formatBytes(item.size_bytes)}</Badge>
                    {item.duration_seconds ? (
                      <Badge variant="subtle">{Math.round(item.duration_seconds)}s</Badge>
                    ) : null}
                    {item.loudness && (
                      <Badge variant="success">{item.loudness.integrated_lufs.toFixed(1)} LUFS</Badge>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => studio.playEpisode(item)}
                    className="p-2 rounded-lg text-muted hover:text-accent"
                    aria-label={`Play ${item.filename}`}
                    title="Play"
                  >
                    <Play className="w-4 h-4" />
                  </button>
                  <a
                    href={`/outputs/${encodeURIComponent(item.filename)}`}
                    download
                    className="p-2 rounded-lg text-muted hover:text-accent"
                    aria-label={`Download ${item.filename}`}
                    title="Download"
                  >
                    <Download className="w-4 h-4" />
                  </a>
                  {item.has_transcript && (
                    <button
                      onClick={async () => {
                        if (await studio.loadEpisodeForRerender(item)) onEdit();
                      }}
                      className="p-2 rounded-lg text-muted hover:text-accent"
                      aria-label={`Re-render ${item.filename}`}
                      title="Load script and re-render without generating a new script"
                    >
                      <RefreshCcw className="w-4 h-4" />
                    </button>
                  )}
                  <button
                    onClick={() => {
                      studio.setRenamingFile(item.filename);
                      studio.setRenameValue(item.filename.replace(/\.wav$/i, ""));
                    }}
                    className="p-2 rounded-lg text-muted hover:text-accent"
                    aria-label={`Rename ${item.filename}`}
                    title="Rename"
                  >
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => studio.deleteFile(item.filename)}
                    onBlur={() => studio.setPendingDelete(null)}
                    className={
                      studio.pendingDelete === item.filename
                        ? "px-2 py-1 rounded-lg text-[11px] text-error border border-error/40"
                        : "p-2 rounded-lg text-muted hover:text-error"
                    }
                    aria-label={`Delete ${item.filename}`}
                    title={studio.pendingDelete === item.filename ? "Click again to confirm" : "Delete"}
                  >
                    {studio.pendingDelete === item.filename ? "Confirm?" : <Trash2 className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <p className="text-[10px] text-muted mt-2">{formatDate(item.created_at)}</p>
            </article>
          ))}
        </div>
      )}

      {studio.history.length >= studio.historyLimit && !studio.historySearch && (
        <div className="text-center">
          <Button variant="ghost" size="sm" onClick={studio.loadMore}>
            Load more episodes
          </Button>
        </div>
      )}
    </div>
  );
}
