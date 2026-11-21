"use client";

import { useEffect, useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ErrorBanner, TextInput } from "./ui";
import { ConfigStatus, errorMessage } from "@/lib/studio-types";

const KEYS = [
  { id: "DIALOGRAM_API_KEY", label: "Dialogram", desc: "Primary script provider (Qwen 3.6 Plus)", link: "https://dialogram.me/" },
  { id: "GROQ_API_KEY", label: "Groq", desc: "Fast fallback (openai/gpt-oss-120b)", link: "https://console.groq.com/keys" },
  { id: "SARVAM_API_KEY", label: "Sarvam", desc: "Indian-language TTS", link: "https://dashboard.sarvam.ai/" },
  { id: "TAVILY_API_KEY", label: "Tavily", desc: "Live web research", link: "https://app.tavily.com/home" },
  { id: "GEMINI_API_KEY", label: "Gemini", desc: "Google fallback", link: "https://aistudio.google.com/api-keys" },
  { id: "MISTRAL_API_KEY", label: "Mistral", desc: "Mistral fallback", link: "https://console.mistral.ai/home" },
  { id: "DEEPSEEK_API_KEY", label: "DeepSeek", desc: "DeepSeek fallback", link: "https://platform.deepseek.com/api_keys" },
  { id: "TOGETHER_API_KEY", label: "Together AI", desc: "Together fallback", link: "https://api.together.ai/settings/api-keys" },
  { id: "OPENROUTER_API_KEY", label: "OpenRouter", desc: "Last fallback, free model picked live", link: "https://openrouter.ai/settings/keys" },
];

export function SettingsModal({
  isOpen,
  onClose,
  config,
  onSaved,
}: {
  isOpen: boolean;
  onClose: () => void;
  config: Record<string, ConfigStatus>;
  onSaved: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [cleared, setCleared] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // The form starts empty: the mask is a hint, never a value that gets saved back.
  useEffect(() => {
    if (isOpen) {
      setValues({});
      setCleared([]);
      setSaveError(null);
    }
  }, [isOpen]);

  async function save() {
    const payload: Record<string, string | null> = {};
    for (const key of KEYS) {
      const value = (values[key.id] ?? "").trim();
      if (value) payload[key.id] = value;
      else if (cleared.includes(key.id)) payload[key.id] = null;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      onSaved();
      onClose();
    } catch (error) {
      setSaveError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="API keys" className="max-w-3xl">
      <p className="text-xs text-muted mb-5">
        Keys stay on this machine in <code>voice-service/user_config.json</code>. They are only sent to
        the provider they belong to. Ollama needs no key and keeps scripting fully offline.
      </p>
      <div className="space-y-4">
        {KEYS.map((key) => {
          const status = config[key.id];
          return (
            <div key={key.id} className="flex flex-col sm:flex-row sm:items-center gap-3 pb-4 border-b border-border last:border-0">
              <div className="flex-1">
                <p className="text-sm font-semibold">{key.label}</p>
                <p className="text-[11px] text-muted">{key.desc}</p>
                <a href={key.link} target="_blank" rel="noreferrer" className="text-[11px] text-accent hover:underline">
                  Get a key →
                </a>
              </div>
              <div className="sm:w-[300px]">
                <div className="mb-1.5">
                  {status?.configured ? (
                    <Badge variant="success" className="text-[10px]">Configured · {status.masked}</Badge>
                  ) : (
                    <Badge variant="subtle" className="text-[10px]">Not configured</Badge>
                  )}
                </div>
                <TextInput
                  type="password"
                  value={values[key.id] ?? ""}
                  onChange={(e) => {
                    setValues((previous) => ({ ...previous, [key.id]: e.target.value }));
                    setCleared((previous) => previous.filter((id) => id !== key.id));
                  }}
                  placeholder={status?.masked ? `Currently ${status.masked}` : "Paste a new key"}
                  aria-label={`${key.label} API key`}
                />
                {status?.configured && (
                  <button
                    type="button"
                    onClick={() => {
                      setValues((previous) => ({ ...previous, [key.id]: "" }));
                      setCleared((previous) => (previous.includes(key.id) ? previous : [...previous, key.id]));
                    }}
                    className="mt-1 text-[11px] text-muted hover:text-error"
                  >
                    {cleared.includes(key.id) ? "Will be removed on save" : "Remove this key"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {saveError && (
        <div className="mt-4">
          <ErrorBanner message={saveError} onDismiss={() => setSaveError(null)} />
        </div>
      )}
      <div className="mt-6 flex gap-3">
        <Button variant="primary" onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save changes"}
        </Button>
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </div>
    </Modal>
  );
}

export function HelpModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Setup and engines" className="max-w-3xl">
      <div className="space-y-5 text-xs text-muted leading-relaxed">
        <section>
          <h4 className="text-sm font-semibold text-foreground mb-2">Run the app</h4>
          <code className="block bg-surface-2 border border-border rounded-lg p-3 whitespace-pre-wrap">{`cd voice-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ../vibevoice-src && pip install -e . && cd ../voice-service
cp .env.example .env        # add at least one LLM key
uvicorn main:app --host 0.0.0.0 --port 8000

# in a second terminal
cd frontend && npm install && npm run dev`}</code>
          <p className="mt-2">
            The studio opens at <code>http://localhost:3000</code>, the marketing page at{" "}
            <code>/landing</code>. transformers must stay below 5.0 or VibeVoice fails to import.
          </p>
        </section>
        <section>
          <h4 className="text-sm font-semibold text-foreground mb-2">Which engine renders my episode?</h4>
          <ul className="list-disc pl-5 space-y-1">
            <li>English monologue up to 10 minutes: VibeVoice Realtime 0.5B (~2 GB).</li>
            <li>English interview, panel or long episodes: VibeVoice Longform 1.5B (~5.4 GB).</li>
            <li>Indian languages: Sarvam cloud, needs a key.</li>
            <li>Voice Lab engines: Kokoro 82M (~300 MB, CPU) and Chatterbox for cloning.</li>
          </ul>
        </section>
        <section>
          <h4 className="text-sm font-semibold text-foreground mb-2">Delivery markers</h4>
          <p>
            <code className="directive">[[pause:0.8]]</code> inserts real silence after the words before
            it. <code className="directive">[[style:calm]]</code> changes the delivery for the rest of that
            line. Styles: neutral, calm, narrative, serious, warm, excited.
          </p>
        </section>
        <section>
          <h4 className="text-sm font-semibold text-foreground mb-2">Publishing</h4>
          <p>
            Set <code>PUBLIC_BASE_URL</code> to a public address before submitting{" "}
            <code>/feed/podcast.rss</code> to a podcast host, otherwise the enclosure URLs point at your
            laptop. Every export is normalised to -16 LUFS.
          </p>
        </section>
        <section>
          <h4 className="text-sm font-semibold text-foreground mb-2">A note on the default model</h4>
          <p>
            The bundled VibeVoice weights carry a research-use model card, cover English and Chinese, and
            embed an audible AI disclaimer plus a watermark. Microsoft removed the TTS inference code
            upstream, so the vendored copy in <code>vibevoice-src/</code> is pinned and must not be synced
            with upstream.
          </p>
        </section>
      </div>
    </Modal>
  );
}
