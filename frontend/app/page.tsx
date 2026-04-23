"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { gsap, useGSAP } from "@/lib/gsap";
import {
  Mic,
  Wand2,
  Clock,
  Settings,
  HelpCircle,
  Info,
  Play,
  Download,
  History,
  AlertTriangle,
  Zap,
  Sparkles,
  Cpu,
  Globe,
  Volume2,
  ChevronRight,
  ChevronDown,
  Save,
  RotateCcw,
  Layers,
  Pencil,
  Trash2,
  Filter,
  CheckCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";

import { Modal } from "@/components/ui/modal";
import { cn, formatBytes, formatDate, formatDuration } from "@/lib/utils";

// ================= Types =================
type Format = "monologue" | "interview" | "panel";
type Language = "en" | "hi-IN" | "ta-IN" | "te-IN" | "kn-IN" | "bn-IN" | "mr-IN" | "gu-IN" | "ml-IN" | "pa-IN" | "od-IN";
interface ScriptLine {
  speaker: string;
  content: string;
}

interface ConfigStatus {
  configured: boolean;
  masked: string;
}

interface HistoryItem {
  filename: string;
  size_bytes: number;
  created_at: string;
  topic?: string;
  title?: string;
  word_count?: number;
  format?: string;
  language?: string;
  provider?: string;
  duration_seconds?: number;
}

// ================= Config =================
const DURATIONS = [2, 5, 10, 15, 30];

const FORMATS: { value: Format; label: string }[] = [
  { value: "monologue", label: "Solo Monologue" },
  { value: "interview", label: "Two-Person Interview" },
  { value: "panel", label: "Three-Person Panel" },
];

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "en", label: "🇺🇸 English (local · fast)" },
  { value: "hi-IN", label: "🇮🇳 Hindi (Sarvam)" },
  { value: "ta-IN", label: "🇮🇳 Tamil (Sarvam)" },
  { value: "te-IN", label: "🇮🇳 Telugu (Sarvam)" },
  { value: "kn-IN", label: "🇮🇳 Kannada (Sarvam)" },
  { value: "bn-IN", label: "🇮🇳 Bengali (Sarvam)" },
  { value: "mr-IN", label: "🇮🇳 Marathi (Sarvam)" },
  { value: "gu-IN", label: "🇮🇳 Gujarati (Sarvam)" },
  { value: "ml-IN", label: "🇮🇳 Malayalam (Sarvam)" },
  { value: "pa-IN", label: "🇮🇳 Punjabi (Sarvam)" },
  { value: "od-IN", label: "🇮🇳 Odia (Sarvam)" },
];

const LONGFORM_VOICES = ["Alice", "Carter", "Frank"];
const REALTIME_VOICES = ["Carter", "Emma", "Davis", "Grace", "Mike", "Wayne"];
const SARVAM_VOICES = ["shubh", "shreya", "manan", "ishita", "aditya", "ritu", "priya", "neha", "rahul", "pooja", "rohan", "simran", "kavya", "amit", "dev"];

const SCRIPT_ESTIMATES: Record<number, string> = {
  2: "~10–20s",
  5: "~20–40s",
  10: "~30–90s",
  15: "~1–3min",
  30: "~2–5min",
};

// ================= Helpers =================
function getEngineBadge(lang: Language, format: Format, duration: number) {
  if (lang !== "en") return { label: "Sarvam Cloud", variant: "success" as const, time: "~30–90s" };
  if (format === "monologue" && duration <= 10) {
    return { label: "Realtime 0.5B", variant: "accent" as const, time: "~30–90s" };
  }
  return { label: "Longform 1.5B", variant: "warning" as const, time: "~5–15min" };
}

function getAudioEstimate(lang: Language, format: Format, duration: number) {
  return getEngineBadge(lang, format, duration).time;
}

function getSpeakers(format: Format, names: string[]) {
  if (format === "monologue") return [names[0] || "Host"];
  if (format === "interview") return [names[0] || "Host", names[1] || "Guest"];
  return [names[0] || "Host", names[1] || "Guest 1", names[2] || "Guest 2"];
}

