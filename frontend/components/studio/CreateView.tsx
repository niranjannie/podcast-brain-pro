"use client";

import { useEffect, useRef, useState } from "react";
import { Studio } from "@/lib/useStudio";
import { Format, Language } from "@/lib/studio-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorBanner, Field, SectionTitle, Select, TextArea, TextInput } from "./ui";
import { ExtrasView } from "./ExtrasView";
import {
  AudioLines,
  Clock,
  Download,
  FileJson,
  PauseCircle,
  Play,
  Rss,
  Sparkles,
  Square,
  Volume2,
  Wand2,
} from "lucide-react";

const FORMATS: { value: Format; label: string; hint: string }[] = [
  { value: "monologue", label: "Monologue", hint: "One host" },
  { value: "interview", label: "Interview", hint: "Two voices" },
  { value: "panel", label: "Panel", hint: "Three voices" },
];

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "en", label: "English (local)" },
  { value: "hi-IN", label: "Hindi" },
  { value: "ta-IN", label: "Tamil" },
  { value: "te-IN", label: "Telugu" },
  { value: "kn-IN", label: "Kannada" },
  { value: "bn-IN", label: "Bengali" },
  { value: "mr-IN", label: "Marathi" },
  { value: "gu-IN", label: "Gujarati" },
  { value: "ml-IN", label: "Malayalam" },
  { value: "pa-IN", label: "Punjabi" },
  { value: "od-IN", label: "Odia" },
];

