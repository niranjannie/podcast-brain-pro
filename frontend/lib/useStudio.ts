"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ConfigStatus,
  DeliveryStyle,
  EngineInfo,
  Format,
  HistoryItem,
  Language,
  ModelStatus,
  ScriptLine,
  VoiceCatalogue,
  VoiceInfo,
  countWords,
  errorMessage,
  isAbortError,
  readError,
} from "./studio-types";

const DURATIONS = [2, 5, 10, 15, 30];
const SARVAM_VOICES = [
  "shubh", "shreya", "manan", "ishita", "aditya", "ritu", "priya", "neha",
  "rahul", "pooja", "rohan", "simran", "kavya", "amit", "dev",
];
const LONGFORM_FALLBACK = ["Alice", "Carter", "Frank"];
const REALTIME_FALLBACK = ["Carter", "Emma", "Davis", "Grace", "Mike", "Wayne"];
const HISTORY_PAGE = 20;

export function getSpeakers(format: Format, names: string[]): string[] {
  if (format === "monologue") return [names[0] || "Host"];
  if (format === "interview") return [names[0] || "Host", names[1] || "Guest"];
  return [names[0] || "Host", names[1] || "Guest 1", names[2] || "Guest 2"];
}

export function useStudio() {
  // ---- Brief ----
  const [topic, setTopic] = useState("");
  const [duration, setDuration] = useState(2);
  const [format, setFormat] = useState<Format>("monologue");
  const [language, setLanguage] = useState<Language>("en");
  const [speakerNames, setSpeakerNames] = useState(["Host", "Guest", "Guest 2"]);
  const [voiceSelections, setVoiceSelections] = useState<string[]>([]);
  const [deliveryStyle, setDeliveryStyle] = useState<DeliveryStyle>("neutral");

  // ---- Catalogues ----
  const [voices, setVoices] = useState<VoiceCatalogue>({ longform: [], streaming: [], styles: [] });
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [config, setConfig] = useState<Record<string, ConfigStatus>>({});

  // ---- Script ----
  const [script, setScript] = useState<ScriptLine[] | null>(null);
  const [scriptStats, setScriptStats] = useState("");
  const [isGeneratingScript, setIsGeneratingScript] = useState(false);
  const [scriptError, setScriptError] = useState<string | null>(null);
  const [editedLines, setEditedLines] = useState<Record<number, string>>({});
  const [hasEdits, setHasEdits] = useState(false);

  // ---- Audio ----
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioFilename, setAudioFilename] = useState("");
  const [audioStats, setAudioStats] = useState("");
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  const [audioElapsed, setAudioElapsed] = useState(0);
  const [audioStatusText, setAudioStatusText] = useState("");
  const [audioError, setAudioError] = useState<string | null>(null);

  // ---- Library ----
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historySearch, setHistorySearch] = useState("");
  const [historyLimit, setHistoryLimit] = useState(HISTORY_PAGE);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [renamingFile, setRenamingFile] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  // ---- System ----
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  const scriptAbortRef = useRef<AbortController | null>(null);
  const audioAbortRef = useRef<AbortController | null>(null);
  const scriptRunIdRef = useRef(0);
  const audioTimerRef = useRef<number | undefined>(undefined);

  // ---- Derived ----
  const speakers = useMemo(() => getSpeakers(format, speakerNames), [format, speakerNames]);
  const isIndic = language !== "en";
  const usesLongform = isIndic || format !== "monologue" || duration > 10;

  const availableVoices = useMemo(() => {
    if (isIndic) return SARVAM_VOICES;
    const catalogue = (usesLongform ? voices.longform : voices.streaming).map((v) => v.id);
    if (catalogue.length > 0) return catalogue;
    return usesLongform ? LONGFORM_FALLBACK : REALTIME_FALLBACK;
  }, [isIndic, usesLongform, voices]);

  const voiceLabels = useMemo(() => {
    const labels: Record<string, string> = {};
    for (const voice of [...voices.longform, ...voices.streaming]) {
      labels[voice.id] = `${voice.name} (${voice.gender})`;
    }
    return labels;
  }, [voices]);

  const scriptWordCount = useMemo(
    () => (script ?? []).reduce((sum, line) => sum + countWords(line.content), 0),
    [script]
  );

  const requiredModel = isIndic ? null : usesLongform ? modelStatus?.longform : modelStatus?.realtime;
  const modelCached = isIndic ? true : (requiredModel?.cached ?? false);
  const modelReady = isIndic ? true : (requiredModel?.loaded ?? false);
  const engineLabel = isIndic
    ? "Sarvam Cloud"
    : usesLongform
      ? "VibeVoice Longform 1.5B"
      : "VibeVoice Realtime 0.5B";

  const filteredHistory = useMemo(() => {
    const needle = historySearch.trim().toLowerCase();
    if (!needle) return history;
    return history.filter((item) =>
      [item.filename, item.topic, item.title, item.format, item.language]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle))
    );
  }, [history, historySearch]);

  // ---- Data loading ----
  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch("/api/config");
      if (res.ok) setConfig(await res.json());
    } catch {
      /* the settings modal shows what it could load */
    }
  }, []);

  const loadHistory = useCallback(async (limit: number) => {
    try {
      const res = await fetch(`/api/podcast/history?limit=${limit}`);
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      setHistory(data.files ?? []);
      setHistoryError(null);
    } catch (error) {
      setHistoryError(errorMessage(error));
    }
  }, []);

  const fetchSystem = useCallback(async () => {
    try {
      const health = await fetch("/api/health", { cache: "no-store" });
      setBackendOnline(health.ok);
    } catch {
      setBackendOnline(false);
    }
    try {
      const res = await fetch("/api/models/status", { cache: "no-store" });
      if (res.ok) setModelStatus(await res.json());
    } catch {
      /* health already reported the backend state */
    }
  }, []);

  useEffect(() => {
    fetchConfig();
    loadHistory(HISTORY_PAGE);
    fetchSystem();

    fetch("/api/voices")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setVoices({
            longform: data.longform ?? [],
            streaming: data.streaming ?? [],
            styles: data.styles ?? [],
          });
        }
      })
      .catch(() => undefined);

    fetch("/api/engines")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setEngines(data.engines ?? []);
      })
      .catch(() => undefined);
  }, [fetchConfig, loadHistory, fetchSystem]);

  // Poll the backend, but only while the tab is visible.
  useEffect(() => {
    let interval: number | undefined;
    const start = () => {
      window.clearInterval(interval);
      interval = window.setInterval(() => {
        if (document.visibilityState === "visible") fetchSystem();
      }, 15000);
    };
    start();
    document.addEventListener("visibilitychange", start);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", start);
    };
  }, [fetchSystem]);

  // Keep the cast valid for the engine that will actually render the episode.
  useEffect(() => {
    setVoiceSelections((previous) => {
      const valid = previous.filter((voice) => availableVoices.includes(voice));
      return Array.from({ length: speakers.length }, (_, index) => {
        const kept = valid[index];
        if (kept && !valid.slice(0, index).includes(kept)) return kept;
        const used = new Set(valid.slice(0, index));
        const next = availableVoices.find((voice) => !used.has(voice));
        return next ?? availableVoices[index % availableVoices.length];
      });
    });
  }, [format, language, duration, speakers.length, availableVoices]);

  // Revoke blob URLs when they are replaced.
  useEffect(() => {
    return () => {
      if (audioUrl?.startsWith("blob:")) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  // Stop everything when the page unloads.
  useEffect(() => {
    return () => {
      scriptAbortRef.current?.abort();
      audioAbortRef.current?.abort();
      window.clearInterval(audioTimerRef.current);
    };
  }, []);

  // ---- Script actions ----
  function stopScriptGeneration() {
    scriptAbortRef.current?.abort();
    scriptAbortRef.current = null;
    setIsGeneratingScript(false);
  }

  async function generateScript() {
    if (!topic.trim() || isGeneratingScript) return;
    const runId = ++scriptRunIdRef.current;
    setIsGeneratingScript(true);
    setScript(null);
    setScriptError(null);
    setScriptStats("");
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
          style: deliveryStyle,
        }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      if (runId !== scriptRunIdRef.current) return;
      setScript(data.script);
      setScriptStats(`${data.word_count} words · ${data.generation_time_seconds}s`);
    } catch (error) {
      if (runId !== scriptRunIdRef.current) return;
      if (isAbortError(error)) {
        setScriptStats("Generation cancelled");
      } else {
        setScriptError(errorMessage(error));
      }
    } finally {
      if (runId === scriptRunIdRef.current) {
        setIsGeneratingScript(false);
        scriptAbortRef.current = null;
      }
    }
  }

  function saveEdits() {
    if (!script) return;
    const updated = script.map((line, index) => ({
      ...line,
      content: editedLines[index] !== undefined ? editedLines[index] : line.content,
    }));
    setScript(updated);
    setHasEdits(false);
    setEditedLines({});
    setScriptStats(`${updated.reduce((sum, line) => sum + countWords(line.content), 0)} words · edited`);
  }

  function editLine(index: number, value: string) {
    setEditedLines((previous) => ({ ...previous, [index]: value }));
    setHasEdits(true);
  }

  function addPause(index: number) {
    if (!script) return;
    const current = editedLines[index] ?? script[index].content;
    editLine(index, `${current.replace(/\s+$/, "")} [[pause:0.6]]`);
  }

  // ---- Audio actions ----
  function cancelAudio() {
    audioAbortRef.current?.abort();
    window.clearInterval(audioTimerRef.current);
    setIsGeneratingAudio(false);
    setAudioStatusText("Cancelled");
  }

  async function generateAudio() {
    if (!script || isGeneratingAudio) return;
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setIsGeneratingAudio(true);
    setAudioUrl(null);
    setAudioError(null);
    setAudioStats("");
    setAudioElapsed(0);
    setAudioStatusText("Starting the engine...");

    const startedAt = Date.now();
    window.clearInterval(audioTimerRef.current);
    audioTimerRef.current = window.setInterval(() => {
      setAudioElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    const abortCtrl = new AbortController();
    audioAbortRef.current = abortCtrl;

    // A hung job is abandoned after 35 minutes rather than spinning forever.
    const safetyTimer = window.setTimeout(() => {
      abortCtrl.abort();
      window.clearInterval(audioTimerRef.current);
      setIsGeneratingAudio(false);
      setAudioStatusText("Timed out");
      setAudioError(
        "Audio generation timed out after 35 minutes. The backend may still be working — check the outputs folder or logs/audio_generation.log."
      );
    }, 35 * 60 * 1000);

    try {
      let res: Response;
      if (isIndic) {
        const fullText = script.map((line) => line.content).join("\n\n");
        res = await fetch("/api/tts/sarvam", {
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
      } else if (usesLongform) {
        // Real speaker names go over the wire; the backend maps them to voices.
        const castOrder: string[] = [];
        for (const line of script) {
          if (!castOrder.includes(line.speaker)) castOrder.push(line.speaker);
        }
        const voiceNames = castOrder.map(
          (speaker) => voiceSelections[Math.max(0, speakers.indexOf(speaker))] ?? speaker
        );
        res = await fetch("/api/tts/longform", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: abortCtrl.signal,
          body: JSON.stringify({
            script: script.map((line) => ({ speaker: line.speaker, content: line.content })),
            voice_names: voiceNames,
            style: deliveryStyle,
            save_to_disk: true,
            topic: topic.trim() || undefined,
            format,
            language,
          }),
        });
      } else {
        res = await fetch("/api/tts/realtime", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: abortCtrl.signal,
          body: JSON.stringify({
            text: script.map((line) => line.content).join("\n\n"),
            speaker_name: voiceSelections[0] || "Carter",
            style: deliveryStyle,
            save_to_disk: true,
            topic: topic.trim() || undefined,
            format,
            language,
          }),
        });
      }

      if (!res.ok) throw new Error(await readError(res));
      const savedFilename = res.headers.get("X-Saved-Filename") ?? "";
      const chunks = res.headers.get("X-Chunks-Used");
      const genTime = res.headers.get("X-Gen-Time-Sec");
      const blob = await res.blob();

      if (audioUrl) URL.revokeObjectURL(audioUrl);
      setAudioUrl(URL.createObjectURL(blob));
      setAudioFilename(
        savedFilename || `podcast_${topic.replace(/[^a-z0-9]/gi, "_").toLowerCase()}_${Date.now()}.wav`
      );
      const stats = [
        chunks ? `${chunks} segments` : null,
        genTime ? `${Number(genTime).toFixed(1)}s of synthesis` : null,
        `${Math.round((Date.now() - startedAt) / 1000)}s total`,
      ].filter(Boolean);
      setAudioStats(stats.join(" · "));
      setAudioStatusText("Audio generation complete");
      loadHistory(historyLimit);
    } catch (error) {
      if (isAbortError(error)) {
        setAudioStatusText("Cancelled");
      } else {
        setAudioError(errorMessage(error));
        setAudioStatusText("Error");
      }
    } finally {
      window.clearTimeout(safetyTimer);
      window.clearInterval(audioTimerRef.current);
      audioAbortRef.current = null;
      setIsGeneratingAudio(false);
    }
  }

  function playEpisode(item: HistoryItem) {
    if (audioUrl?.startsWith("blob:")) URL.revokeObjectURL(audioUrl);
    setAudioUrl(`/outputs/${encodeURIComponent(item.filename)}`);
    setAudioFilename(item.filename);
    setAudioStats(
      [item.duration_seconds ? `${Math.round(item.duration_seconds)}s` : null, item.format, item.language]
        .filter(Boolean)
        .join(" · ")
    );
    setAudioError(null);
  }

  function downloadTranscript() {
    if (!script) return;
    const payload = {
      topic: topic.trim(),
      format,
      language,
      duration_minutes: duration,
      delivery: deliveryStyle,
      script: script.map((line) => ({ speaker: line.speaker, content: line.content })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `podcast_${topic.replace(/[^a-z0-9]/gi, "_").toLowerCase() || "episode"}_script.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  // ---- Library actions ----
  async function renameFile(oldFilename: string, newFilename: string) {
    try {
      const res = await fetch("/api/podcast/rename", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_filename: oldFilename, new_filename: newFilename }),
      });
      if (!res.ok) throw new Error(await readError(res));
      setRenamingFile(null);
      setRenameValue("");
      loadHistory(historyLimit);
    } catch (error) {
      setHistoryError(`Rename failed: ${errorMessage(error)}`);
    }
  }

  async function deleteFile(filename: string) {
    if (pendingDelete !== filename) {
      setPendingDelete(filename);
      return;
    }
    setPendingDelete(null);
    try {
      const res = await fetch(`/api/podcast/delete?filename=${encodeURIComponent(filename)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await readError(res));
      if (audioFilename === filename) {
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        setAudioUrl(null);
        setAudioFilename("");
      }
      loadHistory(historyLimit);
    } catch (error) {
      setHistoryError(`Delete failed: ${errorMessage(error)}`);
    }
  }

  function loadMore() {
    const next = historyLimit + HISTORY_PAGE;
    setHistoryLimit(next);
    loadHistory(next);
  }

  // ---- Voice Lab actions ----
  async function auditionVoice(voice: string): Promise<void> {
    const res = await fetch("/api/tts/realtime", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: "Hi, this is what I sound like when I host your show.",
        speaker_name: voice,
        save_to_disk: false,
      }),
    });
    if (!res.ok) throw new Error(await readError(res));
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    new Audio(url).play();
  }

  async function engineSpeak(input: {
    text: string;
    engine: string;
    voice?: string;
  }): Promise<{ url: string; filename: string }> {
    const res = await fetch("/api/tts/engine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: input.text,
        engine: input.engine,
        voice: input.voice,
        save_to_disk: false,
      }),
    });
    if (!res.ok) throw new Error(await readError(res));
    const blob = await res.blob();
    return {
      url: URL.createObjectURL(blob),
      filename: `${input.engine}_voice.wav`,
    };
  }

  async function cloneVoice(input: {
    text: string;
    engine: string;
    reference: File;
    consent: boolean;
  }): Promise<{ url: string; filename: string }> {
    const form = new FormData();
    form.append("text", input.text);
    form.append("engine", input.engine);
    form.append("consent", String(input.consent));
    form.append("reference", input.reference);
    const res = await fetch("/api/tts/clone", { method: "POST", body: form });
    if (!res.ok) throw new Error(await readError(res));
    const blob = await res.blob();
    return {
      url: URL.createObjectURL(blob),
      filename: res.headers.get("X-Saved-Filename") ?? "cloned_voice.wav",
    };
  }

  return {
    // brief
    topic, setTopic,
    duration, setDuration,
    format, setFormat,
    language, setLanguage,
    speakerNames, setSpeakerNames,
    voiceSelections, setVoiceSelections,
    deliveryStyle, setDeliveryStyle,
    durations: DURATIONS,
    speakers,
    isIndic,
    usesLongform,
    availableVoices,
    voiceLabels,
    engineLabel,
    // catalogues
    voices,
    engines,
    config,
    fetchConfig,
    // script
    script, setScript,
    scriptStats,
    scriptWordCount,
    isGeneratingScript,
    scriptError, setScriptError,
    editedLines,
    hasEdits,
    generateScript,
    stopScriptGeneration,
    saveEdits,
    editLine,
    addPause,
    // audio
    audioUrl,
    audioFilename,
    audioStats,
    isGeneratingAudio,
    audioElapsed,
    audioStatusText,
    audioError, setAudioError,
    generateAudio,
    cancelAudio,
    playEpisode,
    downloadTranscript,
    // library
    history,
    filteredHistory,
    historyError, setHistoryError,
    historySearch, setHistorySearch,
    historyLimit,
    pendingDelete, setPendingDelete,
    renamingFile, setRenamingFile,
    renameValue, setRenameValue,
    renameFile,
    deleteFile,
    loadMore,
    refreshHistory: () => loadHistory(historyLimit),
    // system
    modelStatus,
    modelCached,
    modelReady,
    backendOnline,
    refreshSystem: fetchSystem,
    // voice lab
    auditionVoice,
    engineSpeak,
    cloneVoice,
  };
}

export type Studio = ReturnType<typeof useStudio>;
