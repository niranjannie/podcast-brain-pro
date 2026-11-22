"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ConfigStatus,
  ContentExtras,
  DeliveryStyle,
  EngineInfo,
  Format,
  HistoryItem,
  Language,
  ModelStatus,
  ScriptLine,
  SocialClip,
  VoiceCatalogue,
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
const AUDIO_BACKEND_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

function audioEndpoint(path: string): string {
  return `${AUDIO_BACKEND_URL}${path}`;
}

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
  const [episodeEngine, setEpisodeEngine] = useState("vibevoice");

  // ---- Catalogues ----
  const [voices, setVoices] = useState<VoiceCatalogue>({ longform: [], streaming: [], cloned: [], styles: [] });
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [config, setConfig] = useState<Record<string, ConfigStatus>>({});

  // ---- Script ----
  const [script, setScript] = useState<ScriptLine[] | null>(null);
  const [scriptStats, setScriptStats] = useState("");
  const [isGeneratingScript, setIsGeneratingScript] = useState(false);
  const [scriptError, setScriptError] = useState<string | null>(null);
  const [extras, setExtras] = useState<ContentExtras | null>(null);
  const [extrasError, setExtrasError] = useState<string | null>(null);
  const [isGeneratingExtras, setIsGeneratingExtras] = useState(false);
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
  const extrasRunIdRef = useRef(0);
  const audioTimerRef = useRef<number | undefined>(undefined);

  // ---- Derived ----
  const speakers = useMemo(() => getSpeakers(format, speakerNames), [format, speakerNames]);
  const isIndic = language !== "en";
  const usesLongform = isIndic || format !== "monologue" || duration > 10;

  const availableVoices = useMemo(() => {
    if (isIndic) return SARVAM_VOICES;
    if (episodeEngine === "chatterbox") {
      return voices.cloned.filter((voice) => voice.engine === "chatterbox").map((voice) => voice.id);
    }
    if (episodeEngine === "kokoro" || episodeEngine === "qwen3-tts") {
      const engineVoices = engines.find((engine) => engine.id === episodeEngine)?.voices ?? [];
      const cloned = episodeEngine === "qwen3-tts"
        ? voices.cloned.filter((voice) => voice.engine === "qwen3-tts").map((voice) => voice.id)
        : [];
      return [...engineVoices, ...cloned];
    }
    const catalogue = (usesLongform ? voices.longform : voices.streaming).map((v) => v.id);
    if (catalogue.length > 0) return catalogue;
    return usesLongform ? LONGFORM_FALLBACK : REALTIME_FALLBACK;
  }, [isIndic, episodeEngine, usesLongform, voices, engines]);

  const voiceLabels = useMemo(() => {
    const labels: Record<string, string> = {};
    for (const voice of [...voices.longform, ...voices.streaming, ...voices.cloned]) {
      labels[voice.id] = `${voice.name} (${voice.gender})`;
    }
    return labels;
  }, [voices]);

  const scriptWordCount = useMemo(
    () => (script ?? []).reduce((sum, line) => sum + countWords(line.content), 0),
    [script]
  );

  const usesVibeVoice = episodeEngine === "vibevoice";
  const selectedEngineInfo = engines.find((engine) => engine.id === episodeEngine);
  const requiredModel = isIndic || !usesVibeVoice
    ? null
    : usesLongform
      ? modelStatus?.longform
      : modelStatus?.realtime;
  const modelCached = isIndic || !usesVibeVoice ? true : (requiredModel?.cached ?? false);
  const modelReady = isIndic || !usesVibeVoice ? true : (requiredModel?.loaded ?? false);
  const engineLabel = isIndic
    ? "Sarvam Cloud"
    : !usesVibeVoice
      ? selectedEngineInfo?.label ?? episodeEngine
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

  const fetchVoices = useCallback(async () => {
    try {
      const res = await fetch("/api/voices");
      if (!res.ok) return;
      const data = await res.json();
      setVoices({
        longform: data.longform ?? [],
        streaming: data.streaming ?? [],
        cloned: data.cloned ?? [],
        styles: data.styles ?? [],
      });
    } catch {
      // Existing presets remain available when the backend is offline.
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
    fetchVoices();

    fetch("/api/engines")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setEngines(data.engines ?? []);
      })
      .catch(() => undefined);
  }, [fetchConfig, loadHistory, fetchSystem, fetchVoices]);

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
    extrasRunIdRef.current += 1;
    setIsGeneratingExtras(false);
    setIsGeneratingScript(true);
    setScript(null);
    setScriptError(null);
    setExtras(null);
    setExtrasError(null);
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
          include_extras: true,
        }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      if (runId !== scriptRunIdRef.current) return;
      setScript(data.script);
      setExtras(data.extras ?? null);
      setExtrasError(data.extras_error ?? null);
      const shortNote = data.under_target ? " · shorter than requested" : "";
      setScriptStats(`${data.word_count} words · ${data.generation_time_seconds}s${shortNote}`);
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
    })).filter((line) => line.content.trim());
    if (!updated.length) {
      setScriptError("The script needs at least one non-empty turn");
      return;
    }
    setScript(updated);
    extrasRunIdRef.current += 1;
    setIsGeneratingExtras(false);
    setHasEdits(false);
    setEditedLines({});
    setExtras(null);
    setExtrasError("Script changed. Refresh show notes, chapters, and clips before rendering.");
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

  function renameSpeaker(index: number, value: string) {
    const previous = speakers[index];
    const nextNames = [...speakerNames];
    nextNames[index] = value;
    setSpeakerNames(nextNames);
    if (script && value.trim() && previous !== value.trim()) {
      const nextName = value.trim();
      setScript(script.map((line) => line.speaker === previous ? { ...line, speaker: nextName } : line));
      extrasRunIdRef.current += 1;
      setIsGeneratingExtras(false);
      setExtras(null);
      setExtrasError("Cast changed. Refresh show notes, chapters, and clips before rendering.");
    }
  }

  async function generateExtras() {
    if (!script || !topic.trim() || isGeneratingExtras) return;
    const runId = ++extrasRunIdRef.current;
    setIsGeneratingExtras(true);
    setExtrasError(null);
    try {
      const res = await fetch("/api/podcast/extras", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic.trim(),
          script,
          duration_minutes: duration,
          format,
          language,
        }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      if (runId !== extrasRunIdRef.current) return;
      setExtras(data.extras);
    } catch (error) {
      if (runId === extrasRunIdRef.current) setExtrasError(errorMessage(error));
    } finally {
      if (runId === extrasRunIdRef.current) setIsGeneratingExtras(false);
    }
  }

  // ---- Audio actions ----
  function cancelAudio() {
    audioAbortRef.current?.abort();
    window.clearInterval(audioTimerRef.current);
    setIsGeneratingAudio(false);
    setAudioStatusText("Cancelled");
  }

  async function requestAudio(
    turns: ScriptLine[],
    persist: boolean,
    requestTopic: string,
    signal?: AbortSignal,
  ): Promise<Response> {
    const normalizedTurns = turns.filter((line) => line.content.trim());
    const castOrder: string[] = [];
    for (const line of normalizedTurns) {
      if (!castOrder.includes(line.speaker)) castOrder.push(line.speaker);
    }
    const voiceNames = castOrder.map((speaker) => {
      const configuredIndex = speakers.indexOf(speaker);
      const selectionIndex = configuredIndex >= 0 ? configuredIndex : castOrder.indexOf(speaker);
      return voiceSelections[selectionIndex] ?? speaker;
    });
    const requestExtras = persist ? extras : null;

    if (isIndic) {
      return fetch(audioEndpoint("/tts/sarvam"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal,
        body: JSON.stringify({
          text: normalizedTurns.map((line) => line.content).join("\n\n"),
          script: normalizedTurns,
          voice_names: voiceNames,
          target_language_code: language,
          speaker: voiceNames[0] || "shubh",
          pace: 1.0,
          model: "bulbul:v3",
          output_audio_codec: "wav",
          save_to_disk: persist,
          topic: requestTopic || undefined,
          format,
          language,
          duration_minutes: duration,
          style: deliveryStyle,
          extras: requestExtras,
        }),
      });
    }

    if (usesLongform || !usesVibeVoice) {
      return fetch(audioEndpoint("/tts/longform"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal,
        body: JSON.stringify({
          script: normalizedTurns,
          voice_names: voiceNames,
          engine: episodeEngine,
          style: deliveryStyle,
          save_to_disk: persist,
          topic: requestTopic || undefined,
          format,
          language,
          duration_minutes: duration,
          extras: requestExtras,
        }),
      });
    }

    return fetch(audioEndpoint("/tts/realtime"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal,
      body: JSON.stringify({
        text: normalizedTurns.map((line) => line.content).join("\n\n"),
        speaker_name: voiceNames[0] || "Carter",
        style: deliveryStyle,
        save_to_disk: persist,
        topic: requestTopic || undefined,
        format,
        language,
        duration_minutes: duration,
        extras: requestExtras,
      }),
    });
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
    const extrasRunId = extrasRunIdRef.current;
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
      const res = await requestAudio(script, true, topic.trim(), abortCtrl.signal);

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
      if (extras?.chapters.length && savedFilename) {
        try {
          const chaptersUrl = `/outputs/${savedFilename.replace(/\.wav$/i, ".chapters.json")}`;
          const chaptersResponse = await fetch(chaptersUrl);
          if (chaptersResponse.ok && extrasRunId === extrasRunIdRef.current) {
            const chapterData = await chaptersResponse.json();
            if (extrasRunId !== extrasRunIdRef.current) return;
            setExtras({
              ...extras,
              chapters: extras.chapters.map((chapter, index) => ({
                ...chapter,
                startTime: chapterData.chapters[index]?.startTime,
              })),
            });
          }
        } catch {
          // The generated audio is still valid; planned chapters remain visible.
        }
      }
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
      extras,
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

  async function renderSocialClip(clip: SocialClip): Promise<{ url: string; filename: string }> {
    if (!script) throw new Error("Load the source script first");
    const normalizedScript = script.filter((line) => line.content.trim());
    const turns = normalizedScript.slice(clip.start_turn, clip.end_turn + 1);
    if (!turns.length) throw new Error("The selected clip has no script turns");
    const res = await requestAudio(turns, false, `${topic.trim()} - ${clip.title}`);
    if (!res.ok) throw new Error(await readError(res));
    const blob = await res.blob();
    const safeName = clip.title.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "").toLowerCase() || "clip";
    return { url: URL.createObjectURL(blob), filename: `${safeName}.wav` };
  }

  // ---- Library actions ----
  async function loadEpisodeForRerender(item: HistoryItem): Promise<boolean> {
    try {
      const stem = item.filename.replace(/\.wav$/i, "");
      const res = await fetch(`/outputs/${encodeURIComponent(stem)}.transcript.json`);
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      if (!Array.isArray(data.script) || data.script.length === 0) {
        throw new Error("The saved transcript has no script turns");
      }
      const loadedScript: ScriptLine[] = data.script.map((line: ScriptLine) => ({
        speaker: String(line.speaker),
        content: String(line.content),
      })).filter((line: ScriptLine) => line.content.trim());
      if (!loadedScript.length) throw new Error("The saved transcript has no spoken turns");
      extrasRunIdRef.current += 1;
      setIsGeneratingExtras(false);
      const names: string[] = [];
      for (const line of loadedScript) {
        if (!names.includes(line.speaker)) names.push(line.speaker);
      }
      setTopic(data.topic || item.topic || item.title || "");
      setDuration(DURATIONS.includes(data.duration_minutes) ? data.duration_minutes : 2);
      setFormat(["monologue", "interview", "panel"].includes(data.format) ? data.format : (item.format as Format) || "monologue");
      setLanguage((data.language || item.language || "en") as Language);
      setSpeakerNames([names[0] || "Host", names[1] || "Guest", names[2] || "Guest 2"]);
      setVoiceSelections(data.voice_names?.length ? data.voice_names : data.speaker_name ? [data.speaker_name] : []);
      setEpisodeEngine(["vibevoice", "kokoro", "qwen3-tts", "chatterbox"].includes(data.engine) ? data.engine : "vibevoice");
      setScript(loadedScript);
      setExtras(data.extras || item.extras || null);
      setExtrasError(null);
      setEditedLines({});
      setHasEdits(false);
      setScriptStats(`${loadedScript.reduce((sum, line) => sum + countWords(line.content), 0)} words · loaded from Library`);
      setAudioUrl(`/outputs/${encodeURIComponent(item.filename)}`);
      setAudioFilename(item.filename);
      setAudioError(null);
      setAudioStatusText("Saved episode loaded; change cast or delivery and render again");
      return true;
    } catch (error) {
      setHistoryError(`Could not load transcript: ${errorMessage(error)}`);
      return false;
    }
  }

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
  async function auditionVoice(voice: string, speaker?: string): Promise<{ url: string; filename: string }> {
    const scriptLine = speaker ? script?.find((line) => line.speaker === speaker) : undefined;
    const rawText = scriptLine?.content || `Hi, this is ${speaker || "your host"}. This is my delivery for the show.`;
    const firstSentence = rawText.match(/^[\s\S]{1,240}?[.!?](?:\s|$)/)?.[0];
    const text = (firstSentence || rawText).slice(0, 240).trim();
    let res: Response;
    if (isIndic) {
      res = await fetch(audioEndpoint("/tts/sarvam"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          target_language_code: language,
          speaker: voice,
          output_audio_codec: "wav",
          style: deliveryStyle,
          save_to_disk: false,
        }),
      });
    } else if (usesVibeVoice && usesLongform) {
      res = await fetch(audioEndpoint("/tts/longform"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          script: [{ speaker: speaker || "Host", content: text }],
          voice_names: [voice],
          engine: "vibevoice",
          style: deliveryStyle,
          save_to_disk: false,
        }),
      });
    } else if (usesVibeVoice) {
      res = await fetch(audioEndpoint("/tts/realtime"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, speaker_name: voice, style: deliveryStyle, save_to_disk: false }),
      });
    } else {
      res = await fetch(audioEndpoint("/tts/engine"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          engine: episodeEngine,
          voice,
          language,
          style: deliveryStyle,
          save_to_disk: false,
        }),
      });
    }
    if (!res.ok) throw new Error(await readError(res));
    return {
      url: URL.createObjectURL(await res.blob()),
      filename: `${(speaker || "voice").replace(/[^a-z0-9]+/gi, "_").toLowerCase()}_preview.wav`,
    };
  }

  async function engineSpeak(input: {
    text: string;
    engine: string;
    voice?: string;
    language?: string;
    style?: DeliveryStyle;
  }): Promise<{ url: string; filename: string }> {
    const res = await fetch(audioEndpoint("/tts/engine"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: input.text,
        engine: input.engine,
        voice: input.voice,
        language: input.language ?? "en",
        style: input.style ?? "neutral",
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
    referenceText?: string;
    language?: string;
    consent: boolean;
  }): Promise<{ url: string; filename: string }> {
    const form = new FormData();
    form.append("text", input.text);
    form.append("engine", input.engine);
    form.append("consent", String(input.consent));
    form.append("reference", input.reference);
    form.append("reference_text", input.referenceText ?? "");
    form.append("language", input.language ?? "en");
    const res = await fetch(audioEndpoint("/tts/clone"), { method: "POST", body: form });
    if (!res.ok) throw new Error(await readError(res));
    const blob = await res.blob();
    await fetchVoices();
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
    renameSpeaker,
    voiceSelections, setVoiceSelections,
    deliveryStyle, setDeliveryStyle,
    episodeEngine, setEpisodeEngine,
    usesVibeVoice,
    selectedEngineInfo,
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
    extras,
    extrasError, setExtrasError,
    isGeneratingExtras,
    generateExtras,
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
    renderSocialClip,
    // library
    history,
    filteredHistory,
    historyError, setHistoryError,
    historySearch, setHistorySearch,
    historyLimit,
    loadEpisodeForRerender,
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