export default function Home() {
  // Form state
  const [topic, setTopic] = useState("");
  const [duration, setDuration] = useState(2);
  const [format, setFormat] = useState<Format>("monologue");
  const [language, setLanguage] = useState<Language>("en");

  const [speakerNames, setSpeakerNames] = useState(["Host", "Guest", "Expert"]);
  const [voiceSelections, setVoiceSelections] = useState<string[]>(["Carter", "Frank", "Alice"]);

  // Script & audio state
  const [script, setScript] = useState<ScriptLine[] | null>(null);
  const [scriptStats, setScriptStats] = useState("");
  const [isGeneratingScript, setIsGeneratingScript] = useState(false);
  const [editedLines, setEditedLines] = useState<Record<number, string>>({});
  const [hasEdits, setHasEdits] = useState(false);

  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioFilename, setAudioFilename] = useState("");
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  const [audioProgress, setAudioProgress] = useState(0);
  const [audioStatusText, setAudioStatusText] = useState("");
  const audioTimerRef = useRef<NodeJS.Timeout | null>(null);



  // History & config
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [config, setConfig] = useState<Record<string, ConfigStatus>>({});
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [architectureOpen, setArchitectureOpen] = useState(false);

  // Model status polling
  const [modelStatus, setModelStatus] = useState<{
    realtime: { cached: boolean; loaded: boolean };
    longform: { cached: boolean; loaded: boolean };
    asr: { cached: boolean; loaded: boolean };
    limits?: { max_longform_words: number; chunking_enabled: boolean; device: string };
    system?: { ram_gb?: number; torch_version?: string; mps_available?: boolean; device?: string };
  } | null>(null);

  // Rename state
  const [renamingFile, setRenamingFile] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [historyExpanded, setHistoryExpanded] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyFilterFormat, setHistoryFilterFormat] = useState<string>("all");
  const [historyFilterLanguage, setHistoryFilterLanguage] = useState<string>("all");

  // GSAP refs
  const heroRef = useRef<HTMLDivElement>(null);
  const heroCardsRef = useRef<HTMLDivElement>(null);
  const configRef = useRef<HTMLDivElement>(null);
  const scriptRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLDivElement>(null);
  const historyRef = useRef<HTMLDivElement>(null);
  const scriptLinesRef = useRef<HTMLDivElement>(null);
  const audioProgressRef = useRef<HTMLDivElement>(null);
  const scriptLoadingRef = useRef<HTMLDivElement>(null);
  const waveformRef = useRef<HTMLDivElement>(null);
  const scriptAbortRef = useRef<AbortController | null>(null);

  // Derived
  const speakers = useMemo(() => getSpeakers(format, speakerNames), [format, speakerNames]);
  const engineInfo = useMemo(() => getEngineBadge(language, format, duration), [language, format, duration]);
  const isIndic = language !== "en";
  const usesLongform = isIndic || format !== "monologue" || duration > 10;
  const availableVoices = isIndic ? SARVAM_VOICES : usesLongform ? LONGFORM_VOICES : REALTIME_VOICES;

  // Model readiness for current selection
  const requiredModel = isIndic ? "sarvam" : usesLongform ? "longform" : "realtime";
  const requiredModelStatus = isIndic
    ? null
    : requiredModel === "longform"
    ? modelStatus?.longform
    : modelStatus?.realtime;
  const modelReady = isIndic ? true : (requiredModelStatus?.loaded ?? false);
  const modelCached = isIndic ? true : (requiredModelStatus?.cached ?? false);

  // Memory / chunking estimates
  const maxLongformWords = modelStatus?.limits?.max_longform_words ?? 600;
  const scriptWordCount = script?.reduce((sum, line) => sum + line.content.split(/\s+/).filter(Boolean).length, 0) ?? 0;
  const willChunk = usesLongform && !isIndic && scriptWordCount > maxLongformWords;
  const estimatedChunks = willChunk ? Math.ceil(scriptWordCount / maxLongformWords) : 1;

  // Load config & history on mount
  useEffect(() => {
    fetchConfig();
    loadHistory();
    fetchModelStatus();
    const interval = setInterval(fetchModelStatus, 10000); // poll every 10s
    return () => clearInterval(interval);
  }, []);

  // Revoke blob URLs when audioUrl changes or on unmount
  useEffect(() => {
    return () => {
      if (audioUrl && audioUrl.startsWith("blob:")) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  // Reset voices when format/lang changes
  useEffect(() => {
    setVoiceSelections(speakers.map((_, i) => availableVoices[i % availableVoices.length]));
  }, [format, language, speakers.length]);

  async function fetchConfig() {
    try {
      const res = await fetch("/api/config");
      if (res.ok) setConfig(await res.json());
    } catch {}
  }

  async function fetchModelStatus() {
    try {
      const res = await fetch("/api/models/status");
      if (res.ok) setModelStatus(await res.json());
    } catch {}
  }

  const historyLoadingRef = useRef(false);
  
  async function loadHistory() {
    if (historyLoadingRef.current) return;
    historyLoadingRef.current = true;
    setHistoryError(null);
    try {
      const res = await fetch("/api/podcast/history?limit=20");
      if (res.ok) {
        const data = await res.json();
        const files = data.files || [];
        setHistory(files);
        try {
          localStorage.setItem("podcast_history_cache", JSON.stringify(files));
        } catch {}
        return;
      }
      throw new Error(`Server returned ${res.status}`);
    } catch {
      // Retry once after 1s
      try {
        await new Promise((r) => setTimeout(r, 1000));
        const res = await fetch("/api/podcast/history?limit=20");
        if (res.ok) {
          const data = await res.json();
          const files = data.files || [];
          setHistory(files);
          try {
            localStorage.setItem("podcast_history_cache", JSON.stringify(files));
          } catch {}
          return;
        }
        throw new Error(`Server returned ${res.status}`);
      } catch {
        try {
          const cached = localStorage.getItem("podcast_history_cache");
          if (cached) {
            const files = JSON.parse(cached);
            setHistory(files);
            setHistoryError("Backend unavailable · showing cached episodes");
            return;
          }
        } catch {}
        setHistory([]);
        setHistoryError("Backend unavailable");
      }
    } finally {
      historyLoadingRef.current = false;
    }
  }

  async function renameFile(oldFilename: string, newFilename: string) {
    try {
      const res = await fetch("/api/podcast/rename", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_filename: oldFilename, new_filename: newFilename }),
      });
      if (!res.ok) {
        const text = await res.text();
        let errMsg = text || `HTTP ${res.status}`;
        try {
          const errJson = JSON.parse(text);
          errMsg = errJson.detail || errJson.message || text || `HTTP ${res.status}`;
        } catch {}
        throw new Error(errMsg);
      }
      setRenamingFile(null);
      setRenameValue("");
      loadHistory();
    } catch (e: any) {
      alert("Rename failed: " + (e?.message || "Unknown error"));
    }
  }

  async function deleteFile(filename: string) {
    if (!confirm(`Delete "${filename}" permanently?`)) return;
    try {
      const res = await fetch(`/api/podcast/delete?filename=${encodeURIComponent(filename)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const text = await res.text();
        let errMsg = text || `HTTP ${res.status}`;
        try {
          const errJson = JSON.parse(text);
          errMsg = errJson.detail || errJson.message || text || `HTTP ${res.status}`;
        } catch {}
        throw new Error(errMsg);
      }
      if (audioFilename === filename) {
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        setAudioUrl(null);
        setAudioFilename("");
      }
      loadHistory();
    } catch (e: any) {
      alert("Delete failed: " + (e?.message || "Unknown error"));
    }
  }

  function stopScriptGeneration() {
    if (scriptAbortRef.current) {
      scriptAbortRef.current.abort();
      scriptAbortRef.current = null;
    }
    setIsGeneratingScript(false);
  }

  async function generateScript() {
    if (!topic.trim()) return;
    setIsGeneratingScript(true);
    setScript(null);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setHasEdits(false);
    setEditedLines({});
    scriptAbortRef.current = new AbortController();
    try {
      const res = await fetch("/api/podcast/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: scriptAbortRef.current.signal,
        body: JSON.stringify({
          topic: topic.trim(),
          duration_minutes: duration,
          format,
          speakers,
          language,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        let errMsg = text || `HTTP ${res.status}`;
        try {
          const errJson = JSON.parse(text);
          errMsg = errJson.detail || errJson.message || text || `HTTP ${res.status}`;
        } catch {}
        if (errMsg.includes("rate") || errMsg.includes("429")) {
          throw new Error("Rate limited. Add a Dialogram or GitHub Models key in Settings for unlimited free generation.");
        }
        throw new Error(errMsg);
      }
      const data = await res.json();
      setScript(data.script);
      setScriptStats(`${data.word_count} words · ${data.generation_time_seconds}s`);
    } catch (e: any) {
      if (e.name === "AbortError") {
        setScriptStats("Generation cancelled");
      } else {
        alert("Script generation failed: " + (e?.message || "Unknown error"));
      }
    } finally {
      setIsGeneratingScript(false);
      scriptAbortRef.current = null;
    }
  }

  function saveEdits() {
    if (!script) return;
    const updated = script.map((line, idx) => ({
      ...line,
      content: editedLines[idx] !== undefined ? editedLines[idx] : line.content,
    }));
    setScript(updated);
    setHasEdits(false);
    setEditedLines({});
    const wordCount = updated.reduce((sum, line) => sum + line.content.split(/\s+/).length, 0);
    setScriptStats(`${wordCount} words · edited`);
  }

  async function generateAudio() {
    if (!script || isGeneratingAudio) return;
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setIsGeneratingAudio(true);
    setAudioUrl(null);
    setAudioProgress(2);
    setAudioStatusText("Initializing TTS...");

    // Progress timer
    const wordCount = script.reduce((sum, line) => sum + line.content.split(/\s+/).length, 0);
    const audioMinutes = wordCount / 150;
    // Sarvam cloud is fast (~30-90s), longform local is slow (~5-15min), realtime is fast (~30-90s)
    const isSarvam = isIndic;
    const modelLoad = isSarvam ? 45 : usesLongform ? 150 : 45;
    const rtf = isSarvam ? 1.2 : usesLongform ? 4.0 : 1.2;
    const totalSec = modelLoad + audioMinutes * 60 * rtf;
    let elapsed = 0;

    if (audioTimerRef.current) clearInterval(audioTimerRef.current);
    audioTimerRef.current = setInterval(() => {
      elapsed += 1;
      if (elapsed <= totalSec) {
        const pct = Math.min(95, (elapsed / totalSec) * 100);
        const rem = Math.max(0, Math.round(totalSec - elapsed));
        const min = Math.floor(rem / 60);
        const sec = rem % 60;
        setAudioProgress(pct);
        setAudioStatusText(`Generating audio... ${min > 0 ? `${min}m ${sec}s` : `${sec}s`} remaining (estimated)`);
      } else {
        setAudioProgress(95);
        setAudioStatusText(isSarvam ? "Generating audio... still working (Sarvam cloud can take 1–3 min)" : "Generating audio... still working (Apple Silicon longform can take 5–15 min)");
      }
    }, 1000);

    // Safety timeout: abort and force-clear state if something hangs beyond 35 min
    const SAFETY_TIMEOUT_MS = 35 * 60 * 1000;
    const safetyTimer = setTimeout(() => {
      abortCtrl.abort();
      if (audioTimerRef.current) clearInterval(audioTimerRef.current);
      setIsGeneratingAudio(false);
      setAudioStatusText("Timed out — generation took too long. Check logs or try a shorter script.");
      alert("Audio generation timed out after 35 minutes. The backend may still be processing — check the outputs folder or logs/audio_generation.log");
    }, SAFETY_TIMEOUT_MS);

    // AbortController for fetch (allows canceling hung requests)
    const abortCtrl = new AbortController();

    try {
      let blob: Blob;
      if (isIndic) {
        const fullText = script.map((l) => l.content).join("\n\n");
        const res = await fetch("/api/tts/sarvam", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: abortCtrl.signal,
          body: JSON.stringify({
            text: fullText,
            target_language_code: language,
            speaker: voiceSelections[0] || "shubh",
            pace: 1.0,
            model: "bulbul:v3",
            output_audio_codec: "wav",
            save_to_disk: true,
            topic: topic.trim() || undefined,
            format,
            language,
          }),
        });
        if (!res.ok) {
          const text = await res.text();
          let errMsg = text || `HTTP ${res.status}`;
          try {
            const errJson = JSON.parse(text);
            errMsg = errJson.detail || errJson.message || text || `HTTP ${res.status}`;
          } catch {}
          throw new Error(errMsg);
        }
        blob = await res.blob();
      } else if (usesLongform) {
        const voiceMap: Record<string, string> = {};
        speakers.forEach((s, i) => (voiceMap[s] = voiceSelections[i] || s));
        const scriptPayload = script.map((line) => ({
          role: voiceMap[line.speaker] || line.speaker,
          content: line.content,
        }));
        const res = await fetch("/api/tts/longform", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: abortCtrl.signal,
          body: JSON.stringify({
            script: scriptPayload,
            voice_names: voiceSelections.slice(0, speakers.length),
            save_to_disk: true,
            topic: topic.trim() || undefined,
            format,
            language,
          }),
        });
        if (!res.ok) {
          const text = await res.text();
          let errMsg = text || `HTTP ${res.status}`;
          try {
            const errJson = JSON.parse(text);
            errMsg = errJson.detail || errJson.message || text || `HTTP ${res.status}`;
          } catch {}
          throw new Error(errMsg);
        }
        blob = await res.blob();
      } else {
        const fullText = script.map((l) => l.content).join("\n\n");
        const res = await fetch("/api/tts/realtime", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: abortCtrl.signal,
          body: JSON.stringify({
            text: fullText,
            speaker_name: voiceSelections[0] || "Carter",
            save_to_disk: true,
            topic: topic.trim() || undefined,
            format,
            language,
          }),
        });
        if (!res.ok) {
          const text = await res.text();
          let errMsg = text || `HTTP ${res.status}`;
          try {
            const errJson = JSON.parse(text);
            errMsg = errJson.detail || errJson.message || text || `HTTP ${res.status}`;
          } catch {}
          throw new Error(errMsg);
        }
        blob = await res.blob();
      }

      if (audioUrl) URL.revokeObjectURL(audioUrl);
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
      setAudioFilename(`podcast_${topic.replace(/[^a-z0-9]/gi, "_").toLowerCase()}_${Date.now()}.wav`);
      setAudioProgress(100);
      setAudioStatusText("Audio generation complete!");
      loadHistory();
    } catch (e: any) {
      if (e.name === "AbortError") {
        setAudioStatusText("Cancelled");
      } else {
        alert("Audio generation failed: " + (e?.message || "Unknown error"));
        setAudioStatusText("Error");
      }
    } finally {
      clearTimeout(safetyTimer);
      if (audioTimerRef.current) clearInterval(audioTimerRef.current);
      setIsGeneratingAudio(false);
    }
  }

  // GSAP Animations
  useGSAP(() => {
    const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
    tl.from(".hero-badge", { y: 60, autoAlpha: 0, duration: 0.8 })
      .from(".hero-word", { y: 80, autoAlpha: 0, duration: 1, stagger: 0.1 }, "-=0.4")
      .from(".hero-subtitle", { y: 50, autoAlpha: 0, duration: 1 }, "-=0.6");
  }, { scope: heroRef });

  useGSAP(() => {
    gsap.from(".hero-card", {
      y: 60,
      autoAlpha: 0,
      duration: 0.9,
      stagger: 0.15,
      ease: "power3.out",
      delay: 0.6,
    });
    gsap.to(".hero-card", {
      y: "-=8",
      duration: 2,
      stagger: { each: 0.3, repeat: -1, yoyo: true },
      ease: "sine.inOut",
      delay: 1.8,
    });
  }, { scope: heroCardsRef });

  useGSAP(() => {
    gsap.from(configRef.current, {
      y: 80,
      autoAlpha: 0,
      duration: 1,
      ease: "power3.out",
      scrollTrigger: { trigger: configRef.current, start: "top 90%", toggleActions: "play none none reverse" },
    });
  }, []);

  useGSAP(() => {
    gsap.from(scriptRef.current, {
      y: 80,
      autoAlpha: 0,
      duration: 1,
      ease: "power3.out",
      scrollTrigger: { trigger: scriptRef.current, start: "top 90%", toggleActions: "play none none reverse" },
    });
  }, []);

  useGSAP(() => {
    gsap.from(audioRef.current, {
      y: 80,
      autoAlpha: 0,
      duration: 1,
      ease: "power3.out",
      scrollTrigger: { trigger: audioRef.current, start: "top 90%", toggleActions: "play none none reverse" },
    });
  }, []);

  useGSAP(() => {
    gsap.from(historyRef.current, {
      y: 80,
      autoAlpha: 0,
      duration: 1,
      ease: "power3.out",
      scrollTrigger: { trigger: historyRef.current, start: "top 90%", toggleActions: "play none none reverse" },
    });
  }, []);

  useGSAP(() => {
    if (!isGeneratingScript) return;
    gsap.to(".script-dot", {
      y: -10,
      scale: 1.3,
      duration: 0.5,
      stagger: { each: 0.12, repeat: -1, yoyo: true },
      ease: "power1.inOut",
    });
    gsap.to(".script-glow", {
      opacity: 0.6,
      scale: 1.6,
      duration: 0.8,
      stagger: { each: 0.12, repeat: -1, yoyo: true },
      ease: "sine.inOut",
    });
  }, { scope: scriptLoadingRef, dependencies: [isGeneratingScript], revertOnUpdate: true });

  useGSAP(() => {
    if (!script) return;
    gsap.from(".script-line", {
      x: -30,
      autoAlpha: 0,
      duration: 0.6,
      stagger: 0.08,
      ease: "power2.out",
    });
  }, { scope: scriptLinesRef, dependencies: [script], revertOnUpdate: true });

  useGSAP(() => {
    if (!isGeneratingAudio) return;
    gsap.to(".audio-progress-bar", {
      width: `${audioProgress}%`,
      duration: 0.5,
      ease: "power1.out",
    });
  }, { scope: audioProgressRef, dependencies: [audioProgress], revertOnUpdate: true });

  useGSAP(() => {
    if (!historyExpanded || history.length === 0) return;
    gsap.from(".history-item", {
      x: -20,
      autoAlpha: 0,
      duration: 0.5,
      stagger: 0.05,
      ease: "power2.out",
      delay: 0.1,
    });
  }, { scope: historyRef, dependencies: [historyExpanded, history.length], revertOnUpdate: true });

  useGSAP(() => {
    if (!audioUrl) return;
    gsap.from(".waveform-bar", {
      scaleY: 0,
      duration: 0.4,
      stagger: 0.03,
      ease: "back.out(1.7)",
    });
    gsap.to(".waveform-bar", {
      scaleY: "random(0.3, 1)",
      duration: 0.6,
      stagger: { each: 0.05, repeat: -1, yoyo: true, from: "random" },
      ease: "sine.inOut",
      delay: 0.4,
    });
  }, { scope: waveformRef, dependencies: [audioUrl], revertOnUpdate: true });

  // ================= Render =================
  return (
    <main className="min-h-screen animated-gradient">
      {/* Top Navigation */}
      <nav className="sticky top-0 z-40 glass border-b border-white/5">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-indigo-500 flex items-center justify-center shadow-lg shadow-accent/20">
              <Mic className="w-5 h-5 text-slate-900" />
            </div>
            <div>
              <h1 className="text-lg font-bold gradient-text">Podcast Brain Pro</h1>
              <p className="text-xs text-muted">AI scriptwriter & local TTS synthesizer</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setArchitectureOpen(true)}>
              <Layers className="w-4 h-4" />
              <span className="hidden sm:inline">Architecture</span>
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setSettingsOpen(true)}>
              <Settings className="w-4 h-4" />
              <span className="hidden sm:inline">Settings</span>
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setHelpOpen(true)}>
              <HelpCircle className="w-4 h-4" />
              <span className="hidden sm:inline">Help</span>
            </Button>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Hero */}
        <section ref={heroRef} className="text-center py-8 sm:py-12">
          <div>
            <Badge variant="accent" className="mb-4 hero-badge">
              <Sparkles className="w-3 h-3" />
              Open Source
            </Badge>
            <h2 className="text-3xl sm:text-5xl font-extrabold tracking-tight mb-4">
              <span className="hero-word inline-block">Generate</span>{" "}
              <span className="hero-word inline-block">podcasts</span>{" "}
              <span className="hero-word inline-block">with</span>{" "}
              <span className="hero-word inline-block gradient-text">AI</span>
            </h2>
            <p className="hero-subtitle text-muted text-base sm:text-lg max-w-2xl mx-auto leading-relaxed">
              Research, script, and voice your episodes. Script generation runs in the cloud instantly.
              Full audio synthesis runs locally on your Apple Silicon Mac or NVIDIA GPU.
            </p>
          </div>

          <div
            ref={heroCardsRef}
            className="mt-8 flex flex-wrap items-center justify-center gap-4"
          >
            <motion.div whileHover={{ scale: 1.03, y: -2 }} whileTap={{ scale: 0.98 }} className="hero-card glass rounded-xl px-4 py-3 flex items-center gap-3 cursor-default">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                <Zap className="w-4 h-4 text-accent" />
              </div>
              <div className="text-left">
                <div className="text-sm font-semibold">Instant Scripts</div>
                <div className="text-xs text-muted">Cloud AI · ~10–30s</div>
              </div>
            </motion.div>
            <motion.div whileHover={{ scale: 1.03, y: -2 }} whileTap={{ scale: 0.98 }} className="hero-card glass rounded-xl px-4 py-3 flex items-center gap-3 cursor-default">
              <div className="w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center">
                <Volume2 className="w-4 h-4 text-success" />
              </div>
              <div className="text-left">
                <div className="text-sm font-semibold">Local Audio</div>
                <div className="text-xs text-muted">VibeVoice TTS · GPU powered</div>
              </div>
            </motion.div>
            <motion.div whileHover={{ scale: 1.03, y: -2 }} whileTap={{ scale: 0.98 }} className="hero-card glass rounded-xl px-4 py-3 flex items-center gap-3 cursor-default">
              <div className="w-8 h-8 rounded-lg bg-warning/10 flex items-center justify-center">
                <Globe className="w-4 h-4 text-warning" />
              </div>
              <div className="text-left">
                <div className="text-sm font-semibold">Indian Languages</div>
                <div className="text-xs text-muted">Sarvam AI · 10 languages</div>
              </div>
            </motion.div>
          </div>
        </section>

        {/* Configuration */}
        <div ref={configRef}>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wand2 className="w-4 h-4 text-accent" />
                Episode Configuration
              </CardTitle>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="subtle">
                <Clock className="w-3 h-3" />
                Script {SCRIPT_ESTIMATES[duration]}
              </Badge>
              <Badge variant={engineInfo.variant}>
                <Volume2 className="w-3 h-3" />
                {engineInfo.label} · {engineInfo.time}
              </Badge>
              {!isIndic && (
                (() => {
                  const status = modelStatus?.[requiredModel as "realtime" | "longform"];
                  const isLoaded = status?.loaded;
                  const isCached = status?.cached;
                  if (isLoaded) {
                    return (
                      <Badge variant="success">
                        <CheckCircle className="w-3 h-3" />
                        {requiredModel === "longform" ? "1.5B Ready" : "0.5B Ready"}
                      </Badge>
                    );
                  }
                  if (isCached) {
                    return (
                      <Badge variant="warning">
                        <Cpu className="w-3 h-3" />
                        {requiredModel === "longform" ? "1.5B Cached · loads in ~5s" : "0.5B Cached · loads in ~5s"}
                      </Badge>
                    );
                  }
                  return (
                    <Badge variant="error">
                      <Download className="w-3 h-3" />
                      {requiredModel === "longform" ? "1.5B Downloading… (~5–10 min)" : "0.5B Downloading… (~2–5 min)"}
                    </Badge>
                  );
                })()
              )}
            </div>
          </CardHeader>

          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-muted mb-1.5">Topic</label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g., The future of electric aviation"
                className="w-full rounded-xl bg-surface-2 border border-border px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-muted mb-1.5">Duration</label>
                <div className="flex flex-wrap gap-2">
                  {DURATIONS.map((d) => (
                    <motion.button
                      key={d}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setDuration(d)}
                      className={cn(
                        "px-3 py-2 rounded-lg text-sm font-semibold border transition-all",
                        duration === d
                          ? "bg-accent text-slate-900 border-accent shadow-lg shadow-accent/20"
                          : "bg-surface-2 text-muted border-border hover:bg-surface-3"
                      )}
                    >
                      {d} min
                    </motion.button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-muted mb-1.5">Format</label>
                <select
                  value={format}
                  onChange={(e) => setFormat(e.target.value as Format)}
                  className="w-full rounded-xl bg-surface-2 border border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
                >
                  {FORMATS.map((f) => (
                    <option key={f.value} value={f.value}>
                      {f.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-muted mb-1.5">Language</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as Language)}
                  className="w-full rounded-xl bg-surface-2 border border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
                >
                  {LANGUAGES.map((l) => (
                    <option key={l.value} value={l.value}>
                      {l.label}
                    </option>
                  ))}
                </select>
                {!config.SARVAM_API_KEY?.configured && isIndic && (
                  <p className="text-xs text-warning mt-1.5">
                    Add Sarvam API key in Settings to generate Indian-language audio.
                  </p>
                )}
              </div>
            </div>

            {/* Engine info for English multi-speaker */}
            {!isIndic && format !== "monologue" && (
              <div className="rounded-xl border border-border bg-surface-2 p-4">
                <div className="text-sm font-semibold flex items-center gap-2 mb-2">
                  <Cpu className="w-4 h-4 text-accent" />
                  Audio Engine
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-warning mt-2" />
                  <p className="text-sm text-muted">
                    Interview and panel formats use <strong>Longform 1.5B</strong> for native multi-speaker support.
                    This produces the most natural dialog but takes <strong>~5–15 minutes</strong> on Apple Silicon.
                    A faster stitching mode is on the roadmap.
                  </p>
                </div>
              </div>
            )}

            {/* Speakers */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {speakers.map((_, idx) => (
                <div key={idx}>
                  <label className="block text-sm font-medium text-muted mb-1.5">
                    {format === "monologue"
                      ? "Host Name"
                      : format === "interview"
                      ? idx === 0
                        ? "Interviewer"
                        : "Guest"
                      : idx === 0
                      ? "Host"
                      : idx === 1
                      ? "Guest 1"
                      : "Guest 2"}
                  </label>
                  <input
                    type="text"
                    value={speakerNames[idx]}
                    onChange={(e) => {
                      const next = [...speakerNames];
                      next[idx] = e.target.value;
                      setSpeakerNames(next);
                    }}
                    className="w-full rounded-xl bg-surface-2 border border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
                  />
                </div>
              ))}
            </div>

            {/* Voice Cast — Dropdowns */}
            <div>
              <label className="block text-sm font-medium text-muted mb-2">Voice Cast</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {speakers.map((spk, idx) => (
                  <div key={idx}>
                    <label className="block text-xs text-muted mb-1.5">{spk}</label>
                    <select
                      value={voiceSelections[idx] || availableVoices[0]}
                      onChange={(e) => {
                        const next = [...voiceSelections];
                        next[idx] = e.target.value;
                        setVoiceSelections(next);
                      }}
                      className="w-full rounded-xl bg-surface-2 border border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
                    >
                      {availableVoices.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted mt-2">
                {isIndic
                  ? "Select a Sarvam voice for each speaker."
                  : usesLongform
                  ? "Select a longform voice for each speaker. Longform audio on Apple Silicon can take 5–15 min."
                  : "Select a realtime voice for the monologue."}
              </p>
            </div>

            {/* Model requirement alert */}
            {usesLongform && !isIndic && (
              <div className={`rounded-xl border p-4 space-y-2 ${modelStatus?.longform?.loaded ? "bg-success/5 border-success/20" : modelStatus?.longform?.cached ? "bg-warning/5 border-warning/20" : "bg-error/5 border-error/20"}`}>
                <div className="flex items-center gap-2 font-semibold text-sm">
                  {modelStatus?.longform?.loaded ? (
                    <><CheckCircle className="w-4 h-4 text-success" /> Longform 1.5B model is ready</>
                  ) : modelStatus?.longform?.cached ? (
                    <><Cpu className="w-4 h-4 text-warning" /> Longform 1.5B model is cached</>
                  ) : (
                    <><AlertTriangle className="w-4 h-4 text-error" /> Longform 1.5B model required</>
                  )}
                </div>
                <p className="text-xs text-muted leading-relaxed">
                  Your current selection ({duration} min · {format === "interview" ? "Interview" : format === "panel" ? "Panel" : format}) requires the <strong>Longform 1.5B model (~5.4 GB)</strong>.
                  {modelStatus?.longform?.loaded
                    ? " It is loaded in memory and ready to generate."
                    : modelStatus?.longform?.cached
                    ? " It is downloaded on disk and will load into memory in ~5 seconds when you click Generate Audio."
                    : " It is downloading in the background. Wait for the green Ready badge before clicking Generate Audio — this takes ~5–10 minutes on first install."}
                </p>
                {willChunk && (
                  <div className="rounded-lg bg-warning/10 border border-warning/30 p-2.5 space-y-1">
                    <div className="flex items-center gap-1.5 text-xs font-medium text-warning">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Memory-safe chunking will be used
                    </div>
                    <p className="text-[11px] text-muted leading-relaxed">
                      This script is {scriptWordCount} words (limit: {maxLongformWords}).
                      It will be split into {estimatedChunks} chunks, generated separately, and stitched together.
                      {(() => {
                        const device = modelStatus?.limits?.device ?? modelStatus?.system?.device;
                        return device
                          ? `This prevents memory exhaustion on your ${device.toUpperCase()} device. `
                          : "";
                      })()}
                      For single-pass generation, reduce duration to ≤3 min or use a machine with 32+ GB RAM.
                    </p>
                  </div>
                )}
                {!modelStatus?.longform?.cached && (
                  <p className="text-xs text-muted">
                    <strong>Terminal check:</strong>{" "}
                    <code className="bg-surface-2 px-1.5 py-0.5 rounded font-mono text-[10px]">curl http://localhost:8000/models/status</code>
                  </p>
                )}
              </div>
            )}
          </div>
          </Card>
        </div>

        {/* System / Model Status */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-accent" />
                System Status
              </CardTitle>
            </CardHeader>
            <div className="space-y-3">
              {[
                { key: "realtime", name: "Realtime 0.5B", size: "~2 GB", purpose: "English monologue ≤10 min" },
                { key: "longform", name: "Longform 1.5B", size: "~5.4 GB", purpose: "Interview / Panel / &gt;10 min" },
                { key: "asr", name: "ASR 7B", size: "~14 GB", purpose: "Speech-to-text (optional)" },
              ].map((m) => {
                const s = modelStatus?.[m.key as "realtime" | "longform" | "asr"];
                const isReady = s?.loaded;
                const isCached = s?.cached;
                return (
                  <div key={m.key} className="flex items-center justify-between rounded-lg bg-surface-2 border border-border px-3 py-2.5">
                    <div className="flex items-center gap-3">
                      <div className={`w-2.5 h-2.5 rounded-full ${isReady ? "bg-success" : isCached ? "bg-warning" : "bg-error"}`} />
                      <div>
                        <div className="text-sm font-medium">{m.name}</div>
                        <div className="text-xs text-muted">{m.purpose}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <Badge variant={isReady ? "success" : isCached ? "warning" : "error"} className="text-[10px]">
                        {isReady ? "Ready" : isCached ? "Cached" : "Not Downloaded"}
                      </Badge>
                      <div className="text-[10px] text-muted mt-0.5">{m.size}</div>
                    </div>
                  </div>
                );
              })}
              <div className="rounded-lg bg-surface-2 border border-border p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-medium">Hardware & Environment</div>
                  <div className="group relative">
                    <Info className="w-3.5 h-3.5 text-muted cursor-help" />
                    <div className="absolute bottom-full right-0 mb-2 w-56 rounded-lg bg-surface-3 border border-border p-2 text-[11px] text-muted opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 shadow-lg">
                      <span className="font-medium text-foreground">Cached</span> = downloaded to disk.<br/>
                      <span className="font-medium text-foreground">Ready</span> = loaded in memory.
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-muted">
                  <span>Your device:</span>
                  <span className="text-foreground font-medium">{(modelStatus?.limits?.device ?? modelStatus?.system?.device)?.toUpperCase() || "—"}</span>
                  <span>System RAM:</span>
                  <span className="text-foreground font-medium">{modelStatus?.system?.ram_gb ? `${modelStatus.system.ram_gb} GB` : "RAM detection unavailable"}</span>
                  <span>PyTorch:</span>
                  <span className="text-foreground font-medium">{modelStatus?.system?.torch_version || "—"}</span>
                  <span>Max script (single-pass):</span>
                  <span className="text-foreground font-medium">~{maxLongformWords} words (~{Math.round(maxLongformWords/150)} min)</span>
                  <span>Longer scripts:</span>
                  <span className="text-foreground font-medium">Auto-chunked into segments</span>
                  <span>Recommended for 5+ min:</span>
                  <span className="text-foreground font-medium">{modelStatus?.system?.ram_gb && modelStatus.system.ram_gb >= 32 ? "Current system is well equipped" : "32+ GB RAM or GPU"}</span>
                </div>
              </div>
              <p className="text-xs text-muted">
                Models download automatically on first use. Cache location: <code className="bg-surface-2 px-1 rounded">~/.cache/huggingface/hub/</code>
              </p>
            </div>
          </Card>
        </div>

        {/* Script */}
        <div ref={scriptRef}>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wand2 className="w-4 h-4 text-accent" />
                Script
              </CardTitle>
            {scriptStats && <Badge variant="subtle">{scriptStats}</Badge>}
          </CardHeader>

          <div className="flex flex-wrap gap-2 mb-4">
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button
                variant="primary"
                onClick={generateScript}
                disabled={isGeneratingScript || !topic.trim()}
              >
                <Sparkles className="w-4 h-4" />
                {isGeneratingScript ? "Generating..." : "Generate Script"}
              </Button>
            </motion.div>
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button
                variant="secondary"
                onClick={saveEdits}
                disabled={!hasEdits}
              >
                <Save className="w-4 h-4" />
                Save Edits
              </Button>
            </motion.div>
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Button
                variant="secondary"
                onClick={generateAudio}
                disabled={!script || isGeneratingAudio || (isIndic && !config.SARVAM_API_KEY?.configured) || (!isIndic && !modelCached)}
                title={!isIndic && !modelCached ? "Model is still downloading. Wait for the Cached badge." : undefined}
              >
                <Volume2 className="w-4 h-4" />
                {isGeneratingAudio ? "Generating Audio..." : !isIndic && !modelCached ? "Downloading Model..." : "Generate Audio"}
              </Button>
            </motion.div>
          </div>

          {isGeneratingScript && (
            <div ref={scriptLoadingRef} className="space-y-3 py-4">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className="script-glow absolute inset-0 rounded-full bg-accent blur-sm opacity-0" />
                  <div className="script-dot relative w-3 h-3 rounded-full bg-accent" />
                </div>
                <div className="relative">
                  <div className="script-glow absolute inset-0 rounded-full bg-accent blur-sm opacity-0" />
                  <div className="script-dot relative w-3 h-3 rounded-full bg-accent" />
                </div>
                <div className="relative">
                  <div className="script-glow absolute inset-0 rounded-full bg-accent blur-sm opacity-0" />
                  <div className="script-dot relative w-3 h-3 rounded-full bg-accent" />
                </div>
                <div className="flex-1" />
                <Button variant="ghost" size="sm" onClick={stopScriptGeneration}>
                  <span className="text-error">Stop</span>
                </Button>
              </div>
              <p className="text-sm text-muted">Researching topic and writing script...</p>
            </div>
          )}

          <AnimatePresence>
            {script && (
              <motion.div
                ref={scriptLinesRef}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-4 rounded-xl border border-border bg-surface-2 p-4 max-h-[400px] overflow-y-auto"
              >
                <div className="space-y-4">
                  {script.map((line, idx) => (
                    <div key={idx} className="script-line border-b border-border last:border-0 pb-4 last:pb-0">
                      <div className="text-xs font-bold uppercase tracking-wider text-accent mb-1">
                        {line.speaker}
                        {editedLines[idx] !== undefined && editedLines[idx] !== line.content && (
                          <span className="ml-2 text-[10px] text-muted font-normal">edited</span>
                        )}
                      </div>
                      <textarea
                        value={editedLines[idx] ?? line.content}
                        onChange={(e) => {
                          setEditedLines((prev) => ({ ...prev, [idx]: e.target.value }));
                          setHasEdits(true);
                        }}
                        className="w-full bg-transparent text-sm leading-relaxed focus:outline-none resize-y min-h-[3rem]"
                        rows={2}
                      />
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          </Card>
        </div>

        {/* Audio Output */}
        <div ref={audioRef}>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Volume2 className="w-4 h-4 text-accent" />
                Audio Output
              </CardTitle>
            <Badge variant={engineInfo.variant}>{engineInfo.label}</Badge>
          </CardHeader>

          {isGeneratingAudio && (
            <div ref={audioProgressRef} className="space-y-3 mb-4">
              <div className="h-2 w-full rounded-full bg-surface-2 overflow-hidden">
                <div
                  className="audio-progress-bar h-full bg-gradient-to-r from-accent to-indigo-500 rounded-full"
                  style={{ width: "0%" }}
                  role="progressbar"
                  aria-valuenow={audioProgress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={audioStatusText || "Generating audio"}
                />
              </div>
              <p className="text-sm text-muted">{audioStatusText}</p>
            </div>
          )}

          {audioUrl && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-4"
            >
              <div ref={waveformRef} className="flex items-center justify-center gap-1 h-16 rounded-xl bg-surface-2 border border-border px-4">
                {Array.from({ length: 24 }).map((_, i) => (
                  <div
                    key={i}
                    className="waveform-bar w-1.5 rounded-full bg-gradient-to-t from-accent to-indigo-500 origin-bottom"
                    style={{ height: "40%" }}
                  />
                ))}
              </div>
              <audio key={audioUrl} controls className="w-full rounded-lg">
                <source src={audioUrl} type="audio/wav" />
              </audio>
              <div className="flex gap-2">
                <Button variant="secondary" asChild>
                  <a href={audioUrl} download={audioFilename}>
                    <Download className="w-4 h-4" />
                    Download WAV
                  </a>
                </Button>
              </div>
            </motion.div>
          )}

          {!audioUrl && !isGeneratingAudio && (
            <div className="flex items-start gap-3 rounded-xl border border-border bg-surface-2 p-4">
              <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
              <div className="text-sm text-muted">
                <p className="font-medium text-foreground mb-1">Audio runs locally</p>
                <p>
                  Full audio synthesis uses local VibeVoice TTS models and requires an Apple Silicon
                  Mac (MPS) or NVIDIA GPU (CUDA). Script generation works from anywhere.
                </p>
              </div>
            </div>
          )}
          </Card>
        </div>

        {/* History */}
        <div ref={historyRef}>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="w-4 h-4 text-accent" />
                Recent Episodes
                <span className="ml-2 text-xs text-muted font-normal">
                  {history.length > 0 && `(${history.length})`}
                </span>
              </CardTitle>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" onClick={loadHistory}>
                  <RotateCcw className="w-4 h-4" />
                  Refresh
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setHistoryExpanded((v) => !v)}>
                  <motion.div
                    animate={{ rotate: historyExpanded ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <ChevronDown className="w-4 h-4" />
                  </motion.div>
                </Button>
              </div>
            </CardHeader>

            <AnimatePresence initial={false}>
              {historyExpanded && (
                <motion.div
                  key="history-content"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: "easeInOut" }}
                  className="overflow-hidden"
                >
                  {/* Filters */}
                  {history.length > 0 && (
                    <div className="flex items-center gap-2 mb-3 flex-wrap">
                      <Filter className="w-3.5 h-3.5 text-muted" />
                      <select
                        value={historyFilterFormat}
                        onChange={(e) => setHistoryFilterFormat(e.target.value)}
                        className="text-xs bg-surface-2 border border-border rounded-lg px-2 py-1 text-foreground focus:outline-none focus:ring-1 focus:ring-accent/30"
                      >
                        <option value="all">All Formats</option>
                        <option value="monologue">Solo</option>
                        <option value="interview">2-Person</option>
                        <option value="panel">3-Person Panel</option>
                      </select>
                      <select
                        value={historyFilterLanguage}
                        onChange={(e) => setHistoryFilterLanguage(e.target.value)}
                        className="text-xs bg-surface-2 border border-border rounded-lg px-2 py-1 text-foreground focus:outline-none focus:ring-1 focus:ring-accent/30"
                      >
                        <option value="all">All Languages</option>
                        <option value="en">English</option>
                        <option value="hi-IN">Hindi</option>
                        <option value="ta-IN">Tamil</option>
                        <option value="te-IN">Telugu</option>
                        <option value="kn-IN">Kannada</option>
                        <option value="bn-IN">Bengali</option>
                        <option value="mr-IN">Marathi</option>
                        <option value="gu-IN">Gujarati</option>
                        <option value="ml-IN">Malayalam</option>
                        <option value="pa-IN">Punjabi</option>
                        <option value="od-IN">Odia</option>
                      </select>
                      {(historyFilterFormat !== "all" || historyFilterLanguage !== "all") && (
                        <button
                          onClick={() => { setHistoryFilterFormat("all"); setHistoryFilterLanguage("all"); }}
                          className="text-xs text-accent hover:underline"
                        >
                          Clear
                        </button>
                      )}
                    </div>
                  )}

                  <div className="space-y-3 pt-2">
                    {(() => {
                      const filtered = history.filter((item) => {
                        const matchFormat = historyFilterFormat === "all" || item.format === historyFilterFormat;
                        const matchLang = historyFilterLanguage === "all" || item.language === historyFilterLanguage;
                        return matchFormat && matchLang;
                      });
                      if (filtered.length === 0) {
                        return (
                          <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="text-sm text-muted"
                          >
                            {historyError || "No episodes match the selected filters."}
                          </motion.p>
                        );
                      }
                      return filtered.map((item) => (
                        <motion.div
                          key={item.filename}
                          layout
                          exit={{ opacity: 0, scale: 0.95 }}
                          whileHover={{ scale: 1.01, backgroundColor: "rgba(255,255,255,0.03)" }}
                          transition={{ duration: 0.2 }}
                          className="history-item flex items-center justify-between rounded-xl border border-border bg-surface-2 px-4 py-3"
                        >
                          <div className="min-w-0 flex-1">
                            {renamingFile === item.filename ? (
                              <div className="flex items-center gap-2">
                                <input
                                  type="text"
                                  value={renameValue}
                                  onChange={(e) => setRenameValue(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") {
                                      const newName = renameValue.trim();
                                      if (newName && newName !== item.filename) {
                                        const finalName = newName.endsWith(".wav") ? newName : `${newName}.wav`;
                                        renameFile(item.filename, finalName);
                                      } else {
                                        setRenamingFile(null);
                                      }
                                    }
                                    if (e.key === "Escape") {
                                      setRenamingFile(null);
                                      setRenameValue("");
                                    }
                                  }}
                                  autoFocus
                                  className="flex-1 min-w-0 rounded-lg bg-surface-3 border border-border px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
                                />
                                <Button
                                  variant="primary"
                                  size="sm"
                                  onClick={() => {
                                    const newName = renameValue.trim();
                                    if (newName && newName !== item.filename) {
                                      const finalName = newName.endsWith(".wav") ? newName : `${newName}.wav`;
                                      renameFile(item.filename, finalName);
                                    } else {
                                      setRenamingFile(null);
                                    }
                                  }}
                                >
                                  Save
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    setRenamingFile(null);
                                    setRenameValue("");
                                  }}
                                >
                                  Cancel
                                </Button>
                              </div>
                            ) : (
                              <>
                                <div className="truncate text-sm font-medium">
                                  {item.topic || item.title || item.filename}
                                </div>
                                <div className="flex items-center gap-2 mt-1 flex-wrap">
                                  <span className="text-xs text-muted">
                                    {formatBytes(item.size_bytes)} · {formatDate(item.created_at)}
                                    {item.duration_seconds && (
                                      <span className="ml-2">· {formatDuration(item.duration_seconds)}</span>
                                    )}
                                    {(item.topic || item.title) && item.filename !== (item.topic || item.title) && (
                                      <span className="ml-2 opacity-60">· {item.filename}</span>
                                    )}
                                  </span>
                                  {item.duration_seconds && (
                                    <Badge variant="subtle" className="text-[10px] px-1.5 py-0 h-4">
                                      <Clock className="w-3 h-3" />
                                      {formatDuration(item.duration_seconds)}
                                    </Badge>
                                  )}
                                  {item.format && (
                                    <Badge variant="accent" className="text-[10px] px-1.5 py-0 h-4">
                                      {item.format === "monologue" ? "Solo" : item.format === "interview" ? "Interview" : item.format === "panel" ? "Panel" : item.format}
                                    </Badge>
                                  )}
                                  {item.language && (
                                    <Badge variant="subtle" className="text-[10px] px-1.5 py-0 h-4">
                                      {item.language === "en" ? "English" : item.language}
                                    </Badge>
                                  )}
                                </div>
                              </>
                            )}
                          </div>
                          <div className="flex items-center gap-3 ml-4">
                            {renamingFile !== item.filename && (
                              <>
                                <button
                                  onClick={() => {
                                    setRenamingFile(item.filename);
                                    setRenameValue(item.filename);
                                  }}
                                  className="text-sm text-muted hover:text-accent transition-colors"
                                  title="Rename"
                                >
                                  <Pencil className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => {
                                    if (audioUrl && audioUrl.startsWith("blob:")) URL.revokeObjectURL(audioUrl);
                                    setAudioUrl(`/outputs/${encodeURIComponent(item.filename)}`);
                                    setAudioFilename(item.filename);
                                    audioRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                                  }}
                                  className="text-sm text-accent hover:underline"
                                >
                                  Play
                                </button>
                                <a
                                  href={`/outputs/${encodeURIComponent(item.filename)}`}
                                  download
                                  className="text-sm text-accent hover:underline"
                                >
                                  Download
                                </a>
                                <button
                                  onClick={() => deleteFile(item.filename)}
                                  className="text-sm text-muted hover:text-error transition-colors"
                                  title="Delete"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </>
                            )}
                          </div>
                        </motion.div>
                      ));
                    })()}
                  </div>

                  <div className="mt-4 flex gap-2">
                    <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                      <Button variant="secondary" size="sm" asChild>
                        <a href="/feed/podcast.rss" target="_blank">
                          <Mic className="w-4 h-4" />
                          RSS Feed
                        </a>
                      </Button>
                    </motion.div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 mt-12">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 text-center text-sm text-muted">
          <p>
            Podcast Brain Pro is open source. Built with FastAPI, PyTorch, and VibeVoice.
          </p>
          <p className="mt-1">
            Script generation powered by Dialogram Qwen 3.6.
          </p>
        </div>
      </footer>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        config={config}
        onSaved={fetchConfig}
      />

      {/* Help Modal */}
      <HelpModal isOpen={helpOpen} onClose={() => setHelpOpen(false)} />

      {/* Architecture Modal */}
      <ArchitectureModal isOpen={architectureOpen} onClose={() => setArchitectureOpen(false)} />
    </main>
  );
}

// ================= Subcomponents =================

function SettingsModal({
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
  const keys = [
    { id: "DIALOGRAM_API_KEY", label: "Dialogram API Key", desc: "Primary script provider (Qwen 3.6 Plus)", link: "https://dialogram.me/" },
    { id: "GITHUB_PERSONAL_ACCESS_TOKEN", label: "GitHub Models Token", desc: "Free GPT-4o fallback", link: "https://github.com/settings/tokens" },
    { id: "GROQ_API_KEY", label: "Groq API Key", desc: "Fast Llama-3.3-70B fallback", link: "https://console.groq.com/keys" },
    { id: "SARVAM_API_KEY", label: "Sarvam API Key", desc: "Indian-language TTS", link: "https://dashboard.sarvam.ai/" },
    { id: "TAVILY_API_KEY", label: "Tavily API Key", desc: "Live web research", link: "https://app.tavily.com/home" },
    { id: "GEMINI_API_KEY", label: "Gemini API Key", desc: "Google Gemini fallback", link: "https://aistudio.google.com/api-keys" },
    { id: "MISTRAL_API_KEY", label: "Mistral API Key", desc: "Mistral AI fallback", link: "https://console.mistral.ai/home" },
    { id: "DEEPSEEK_API_KEY", label: "DeepSeek API Key", desc: "DeepSeek fallback", link: "https://platform.deepseek.com/api_keys" },
    { id: "TOGETHER_API_KEY", label: "Together AI Key", desc: "Together AI fallback", link: "https://api.together.ai/settings/api-keys" },
    { id: "OPENROUTER_API_KEY", label: "OpenRouter Key", desc: "Final fallback", link: "https://openrouter.ai/settings/keys" },
  ];

  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  // Seed form values from config when modal opens
  useEffect(() => {
    if (isOpen) {
      const seeded: Record<string, string> = {};
      keys.forEach((k) => {
        seeded[k.id] = config[k.id]?.masked || "";
      });
      setValues(seeded);
    }
  }, [isOpen, config]);

  async function save() {
    const payload: Record<string, string> = {};
    keys.forEach((k) => {
      const v = values[k.id] ?? "";
      // Send empty string to delete, otherwise send trimmed value
      payload[k.id] = v.trim();
    });
    setSaving(true);
    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const text = await res.text();
        let errMsg = text || `HTTP ${res.status}`;
        try {
          const errJson = JSON.parse(text);
          errMsg = errJson.detail || errJson.message || text || `HTTP ${res.status}`;
        } catch {}
        throw new Error(errMsg);
      }
      onSaved();
      onClose();
    } catch (e: any) {
      alert("Failed to save: " + e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="⚙️ API Keys & Settings">
      <p className="text-sm text-muted mb-5">
        Configure API keys to unlock cloud providers. Keys are saved locally and never sent to our servers.
      </p>
      <div className="space-y-5">
        {keys.map((k) => {
          const status = config[k.id];
          return (
            <div key={k.id} className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-6 pb-5 border-b border-border last:border-0">
              <div className="flex-1">
                <div className="font-semibold text-sm">{k.label}</div>
                <div className="text-xs text-muted mt-0.5">{k.desc}</div>
                <a href={k.link} target="_blank" className="text-xs text-accent hover:underline mt-1 inline-block">
                  Get key →
                </a>
              </div>
              <div className="sm:min-w-[280px] sm:max-w-[320px] w-full">
                {status && (
                  <div className="mb-2">
                    {status.configured ? (
                      <Badge variant="success">Configured {status.masked ? `· ${status.masked}` : ""}</Badge>
                    ) : (
                      <Badge variant="subtle">Not configured</Badge>
                    )}
                  </div>
                )}
                <input
                  type="password"
                  value={values[k.id] || ""}
                  onChange={(e) => setValues((prev) => ({ ...prev, [k.id]: e.target.value }))}
                  placeholder={status?.masked ? `Currently: ${status.masked}` : "Paste key here"}
                  className="w-full rounded-lg bg-surface-2 border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/30"
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="primary" onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save Changes"}
        </Button>
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </Modal>
  );
}

function HelpModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Help & Setup Guide" className="max-w-3xl">
      <div className="space-y-6 text-sm text-muted max-h-[70vh] overflow-y-auto pr-1">
        <section>
          <h4 className="text-accent font-semibold mb-2 text-base">What is Podcast Brain Pro?</h4>
          <p>
            An open-source AI podcast factory. It writes research-backed scripts in seconds using cloud LLMs,
            then synthesizes natural-sounding audio locally on your Apple Silicon Mac or NVIDIA GPU.
            Generate monologues, two-person interviews, or three-person panels in English
            and 10 Indian languages.
          </p>
        </section>

        <section>
          <h4 className="text-accent font-semibold mb-2 text-base">Local Setup (Your Laptop)</h4>
          <div className="space-y-3">
            <div className="rounded-lg bg-surface-2 border border-border p-3 space-y-2">
              <p className="font-medium text-foreground">1. Clone & install vibevoice package</p>
              <code className="block bg-surface-3 px-2 py-1.5 rounded text-xs font-mono text-foreground">
                git clone https://github.com/YOUR_USERNAME/podcast-brain-pro.git<br/>
                cd podcast-brain-pro/voice-service<br/>
                python3 -m venv .venv && source .venv/bin/activate<br/>
                pip install -r requirements.txt<br/>
                cd ../vibevoice-src && pip install -e . && cd ../voice-service
              </code>
            </div>
            <div className="rounded-lg bg-surface-2 border border-border p-3 space-y-2">
              <p className="font-medium text-foreground">2. Configure API keys</p>
              <code className="block bg-surface-3 px-2 py-1.5 rounded text-xs font-mono text-foreground">
                cp .env.example .env<br/>
                # Edit .env with at least one LLM key (Dialogram, GitHub, or Groq)
              </code>
            </div>
            <div className="rounded-lg bg-surface-2 border border-border p-3 space-y-2">
              <p className="font-medium text-foreground">3. Start backend</p>
              <code className="block bg-surface-3 px-2 py-1.5 rounded text-xs font-mono text-foreground">
                uvicorn main:app --host 0.0.0.0 --port 8000
              </code>
              <p className="text-xs text-muted">
                Or run <code className="bg-surface-2 px-1 rounded">./start.sh</code> which auto-activates the venv.
                Override the port with <code className="bg-surface-2 px-1 rounded">PORT=9000 ./start.sh</code>.
              </p>
            </div>
            <div className="rounded-lg bg-surface-2 border border-border p-3 space-y-2">
              <p className="font-medium text-foreground">4. Start frontend (new terminal)</p>
              <code className="block bg-surface-3 px-2 py-1.5 rounded text-xs font-mono text-foreground">
                cd ../frontend && npm install && npm run dev
              </code>
              <p className="text-xs">Open <strong className="text-foreground">http://localhost:3000</strong></p>
            </div>
          </div>
        </section>

        <section>
          <h4 className="text-accent font-semibold mb-2 text-base">Which Model Will Be Used?</h4>
          <p className="text-sm text-muted mb-2">
            The app <strong>automatically picks</strong> the right engine based on your settings. The badge next to "Audio" shows you which one:
          </p>
          <div className="rounded-lg bg-surface-2 border border-border p-3 space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span><strong>Realtime 0.5B</strong> — English monologue, ≤10 min</span>
              <Badge variant="accent"><Zap className="w-3 h-3" />Fast</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span><strong>Longform 1.5B</strong> — Interview / Panel / &gt;10 min / Non-English</span>
              <Badge variant="warning"><Cpu className="w-3 h-3" />Slow</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span><strong>Sarvam Bulbul</strong> — Indian languages (cloud)</span>
              <Badge variant="success"><Globe className="w-3 h-3" />Cloud</Badge>
            </div>
          </div>
        </section>

        <section>
          <h4 className="text-accent font-semibold mb-2 text-base">Model Downloads (First Time Only)</h4>
          <p className="mb-2 text-sm">
            Models download <strong>automatically from HuggingFace</strong> on first use. No manual download needed. Requires ~15 GB disk space.
          </p>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span>Realtime 0.5B (English fast)</span>
              <span className="text-foreground">~2 GB · downloads in ~2–5 min</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span>Longform 1.5B (English multi-speaker)</span>
              <span className="text-foreground">~5.4 GB · downloads in ~5–10 min</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span>ASR 7B (Speech-to-text)</span>
              <span className="text-foreground">~14 GB · downloads in ~10–15 min</span>
            </div>
          </div>
          <div className="mt-3 rounded-lg bg-surface-2 border border-border p-3 space-y-2">
            <p className="font-medium text-foreground text-sm">How to check if models are ready</p>
            <p className="text-xs text-muted">Run these commands in your terminal:</p>
            <code className="block bg-surface-3 px-2 py-1.5 rounded text-xs font-mono text-foreground">
              curl http://localhost:8000/models/status | python3 -m json.tool
            </code>
            <p className="text-xs text-muted">Or check disk cache:</p>
            <code className="block bg-surface-3 px-2 py-1.5 rounded text-xs font-mono text-foreground">
              du -sh ~/.cache/huggingface/hub/models--microsoft--VibeVoice-*/
            </code>
          </div>
          <p className="mt-2 text-xs text-muted">
            The UI shows a <Badge variant="success" className="text-[10px]"><CheckCircle className="w-3 h-3" />Ready</Badge> badge when the model is loaded. Wait for it before clicking Generate Audio.
          </p>
        </section>

        <section>
          <h4 className="text-accent font-semibold mb-2 text-base">API Keys</h4>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Dialogram</strong> — Primary script provider (free tier).</li>
            <li><strong>GitHub Models</strong> — Free GPT-4o fallback (GitHub PAT).</li>
            <li><strong>Groq / DeepSeek / Gemini / Mistral / Together / OpenRouter</strong> — Optional fallbacks.</li>
            <li><strong>Sarvam</strong> — Required only for Indian-language audio.</li>
          </ul>
          <p className="mt-2 text-xs">
            Keys saved locally in <code className="bg-surface-2 px-1 rounded">user_config.json</code>. Never sent to our servers.
          </p>
        </section>

        <section>
          <h4 className="text-accent font-semibold mb-2 text-base">Managing Episodes</h4>
          <ul className="list-disc pl-5 space-y-1">
            <li>Episodes auto-save to <code className="bg-surface-2 px-1 rounded">outputs/</code> with metadata JSON.</li>
            <li>Use <em>Recent Episodes</em> to play, rename, delete, or download.</li>
            <li>Filter by format (Solo / 2-Person / 3-Person Panel) or language.</li>
            <li><em>RSS Feed</em> gives a podcast-compatible URL for any player.</li>
          </ul>
        </section>

        <section>
          <h4 className="text-accent font-semibold mb-2 text-base">Troubleshooting</h4>
          <div className="space-y-2">
            <p>
              <strong className="text-foreground">Script generation fails?</strong>
              <br />
              Check Settings for at least one LLM key. Dialogram free tier can rate-limit — retry in a few seconds.
            </p>
            <p>
              <strong className="text-foreground">Audio very slow?</strong>
              <br />
              Longform 1.5B takes 5–15 min on Apple Silicon. Choose monologue ≤10 min for fastest results.
            </p>
            <p>
              <strong className="text-foreground">No audio plays?</strong>
              <br />
              Ensure backend is running on port 8000 and the <code className="bg-surface-2 px-1 rounded">outputs/</code> folder exists.
            </p>
          </div>
        </section>
      </div>
    </Modal>
  );
}

function ArchitectureModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="System Architecture" className="max-w-5xl">
      <div className="space-y-4 text-sm text-muted">
        <p>
          Podcast Brain Pro is split into a cloud-facing frontend and a local GPU backend.
          Script generation happens instantly in the cloud, while audio synthesis runs entirely on your machine.
        </p>
        <div className="rounded-xl border border-border overflow-hidden bg-surface-2">
          <img
            src="/architecture.svg"
            alt="Podcast Brain Pro Architecture Diagram"
            className="w-full h-auto"
          />
        </div>
        <div className="flex items-center justify-between rounded-lg border border-border bg-surface-2 px-3 py-2">
          <div className="text-xs">
            <span className="font-medium text-foreground">Editable source:</span> Open this diagram in Excalidraw or Obsidian Excalidraw
          </div>
          <a
            href="/PodcastBrainPro-Architecture.excalidraw"
            download
            className="text-xs font-medium text-accent hover:underline"
          >
            Download .excalidraw
          </a>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="rounded-lg border border-border bg-surface-2 p-3">
            <div className="font-semibold text-foreground mb-1">Frontend</div>
            <div className="text-xs">Next.js 14 · React · Tailwind CSS · Framer Motion</div>
          </div>
          <div className="rounded-lg border border-border bg-surface-2 p-3">
            <div className="font-semibold text-foreground mb-1">Backend</div>
            <div className="text-xs">FastAPI · Python · PyTorch · Transformers</div>
          </div>
          <div className="rounded-lg border border-border bg-surface-2 p-3">
            <div className="font-semibold text-foreground mb-1">Script LLM</div>
            <div className="text-xs">Dialogram Qwen 3.6 Plus with 9-provider fallback chain</div>
          </div>
          <div className="rounded-lg border border-border bg-surface-2 p-3">
            <div className="font-semibold text-foreground mb-1">TTS Models</div>
            <div className="text-xs">VibeVoice Realtime 0.5B · VibeVoice Longform 1.5B · Sarvam Bulbul</div>
          </div>
        </div>
      </div>
    </Modal>
  );
}
