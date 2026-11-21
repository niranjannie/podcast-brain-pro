export type Format = "monologue" | "interview" | "panel";

export type Language =
  | "en"
  | "hi-IN"
  | "ta-IN"
  | "te-IN"
  | "kn-IN"
  | "bn-IN"
  | "mr-IN"
  | "gu-IN"
  | "ml-IN"
  | "pa-IN"
  | "od-IN";

export const DELIVERY_STYLES = ["neutral", "calm", "narrative", "serious", "warm", "excited"] as const;
export type DeliveryStyle = (typeof DELIVERY_STYLES)[number];

export interface ScriptLine {
  speaker: string;
  content: string;
}

export interface ConfigStatus {
  configured: boolean;
  masked: string;
}

export interface LoudnessInfo {
  integrated_lufs: number;
  true_peak_db: number;
}

export interface HistoryItem {
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
  engine?: string;
  loudness?: LoudnessInfo;
}

export interface VoiceInfo {
  id: string;
  language: string;
  gender: string;
  name: string;
}

export interface VoiceCatalogue {
  longform: VoiceInfo[];
  streaming: VoiceInfo[];
  styles: string[];
}

export interface EngineInfo {
  id: string;
  label: string;
  license: string;
  commercial: boolean;
  cloning: boolean;
  languages: string;
  download: string;
  memory: string;
  install: string;
  notes: string;
  wired: boolean;
  installed: boolean;
  health: { ok: boolean; detail: string };
  voices: string[];
}

export interface ModelStatus {
  realtime: { cached: boolean; loaded: boolean };
  longform: { cached: boolean; loaded: boolean };
  asr: { cached: boolean; loaded: boolean };
  limits?: { max_longform_words: number; chunking_enabled: boolean; device: string };
  system?: { ram_gb?: number; torch_version?: string; mps_available?: boolean; device?: string };
}

export type ViewId = "create" | "library" | "voicelab";

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  return "Unknown error";
}

export function isAbortError(error: unknown): boolean {
  return typeof error === "object" && error !== null && "name" in error && error.name === "AbortError";
}

export function countWords(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

export async function readError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const parsed = JSON.parse(text);
    return parsed.detail || parsed.message || text || `HTTP ${res.status}`;
  } catch {
    return text || `HTTP ${res.status}`;
  }
}
