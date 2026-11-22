"use client";

import { useEffect, useRef, useState } from "react";
import { Studio } from "@/lib/useStudio";
import { SocialClip, errorMessage } from "@/lib/studio-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorBanner, SectionTitle } from "./ui";
import { Check, Copy, Download, ListVideo, RefreshCw, Scissors } from "lucide-react";

function chapterTime(seconds?: number): string {
  if (seconds === undefined) return "after render";
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60);
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

export function ExtrasView({ studio }: { studio: Studio }) {
  const [busyClip, setBusyClip] = useState<number | null>(null);
  const [clipResults, setClipResults] = useState<Record<number, { url: string; filename: string }>>({});
  const clipResultsRef = useRef<Record<number, { url: string; filename: string }>>({});
  const clipRunIdRef = useRef(0);
  const mountedRef = useRef(true);
  const [copied, setCopied] = useState<number | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clipRunIdRef.current += 1;
      Object.values(clipResultsRef.current).forEach((result) => URL.revokeObjectURL(result.url));
    };
  }, []);

  useEffect(() => {
    clipRunIdRef.current += 1;
    Object.values(clipResultsRef.current).forEach((result) => URL.revokeObjectURL(result.url));
    clipResultsRef.current = {};
    setClipResults({});
    setBusyClip(null);
  }, [studio.script, studio.extras]);

  async function renderClip(clip: SocialClip, index: number) {
    const runId = ++clipRunIdRef.current;
    const sourceScript = studio.script;
    const sourceExtras = studio.extras;
    setBusyClip(index);
    studio.setExtrasError(null);
    try {
      const result = await studio.renderSocialClip(clip);
      if (!mountedRef.current || runId !== clipRunIdRef.current || studio.script !== sourceScript || studio.extras !== sourceExtras) {
        URL.revokeObjectURL(result.url);
        return;
      }
      const previous = clipResults[index];
      if (previous) URL.revokeObjectURL(previous.url);
      const next = { ...clipResultsRef.current, [index]: result };
      clipResultsRef.current = next;
      setClipResults(next);
    } catch (error) {
      if (mountedRef.current && runId === clipRunIdRef.current) studio.setExtrasError(errorMessage(error));
    } finally {
      if (mountedRef.current && runId === clipRunIdRef.current) setBusyClip(null);
    }
  }

  async function copyCaption(caption: string, index: number) {
    await navigator.clipboard.writeText(caption);
    setCopied(index);
  }

  if (!studio.script) return null;

  const extras = studio.extras;
  return (
    <section className="panel p-5 sm:p-6">
      <SectionTitle
        title="Show notes & distribution"
        subtitle="Grounded in the current script; refresh after editing without rewriting the episode."
        action={(
          <Button variant="secondary" size="sm" onClick={studio.generateExtras} disabled={studio.isGeneratingExtras || !studio.topic.trim()}>
            <RefreshCw className={`w-3.5 h-3.5 ${studio.isGeneratingExtras ? "animate-spin" : ""}`} />
            {studio.isGeneratingExtras ? "Refreshing..." : "Refresh extras"}
          </Button>
        )}
      />

      {studio.extrasError && (
        <div className="mb-4">
          <ErrorBanner message={studio.extrasError} onDismiss={() => studio.setExtrasError(null)} />
        </div>
      )}
      {studio.isGeneratingExtras && <div className="activity-bar h-1.5 rounded-full bg-surface-2 mb-4" />}

      {!extras && !studio.isGeneratingExtras && (
        <EmptyState
          icon={<ListVideo className="w-6 h-6" />}
          title="No content extras yet"
          body="Generate the script with extras, or refresh them here after the script is ready."
        />
      )}

      {extras && (
        <div className="space-y-5">
          <div>
            <Badge variant="accent">{extras.title}</Badge>
            <p className="text-sm mt-3 leading-relaxed">{extras.summary}</p>
            <p className="text-xs text-muted mt-2 leading-relaxed">{extras.description}</p>
          </div>

          <div>
            <h4 className="text-xs font-semibold mb-2">Key takeaways</h4>
            <ul className="space-y-1.5 text-xs text-muted list-disc pl-4">
              {extras.takeaways.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>

          {extras.chapters.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold mb-2">Chapters</h4>
              <div className="divide-y divide-border rounded-lg border border-border overflow-hidden">
                {extras.chapters.map((chapter) => (
                  <div key={`${chapter.start_turn}-${chapter.title}`} className="flex items-center gap-3 px-3 py-2 text-xs">
                    <span className="w-20 shrink-0 text-accent">{chapterTime(chapter.startTime)}</span>
                    <span>{chapter.title}</span>
                    <span className="ml-auto text-[10px] text-muted">turn {chapter.start_turn + 1}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <h4 className="text-xs font-semibold mb-2">Social captions</h4>
            <div className="space-y-2">
              {extras.social_captions.map((caption, index) => (
                <div key={index} className="flex items-start gap-2 panel-inset p-3">
                  <p className="text-xs text-muted flex-1 leading-relaxed">{caption}</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Copy caption ${index + 1}`}
                    onClick={() => copyCaption(caption, index)}
                  >
                    {copied === index ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
                  </Button>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-xs font-semibold mb-2">Social clips</h4>
            <div className="grid lg:grid-cols-3 gap-3">
              {extras.social_clips.map((clip, index) => {
                const result = clipResults[index];
                return (
                  <article key={`${clip.start_turn}-${clip.end_turn}-${clip.title}`} className="panel-inset p-4 space-y-3">
                    <div>
                      <h5 className="text-xs font-semibold">{clip.title}</h5>
                      <p className="text-[10px] text-muted mt-1">Turns {clip.start_turn + 1}–{clip.end_turn + 1}</p>
                    </div>
                    <p className="text-xs text-muted leading-relaxed">{clip.caption}</p>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => renderClip(clip, index)}
                      disabled={busyClip !== null}
                    >
                      <Scissors className="w-3.5 h-3.5" />
                      {busyClip === index ? "Rendering..." : "Render clip"}
                    </Button>
                    {result && (
                      <div className="space-y-2">
                        <audio controls className="w-full h-9" src={result.url} />
                        <Button variant="ghost" size="sm" asChild>
                          <a href={result.url} download={result.filename}>
                            <Download className="w-3.5 h-3.5" /> Download clip
                          </a>
                        </Button>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