export function CreateView({ studio }: { studio: Studio }) {
  const [previewing, setPreviewing] = useState<number | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewResults, setPreviewResults] = useState<Record<number, { url: string; filename: string; key: string }>>({});
  const previewResultsRef = useRef<Record<number, { url: string; filename: string; key: string }>>({});
  const previewsMountedRef = useRef(true);

  useEffect(() => {
    previewsMountedRef.current = true;
    return () => {
      previewsMountedRef.current = false;
      Object.values(previewResultsRef.current).forEach((result) => URL.revokeObjectURL(result.url));
    };
  }, []);
  const audioDisabledReason = !studio.script
    ? "Generate a script first"
    : studio.isGeneratingAudio
      ? "Generation in progress"
      : studio.isIndic && !studio.config.SARVAM_API_KEY?.configured
        ? "Add a Sarvam key in Keys to render Indian languages"
        : !studio.isIndic && !studio.usesVibeVoice && !studio.selectedEngineInfo?.health?.ok
          ? "Install and check this engine in Voice Lab"
          : studio.episodeEngine === "chatterbox" && studio.availableVoices.length === 0
            ? "Create a consented Chatterbox voice in Voice Lab first"
            : !studio.isIndic && studio.usesVibeVoice && !studio.modelCached
              ? "The model is still downloading"
              : null;
  const engineOptions = studio.engines.filter(
    (engine) => engine.wired && engine.installed && engine.health?.ok
  );
  const selectedEngineMissing = !engineOptions.some((engine) => engine.id === studio.episodeEngine);

  return (
    <div className="space-y-6">
      {/* Brief */}
      <section className="panel p-5 sm:p-6">
        <SectionTitle
          title="Brief"
          subtitle="What should this episode be about?"
          action={<Badge variant="accent">{studio.engineLabel}</Badge>}
        />
        <div className="space-y-4">
          <Field label="Topic">
            {(id) => (
              <TextArea
                id={id}
                value={studio.topic}
                onChange={(e) => studio.setTopic(e.target.value)}
                placeholder="e.g. Why Indian cities flood every monsoon, explained with a city planner"
                rows={2}
              />
            )}
          </Field>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Field label="Format">
              {(id) => (
                <Select id={id} value={studio.format} onChange={(e) => studio.setFormat(e.target.value as Format)}>
                  {FORMATS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label} · {item.hint}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Language">
              {(id) => (
                <Select id={id} value={studio.language} onChange={(e) => studio.setLanguage(e.target.value as Language)}>
                  {LANGUAGES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Engine" hint={studio.isIndic ? "Indian languages use Sarvam" : "VibeVoice, lightweight presets, or your cloned voices"}>
              {(id) => (
                <Select
                  id={id}
                  value={studio.isIndic ? "sarvam" : studio.episodeEngine}
                  disabled={studio.isIndic}
                  onChange={(e) => studio.setEpisodeEngine(e.target.value)}
                >
                  {studio.isIndic ? (
                    <option value="sarvam">Sarvam Cloud</option>
                  ) : (
                    <>
                      {selectedEngineMissing && (
                        <option value={studio.episodeEngine} disabled>
                          {studio.selectedEngineInfo?.label ?? studio.episodeEngine} (unavailable)
                        </option>
                      )}
                      {engineOptions.map((engine) => (
                        <option key={engine.id} value={engine.id}>{engine.label}</option>
                      ))}
                    </>
                  )}
                </Select>
              )}
            </Field>
            <Field label="Delivery" hint="Tone for the whole episode">
              {(id) => (
                <Select
                  id={id}
                  value={studio.deliveryStyle}
                  onChange={(e) => studio.setDeliveryStyle(e.target.value as Studio["deliveryStyle"])}
                >
                  {["neutral", "calm", "narrative", "serious", "warm", "excited"].map((style) => (
                    <option key={style} value={style}>
                      {style[0].toUpperCase() + style.slice(1)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>

          <div>
            <span className="block text-xs font-medium text-muted mb-1.5">Length</span>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Episode length in minutes">
              {studio.durations.map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={studio.duration === value}
                  onClick={() => studio.setDuration(value)}
                  className={
                    studio.duration === value
                      ? "px-4 py-1.5 rounded-lg text-sm font-semibold bg-accent/20 border border-accent/50 text-foreground"
                      : "px-4 py-1.5 rounded-lg text-sm bg-surface-2 border border-border text-muted hover:text-foreground"
                  }
                >
                  {value} min
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Cast */}
      <section className="panel p-5 sm:p-6">
        <SectionTitle title="Cast" subtitle="Name each host and give them a distinct voice" />
        <div className="grid sm:grid-cols-3 gap-4">
          {studio.speakers.map((speaker, index) => (
            <div key={index} className="panel-inset p-3 space-y-3">
              <Field label={speaker || `Host ${index + 1}`}>
                {(id) => (
                  <TextInput
                    id={id}
                    value={studio.speakerNames[index] ?? ""}
                    onChange={(e) => studio.renameSpeaker(index, e.target.value)}
                  />
                )}
              </Field>
              <Field label="Voice">
                {(id) => (
                  <Select
                    id={id}
                    value={studio.voiceSelections[index] ?? studio.availableVoices[0]}
                    onChange={(e) => {
                      const next = [...studio.voiceSelections];
                      next[index] = e.target.value;
                      studio.setVoiceSelections(next);
                    }}
                  >
                    {studio.availableVoices.map((voice) => (
                      <option key={voice} value={voice}>
                        {studio.voiceLabels[voice] ?? voice}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Button
                variant="ghost"
                size="sm"
                disabled={previewing !== null || !studio.voiceSelections[index]}
                onClick={async () => {
                  setPreviewing(index);
                  setPreviewError(null);
                  try {
                    const voice = studio.voiceSelections[index];
                    const key = `${studio.episodeEngine}:${voice}:${speaker}:${studio.language}:${studio.deliveryStyle}`;
                    const result = await studio.auditionVoice(voice, speaker);
                    if (!previewsMountedRef.current) {
                      URL.revokeObjectURL(result.url);
                      return;
                    }
                    const previous = previewResultsRef.current[index];
                    if (previous) URL.revokeObjectURL(previous.url);
                    const next = { ...previewResultsRef.current, [index]: { ...result, key } };
                    previewResultsRef.current = next;
                    setPreviewResults(next);
                  } catch (error) {
                    if (previewsMountedRef.current) setPreviewError(error instanceof Error ? error.message : String(error));
                  } finally {
                    if (previewsMountedRef.current) setPreviewing(null);
                  }
                }}
              >
                <Play className="w-3.5 h-3.5" />
                {previewing === index ? "Rendering preview..." : "Preview voice"}
              </Button>
              {previewResults[index]?.key === `${studio.episodeEngine}:${studio.voiceSelections[index]}:${speaker}:${studio.language}:${studio.deliveryStyle}` && (
                <audio
                  key={previewResults[index].url}
                  controls
                  className="w-full h-9"
                  src={previewResults[index].url}
                  aria-label={`Preview ${speaker}`}
                />
              )}
            </div>
          ))}
        </div>
        {previewError && (
          <div className="mt-3"><ErrorBanner message={previewError} onDismiss={() => setPreviewError(null)} /></div>
        )}
        {studio.isIndic && (
          <p className="text-[11px] text-muted mt-3">
            Sarvam renders each turn with the selected speaker voice, then stitches the conversation with its pauses and delivery settings.
          </p>
        )}
      </section>

      {/* Script */}
      <section className="panel p-5 sm:p-6">
        <SectionTitle
          title="Script"
          subtitle={studio.scriptStats || "Research, write, then edit the words before they are spoken"}
          action={
            studio.script ? <Badge variant="subtle">{studio.scriptWordCount} words</Badge> : undefined
          }
        />
        <div className="flex flex-wrap gap-2 mb-4">
          <Button
            variant="primary"
            onClick={studio.generateScript}
            disabled={studio.isGeneratingScript || !studio.topic.trim()}
          >
            <Sparkles className="w-4 h-4" />
            {studio.isGeneratingScript ? "Writing..." : "Generate script"}
          </Button>
          {studio.isGeneratingScript && (
            <Button variant="ghost" onClick={studio.stopScriptGeneration}>
              <Square className="w-3.5 h-3.5" /> Stop
            </Button>
          )}
          <Button variant="secondary" onClick={studio.saveEdits} disabled={!studio.hasEdits}>
            Save edits
          </Button>
          <Button variant="secondary" onClick={studio.generateAudio} disabled={audioDisabledReason !== null}
            title={audioDisabledReason ?? undefined}>
            <Volume2 className="w-4 h-4" />
            {studio.isGeneratingAudio ? "Rendering..." : "Generate audio"}
          </Button>
        </div>

        {studio.scriptError && (
          <div className="mb-4">
            <ErrorBanner message={studio.scriptError} onDismiss={() => studio.setScriptError(null)} />
          </div>
        )}

        {studio.isGeneratingScript && (
          <div className="space-y-2 py-2">
            <div className="activity-bar h-1.5 rounded-full bg-surface-2" />
            <p className="text-xs text-muted">Researching the topic and writing the script...</p>
          </div>
        )}

        {!studio.script && !studio.isGeneratingScript && !studio.scriptError && (
          <EmptyState
            icon={<Wand2 className="w-6 h-6" />}
            title="No script yet"
            body="Write a topic above and press Generate script. The writer marks pauses and tonal shifts that the audio engine renders."
          />
        )}

        {studio.script && (
          <div className="space-y-4 max-h-[420px] overflow-y-auto pr-1">
            {studio.script.map((line, index) => (
              <div key={index} className="panel-inset p-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-accent">
                    {line.speaker}
                  </span>
                  {studio.editedLines[index] !== undefined &&
                    studio.editedLines[index] !== line.content && (
                      <span className="text-[10px] text-muted">edited</span>
                    )}
                  <button
                    type="button"
                    onClick={() => studio.addPause(index)}
                    title="Add a 0.6 second pause at the end of this line"
                    className="ml-auto inline-flex items-center gap-1 rounded-md border border-border px-1.5 py-0.5 text-[10px] text-muted hover:text-foreground"
                  >
                    <PauseCircle className="w-3 h-3" /> pause
                  </button>
                </div>
                <TextArea
                  aria-label={`Line for ${line.speaker}`}
                  value={studio.editedLines[index] ?? line.content}
                  onChange={(e) => studio.editLine(index, e.target.value)}
                  rows={2}
                  className="bg-transparent border-0 px-0"
                />
              </div>
            ))}
          </div>
        )}

        {studio.script && (
          <p className="text-[11px] text-muted mt-3 leading-relaxed">
            Delivery markers stay in the text: <code className="directive">[[pause:0.8]]</code> becomes
            real silence, <code className="directive">[[style:calm]]</code> changes the delivery. Both are
            stripped from the spoken words.
          </p>
        )}
      </section>

      <ExtrasView studio={studio} />

      {/* Audio */}
      <section className="panel p-5 sm:p-6">
        <SectionTitle
          title="Audio"
          subtitle={studio.audioStatusText || "Rendered locally, normalised to podcast loudness"}
          action={studio.audioStats ? <Badge variant="success">{studio.audioStats}</Badge> : undefined}
        />

        {studio.audioError && (
          <div className="mb-4">
            <ErrorBanner message={studio.audioError} onDismiss={() => studio.setAudioError(null)} />
          </div>
        )}

        {studio.isGeneratingAudio && (
          <div className="space-y-2 mb-4">
            <div className="activity-bar h-1.5 rounded-full bg-surface-2" />
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted inline-flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                {Math.floor(studio.audioElapsed / 60)}m {studio.audioElapsed % 60}s elapsed
              </p>
              <Button variant="ghost" size="sm" onClick={studio.cancelAudio}>
                <Square className="w-3.5 h-3.5" /> Cancel
              </Button>
            </div>
          </div>
        )}

        {studio.audioUrl && (
          <div className="space-y-4">
            <audio key={studio.audioUrl} controls className="w-full rounded-lg" src={studio.audioUrl} />
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" asChild>
                <a href={studio.audioUrl} download={studio.audioFilename}>
                  <Download className="w-4 h-4" /> WAV
                </a>
              </Button>
              <Button variant="secondary" onClick={studio.downloadTranscript}>
                <FileJson className="w-4 h-4" /> Script JSON
              </Button>
              <Button variant="secondary" asChild>
                <a href="/feed/podcast.rss" target="_blank" rel="noreferrer">
                  <Rss className="w-4 h-4" /> RSS feed
                </a>
              </Button>
            </div>
          </div>
        )}

        {!studio.audioUrl && !studio.isGeneratingAudio && (
          <EmptyState
            icon={<AudioLines className="w-6 h-6" />}
            title="No audio yet"
            body="Generate a script, then press Generate audio. English multi-host episodes use the local VibeVoice model; Indian languages use Sarvam."
          />
        )}
      </section>
    </div>
  );
}

export function PlayButton({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} className="inline-flex items-center gap-1 text-accent hover:underline text-xs">
      <Play className="w-3.5 h-3.5" /> Play
    </button>
  );
}
