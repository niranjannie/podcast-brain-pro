"use client";

import { useMemo, useState } from "react";
import { Studio } from "@/lib/useStudio";
import { errorMessage } from "@/lib/studio-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorBanner, Field, SectionTitle, Select, TextArea, TextInput } from "./ui";
import { CheckCircle, Download, FlaskConical, Mic, Play, ShieldCheck, Upload, XCircle } from "lucide-react";

export function VoiceLabView({ studio }: { studio: Studio }) {
  const [engineId, setEngineId] = useState("kokoro");
  const [voice, setVoice] = useState("");
  const [text, setText] = useState("Welcome to the show. This voice is running entirely on your machine.");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultName, setResultName] = useState("voice-lab.wav");

  const [cloneEngine, setCloneEngine] = useState("chatterbox");
  const [cloneText, setCloneText] = useState("This is my voice, cloned locally from a short recording.");
  const [reference, setReference] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);

  const installed = useMemo(
    () => studio.engines.filter((e) => e.installed && e.health?.ok),
    [studio.engines]
  );
  const cloningEngines = useMemo(
    () => studio.engines.filter((e) => e.cloning && e.installed && e.health?.ok),
    [studio.engines]
  );
  const selectedEngine = studio.engines.find((e) => e.id === engineId);

  async function runTest() {
    setBusy(true);
    setError(null);
    try {
      const result = await studio.engineSpeak({ text, engine: engineId, voice: voice || undefined });
      if (resultUrl) URL.revokeObjectURL(resultUrl);
      setResultUrl(result.url);
      setResultName(result.filename);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function runClone() {
    if (!reference) {
      setError("Choose a reference recording first: 5-10 seconds of clean speech.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await studio.cloneVoice({ text: cloneText, engine: cloneEngine, reference, consent });
      if (resultUrl) URL.revokeObjectURL(resultUrl);
      setResultUrl(result.url);
      setResultName(result.filename);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Engine catalogue */}
      <section className="panel p-5 sm:p-6">
        <SectionTitle
          title="Engines"
          subtitle="Small local models you can add. Nothing is downloaded until you ask for it."
        />
        <div className="space-y-3">
          {studio.engines.length === 0 && (
            <p className="text-xs text-muted">
              The backend has not reported its engine catalogue yet. Start the backend to see what is
              installed.
            </p>
          )}
          {studio.engines.map((engine) => (
            <article key={engine.id} className="panel-inset p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h4 className="text-sm font-semibold flex items-center gap-2">
                    {engine.label}
                    {engine.installed && engine.health?.ok ? (
                      <Badge variant="success" className="text-[10px]">
                        <CheckCircle className="w-3 h-3" /> Ready
                      </Badge>
                    ) : engine.installed ? (
                      <Badge variant="error" className="text-[10px]">
                        <XCircle className="w-3 h-3" /> Broken here
                      </Badge>
                    ) : engine.wired ? (
                      <Badge variant="subtle" className="text-[10px]">
                        <XCircle className="w-3 h-3" /> Not installed
                      </Badge>
                    ) : (
                      <Badge variant="warning" className="text-[10px]">
                        Documented, not wired
                      </Badge>
                    )}
                  </h4>
                  <p className="text-[11px] text-muted mt-1.5 max-w-2xl leading-relaxed">{engine.notes}</p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    <Badge variant="subtle">{engine.license}</Badge>
                    <Badge variant="subtle">{engine.download}</Badge>
                    <Badge variant="subtle">{engine.memory}</Badge>
                    {engine.cloning && <Badge variant="accent">Voice cloning</Badge>}
                    {engine.commercial && <Badge variant="success">Commercial use</Badge>}
                  </div>
                </div>
              </div>
              {!engine.installed && (
                <code className="block mt-3 text-[11px] bg-surface-3 px-3 py-2 rounded-lg break-all">
                  {engine.install}
                </code>
              )}
              {engine.installed && !engine.health?.ok && (
                <p className="mt-3 text-[11px] text-warning leading-relaxed">{engine.health?.detail}</p>
              )}
            </article>
          ))}
        </div>
      </section>

      {/* Try an engine */}
      <section className="panel p-5 sm:p-6">
        <SectionTitle
          title="Try a small engine"
          subtitle="Kokoro is 82M parameters and runs on CPU, so it is the fastest way to hear a local voice."
        />
        <div className="grid sm:grid-cols-2 gap-4 mb-4">
          <Field label="Engine">
            {(id) => (
              <Select id={id} value={engineId} onChange={(e) => setEngineId(e.target.value)}>
                {installed.length === 0 && <option value="kokoro">kokoro (not installed)</option>}
                {installed
                  .filter((e) => e.id !== "vibevoice")
                  .map((engine) => (
                    <option key={engine.id} value={engine.id}>
                      {engine.label}
                    </option>
                  ))}
              </Select>
            )}
          </Field>
          <Field label="Voice" hint={selectedEngine?.voices.join(", ") || "Leave empty for the default voice"}>
            {(id) => (
              <TextInput id={id} value={voice} onChange={(e) => setVoice(e.target.value)} placeholder="af_heart" />
            )}
          </Field>
        </div>
        <Field label="Text">
          {(id) => <TextArea id={id} rows={2} value={text} onChange={(e) => setText(e.target.value)} />}
        </Field>
        <div className="mt-4">
          <Button variant="primary" onClick={runTest} disabled={busy || !text.trim()}>
            <Play className="w-4 h-4" /> {busy ? "Rendering..." : "Render with this engine"}
          </Button>
        </div>
      </section>

      {/* Cloning */}
      <section className="panel p-5 sm:p-6">
        <SectionTitle
          title="Clone a voice"
          subtitle="Give the engine 5-10 seconds of clean speech and it speaks new text in that voice."
        />
        {cloningEngines.length === 0 ? (
          <EmptyState
            icon={<FlaskConical className="w-6 h-6" />}
            title="No cloning engine installed yet"
            body="Install Chatterbox with 'pip install chatterbox-tts' (MIT licence) or Qwen3-TTS with 'pip install mlx-audio' (Apache-2.0). Chatterbox currently needs Python 3.10-3.12: its watermarking dependency chain breaks on Python 3.14."
          />
        ) : (
          <div className="space-y-4">
            <Field label="Cloning engine">
              {(id) => (
                <Select id={id} value={cloneEngine} onChange={(e) => setCloneEngine(e.target.value)}>
                  {cloningEngines.map((engine) => (
                    <option key={engine.id} value={engine.id}>
                      {engine.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Reference recording" hint="5-10 seconds, one speaker, no music or background noise.">
              {(id) => (
                <div className="flex items-center gap-3">
                  <input
                    id={id}
                    type="file"
                    accept="audio/*"
                    onChange={(e) => setReference(e.target.files?.[0] ?? null)}
                    className="text-xs text-muted file:mr-3 file:rounded-lg file:border file:border-border file:bg-surface-2 file:px-3 file:py-2 file:text-foreground"
                  />
                  <Upload className="w-4 h-4 text-muted" />
                </div>
              )}
            </Field>
            <Field label="Text to speak">
              {(id) => <TextArea id={id} rows={2} value={cloneText} onChange={(e) => setCloneText(e.target.value)} />}
            </Field>
            <label className="flex items-start gap-2.5 text-xs text-muted cursor-pointer">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-0.5"
              />
              <span>
                <ShieldCheck className="w-3.5 h-3.5 inline mr-1 text-success" />
                This is my own voice, or I have written permission from the speaker to clone it. The
                confirmation is stored next to the reference file.
              </span>
            </label>
            <Button variant="primary" onClick={runClone} disabled={busy || !consent || !cloneText.trim()}>
              <Mic className="w-4 h-4" /> {busy ? "Cloning..." : "Clone and speak"}
            </Button>
          </div>
        )}
      </section>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {resultUrl && (
        <section className="panel p-5 sm:p-6">
          <SectionTitle title="Result" subtitle="Rendered locally and normalised to podcast loudness" />
          <audio key={resultUrl} controls className="w-full rounded-lg" src={resultUrl} />
          <div className="mt-3">
            <Button variant="secondary" asChild>
              <a href={resultUrl} download={resultName}>
                <Download className="w-4 h-4" /> Download
              </a>
            </Button>
          </div>
        </section>
      )}
    </div>
  );
}
