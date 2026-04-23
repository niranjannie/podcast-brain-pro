"use client";

import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Mic,
  Zap,
  Globe,
  Cpu,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Github,
  ExternalLink,
  CheckCircle,
  Layers,
  Sparkles,
  ArrowRight,
  Settings,
  HelpCircle,
  AlertTriangle,
  Download,
  Terminal,
  Monitor,
  Key,
  BookOpen,
  Eye,
  Music,
  Radio,
  Headphones,
  Timer,
  Hash,
  Star,
} from "lucide-react";

const PROMO_AUDIO = {
  title: "Hear Podcast Brain Pro in Action",
  subtitle: "AI-narrated product story",
  file: "/samples/podcast-brain-pro-promo.wav",
  duration: "~2:30",
};

const SAMPLES = [
  {
    lang: "English",
    flag: "🇺🇸",
    title: "Interview — AI Future Discussion",
    file: "/samples/english-interview.wav",
    duration: "5:12",
    format: "Interview",
    model: "Longform 1.5B",
  },
  {
    lang: "English",
    flag: "🇺🇸",
    title: "Panel — Technology Trends",
    file: "/samples/english-panel.wav",
    duration: "3:42",
    format: "Panel",
    model: "Longform 1.5B",
  },
  {
    lang: "Hindi",
    flag: "🇮🇳",
    title: "Nation Building: India vs China",
    file: "/samples/hindi-nation-building.wav",
    duration: "4:49",
    format: "Interview",
    model: "Sarvam Bulbul",
  },
  {
    lang: "Hindi",
    flag: "🇮🇳",
    title: "Delhi Air Pollution & Government",
    file: "/samples/hindi-delhi-air.wav",
    duration: "4:04",
    format: "Panel",
    model: "Sarvam Bulbul",
  },
  {
    lang: "Kannada",
    flag: "🇮🇳",
    title: "Bangalore News Update",
    file: "/samples/kannada-bangalore-news.wav",
    duration: "3:04",
    format: "Interview",
    model: "Sarvam Bulbul",
  },
];

const STATS = [
  { value: "10", label: "Languages", icon: <Globe className="w-4 h-4" /> },
  { value: "3", label: "Formats", icon: <Layers className="w-4 h-4" /> },
  { value: "0", label: "Cloud Fees", icon: <Zap className="w-4 h-4" /> },
  { value: "∞", label: "Generations", icon: <Sparkles className="w-4 h-4" /> },
];

const USE_CASES = [
  {
    icon: <BookOpen className="w-5 h-5" />,
    title: "Education",
    desc: "Multilingual lesson podcasts, lecture summaries, language learning audio.",
  },
  {
    icon: <Radio className="w-5 h-5" />,
    title: "News & Journalism",
    desc: "Auto-generated audio briefings, regional language news podcasts.",
  },
  {
    icon: <Mic className="w-5 h-5" />,
    title: "Content Creators",
    desc: "Repurpose scripts to podcasts. Batch-produce episodes without recording.",
  },
  {
    icon: <Cpu className="w-5 h-5" />,
    title: "Enterprise",
    desc: "Training audio in multiple languages. Onboarding podcasts. Product explainers.",
  },
  {
    icon: <Volume2 className="w-5 h-5" />,
    title: "Accessibility",
    desc: "Convert docs to audio. Screen-reader content. Visually impaired access.",
  },
  {
    icon: <Headphones className="w-5 h-5" />,
    title: "Developers",
    desc: "Voice-enabled apps, custom assistants, CMS audio integrations.",
  },
];

const SETUP_STEPS = [
  {
    icon: <Terminal className="w-5 h-5" />,
    title: "Clone & Install",
    code: "git clone https://github.com/niranjannie/podcast-brain-pro.git\ncd podcast-brain-pro/voice-service\npython3 -m venv .venv && source .venv/bin/activate\npip install -r requirements.txt",
  },
  {
    icon: <Key className="w-5 h-5" />,
    title: "Configure Keys",
    code: "cp .env.example .env\n# Add Dialogram / GitHub / Groq key",
  },
  {
    icon: <Monitor className="w-5 h-5" />,
    title: "Start Backend",
    code: "./start.sh\n# uvicorn main:app --host 0.0.0.0 --port 8000",
  },
  {
    icon: <Zap className="w-5 h-5" />,
    title: "Start Frontend",
    code: "cd ../frontend && npm install && npm run dev\n# Open http://localhost:3000",
  },
];

function formatTime(seconds: number) {
  if (!isFinite(seconds)) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function AudioPlayer({ src, title, subtitle, showWave = false }: { src: string; title: string; subtitle?: string; showWave?: boolean }) {
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [muted, setMuted] = useState(false);
  const [dragging, setDragging] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onLoaded = () => setDuration(audio.duration || 0);
    const onTime = () => {
      if (!dragging) {
        setCurrentTime(audio.currentTime);
        setProgress(audio.duration ? (audio.currentTime / audio.duration) * 100 : 0);
      }
    };
    const onEnd = () => setPlaying(false);
    // Fallback: if metadata already loaded before listener attached
    if (audio.readyState >= 1) {
      setDuration(audio.duration || 0);
    }
    audio.addEventListener("loadedmetadata", onLoaded);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnd);
    return () => {
      audio.removeEventListener("loadedmetadata", onLoaded);
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnd);
    };
  }, [dragging]);

  const toggle = () => {
    if (!audioRef.current) return;
    if (playing) audioRef.current.pause();
    else audioRef.current.play().catch(() => {});
    setPlaying(!playing);
  };

  const calcSeek = (clientX: number) => {
    const bar = barRef.current;
    if (!bar || !duration) return null;
    const rect = bar.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return pct * duration;
  };

  const seekTo = (clientX: number) => {
    const time = calcSeek(clientX);
    if (time === null || !audioRef.current) return;
    audioRef.current.currentTime = time;
    setCurrentTime(time);
    setProgress((time / duration) * 100);
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    setDragging(true);
    seekTo(e.clientX);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!dragging) return;
    seekTo(e.clientX);
  };

  const handleMouseUp = () => {
    setDragging(false);
  };

  // Global mouse up to catch releases outside the bar
  useEffect(() => {
    if (!dragging) return;
    const up = () => setDragging(false);
    window.addEventListener("mouseup", up);
    return () => window.removeEventListener("mouseup", up);
  }, [dragging]);

  return (
    <div className="rounded-2xl border border-accent/20 bg-gradient-to-br from-accent/10 to-accent/5 p-5 sm:p-6 space-y-4">
      <div className="flex items-center gap-4">
        <button
          onClick={toggle}
          className="w-14 h-14 rounded-full bg-accent flex items-center justify-center text-slate-900 hover:brightness-110 transition-all shadow-lg shadow-accent/30"
        >
          {playing ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 ml-1" />}
        </button>
        <div className="flex-1 min-w-0">
          <div className="text-base font-semibold text-foreground">{title}</div>
          {subtitle && <div className="text-sm text-muted">{subtitle}</div>}
        </div>
        <button onClick={() => { if (audioRef.current) { audioRef.current.muted = !muted; setMuted(!muted); } }} className="text-muted hover:text-foreground">
          {muted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
        </button>
      </div>

      {/* Progress bar — draggable */}
      <div className="space-y-1 select-none">
        <div
          ref={barRef}
          className="h-2 w-full rounded-full bg-surface-3 cursor-pointer overflow-hidden"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          <div
            className="h-full bg-accent rounded-full"
            style={{ width: `${progress}%`, transition: dragging ? "none" : "width 0.1s linear" }}
          />
        </div>
        <div className="flex justify-between text-xs text-muted font-mono">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>

      {/* Waveform visual */}
      {showWave && (
        <div className="flex items-center justify-center gap-0.5 h-8">
          {Array.from({ length: 40 }).map((_, i) => (
            <motion.div
              key={i}
              className="w-1 rounded-full bg-accent/40"
              animate={{
                height: playing ? [4, 16 + Math.random() * 16, 4] : 4,
                opacity: playing ? [0.4, 1, 0.4] : 0.3,
              }}
              transition={{
                duration: 0.6 + Math.random() * 0.4,
                repeat: Infinity,
                delay: i * 0.03,
              }}
              style={{ height: 4 }}
            />
          ))}
        </div>
      )}

      <audio ref={audioRef} src={src} preload="metadata" />
    </div>
  );
}

function MiniPlayer({ src, title, lang, flag, duration, format, model }: any) {
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  const toggle = async () => {
    if (!audioRef.current) return;
    if (playing) {
      audioRef.current.pause();
      setPlaying(false);
    } else {
      setLoading(true);
      try {
        await audioRef.current.play();
        setPlaying(true);
      } catch {
        // autoplay blocked or error
      }
      setLoading(false);
    }
  };

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onEnd = () => setPlaying(false);
    const onPause = () => setPlaying(false);
    const onPlay = () => { setPlaying(true); setLoading(false); };
    audio.addEventListener("ended", onEnd);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("play", onPlay);
    return () => {
      audio.removeEventListener("ended", onEnd);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("play", onPlay);
    };
  }, []);

  return (
    <div className="rounded-xl border border-border bg-surface-2 p-4 flex items-center gap-4 hover:border-accent/30 transition-colors">
      <button
        onClick={toggle}
        disabled={loading}
        className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center text-accent hover:bg-accent hover:text-slate-900 transition-all shrink-0 disabled:opacity-50"
      >
        {loading ? (
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        ) : playing ? (
          <Pause className="w-4 h-4" />
        ) : (
          <Play className="w-4 h-4 ml-0.5" />
        )}
      </button>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{title}</div>
        <div className="text-xs text-muted flex items-center gap-2 mt-0.5">
          <span>{flag} {lang}</span>
          <span>·</span>
          <span>{format}</span>
          <span>·</span>
          <span className="text-accent">{model}</span>
        </div>
      </div>
      <div className="text-xs text-muted font-mono shrink-0">{duration}</div>
      <audio ref={audioRef} src={src} preload="metadata" />
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0a0e1a] text-foreground font-sans selection:bg-accent/30">
      {/* Subtle grid background */}
      <div className="fixed inset-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: "radial-gradient(circle, #fff 1px, transparent 1px)", backgroundSize: "32px 32px" }} />

      {/* Navbar */}
      <nav className="border-b border-white/5 bg-[#0a0e1a]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-indigo-500 flex items-center justify-center shadow-lg shadow-accent/20">
              <Mic className="w-5 h-5 text-slate-900" />
            </div>
            <span className="font-bold text-lg tracking-tight">Podcast Brain Pro</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="https://github.com/niranjannie/podcast-brain-pro" target="_blank" className="flex items-center gap-2 text-sm text-muted hover:text-foreground transition-colors">
              <Github className="w-4 h-4" />
              <span className="hidden sm:inline">GitHub</span>
            </a>
            <a href="#download" className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-slate-900 text-sm font-semibold hover:brightness-110 transition-all">
              <Download className="w-4 h-4" />
              <span className="hidden sm:inline">Try It</span>
            </a>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden pt-16 pb-20 sm:pt-24 sm:pb-32">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-accent/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="max-w-4xl mx-auto px-4 sm:px-6 relative text-center space-y-8">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs font-semibold mb-6">
              <Sparkles className="w-3.5 h-3.5" />
              Open Source · MIT License · Self-Hosted
            </div>
            <h1 className="text-5xl sm:text-7xl font-black tracking-tight leading-[1.1]">
              Generate podcasts{" "}
              <span className="bg-gradient-to-r from-accent via-indigo-400 to-purple-400 bg-clip-text text-transparent">
                with AI
              </span>
            </h1>
            <p className="text-lg sm:text-xl text-muted max-w-2xl mx-auto mt-6 leading-relaxed">
              Research-backed scripts in seconds. Studio-quality audio synthesis locally on your machine.
              English & 10 Indian languages. No cloud fees. No subscription.
            </p>
          </motion.div>

          {/* Promo Audio Player */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }} className="max-w-xl mx-auto">
            <div className="flex items-center gap-2 mb-3 justify-center">
              <Music className="w-4 h-4 text-accent" />
              <span className="text-xs font-semibold text-accent uppercase tracking-wider">AI Voice Demo</span>
              <span className="text-xs text-muted">— AI-generated voice clone</span>
            </div>
            <AudioPlayer src={PROMO_AUDIO.file} title={PROMO_AUDIO.title} subtitle={PROMO_AUDIO.subtitle} showWave />
          </motion.div>

          {/* Stats */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.35 }} className="flex flex-wrap justify-center gap-4 sm:gap-6 pt-4">
            {STATS.map((s) => (
              <div key={s.label} className="flex items-center gap-2.5 px-5 py-3 rounded-xl bg-white/[0.03] border border-white/5">
                <span className="text-accent">{s.icon}</span>
                <div className="text-left">
                  <div className="text-xl font-bold text-foreground">{s.value}</div>
                  <div className="text-[11px] text-muted uppercase tracking-wider">{s.label}</div>
                </div>
              </div>
            ))}
          </motion.div>

          {/* CTAs */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.45 }} className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-2">
            <a href="#download" className="flex items-center gap-2 px-8 py-4 rounded-xl bg-accent text-slate-900 font-bold hover:brightness-110 transition-all shadow-xl shadow-accent/20 text-lg">
              <Download className="w-5 h-5" />
              Download & Run Locally
            </a>
            <a href="#samples" className="flex items-center gap-2 px-6 py-4 rounded-xl bg-white/[0.05] border border-white/10 text-foreground font-semibold hover:bg-white/[0.08] transition-all">
              <Play className="w-5 h-5" />
              More Samples
            </a>
          </motion.div>
        </div>
      </section>

      {/* Warning Banner */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-4 mb-12">
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground">This page is a static preview.</p>
            <p className="text-xs text-muted mt-1">
              Audio generation requires a local GPU backend (Apple Silicon or NVIDIA). Script generation also needs the backend for LLM routing and API key management. Download the repo to run fully.
            </p>
          </div>
        </div>
      </section>

      {/* Audio Samples */}
      <section id="samples" className="py-16 sm:py-20">
        <div className="max-w-3xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-10">
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">Hear It Yourself</h2>
            <p className="text-muted">Real episodes generated by Podcast Brain Pro. Zero editing.</p>
          </div>
          <div className="space-y-3">
            {SAMPLES.map((s) => (
              <MiniPlayer key={s.file} {...s} />
            ))}
          </div>
        </div>
      </section>

      {/* Use Cases */}
      <section className="py-16 sm:py-20 bg-white/[0.02]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-12">
            <div className="text-xs font-semibold text-accent uppercase tracking-wider mb-2">Capabilities</div>
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">Built For Everyone</h2>
            <p className="text-muted max-w-xl mx-auto">From classrooms to newsrooms — Podcast Brain Pro adapts to your workflow.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {USE_CASES.map((u, i) => (
              <motion.div
                key={u.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="rounded-xl border border-white/5 bg-white/[0.03] p-5 hover:border-accent/20 hover:bg-white/[0.05] transition-all"
              >
                <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center text-accent mb-3">
                  {u.icon}
                </div>
                <h3 className="font-semibold mb-1.5">{u.title}</h3>
                <p className="text-sm text-muted leading-relaxed">{u.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* App Preview */}
      <section className="py-16 sm:py-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-12">
            <div className="text-xs font-semibold text-accent uppercase tracking-wider mb-2">Preview</div>
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">Inside the App</h2>
            <p className="text-muted">Download to use these screens with full functionality.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-5">
            {/* Settings */}
            <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5 space-y-4">
              <div className="flex items-center gap-2 text-accent font-semibold">
                <Settings className="w-5 h-5" />
                Settings — API Keys
              </div>
              <div className="space-y-2.5">
                {[
                  { name: "Dialogram API Key", status: "Configured", color: "text-emerald-400" },
                  { name: "GitHub Models Token", status: "Configured", color: "text-emerald-400" },
                  { name: "Groq API Key", status: "Optional", color: "text-muted" },
                  { name: "Sarvam API Key", status: "Configured", color: "text-emerald-400" },
                  { name: "Tavily API Key", status: "Optional", color: "text-muted" },
                ].map((k) => (
                  <div key={k.name} className="flex items-center justify-between text-sm py-1.5 border-b border-white/5 last:border-0">
                    <span className="text-muted">{k.name}</span>
                    <span className={`text-xs ${k.color}`}>{k.status}</span>
                  </div>
                ))}
              </div>
              <div className="text-xs text-muted bg-white/[0.03] rounded-lg p-3 border border-white/5">
                <Key className="w-3.5 h-3.5 inline mr-1 text-accent" />
                Saved locally in <code className="text-foreground">user_config.json</code>. Never sent to our servers.
              </div>
            </div>

            {/* Architecture */}
            <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5 space-y-4">
              <div className="flex items-center gap-2 text-accent font-semibold">
                <Eye className="w-5 h-5" />
                System Architecture
              </div>
              <div className="space-y-2 text-sm">
                {[
                  { color: "bg-blue-500", text: "React Frontend (Next.js 14)", indent: 0 },
                  { color: "bg-purple-500", text: "FastAPI Backend (Python)", indent: 1 },
                  { color: "bg-amber-500", text: "Script Generation (LLM Chain)", indent: 2 },
                  { color: "bg-emerald-500", text: "VibeVoice TTS (Local GPU)", indent: 2 },
                  { color: "bg-orange-500", text: "Sarvam AI (Indic Languages)", indent: 2 },
                  { color: "bg-gray-500", text: "outputs/ — WAV + JSON + RSS", indent: 1 },
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-2" style={{ paddingLeft: `${item.indent * 16}px` }}>
                    <div className={`w-2 h-2 rounded-full ${item.color}`} />
                    <span className="text-muted text-xs">{item.text}</span>
                  </div>
                ))}
              </div>
              <div className="text-xs text-muted bg-white/[0.03] rounded-lg p-3 border border-white/5">
                <Cpu className="w-3.5 h-3.5 inline mr-1 text-accent" />
                Audio synthesis runs entirely on your machine. Cloud only for script LLMs.
              </div>
            </div>

            {/* Help */}
            <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5 space-y-4">
              <div className="flex items-center gap-2 text-accent font-semibold">
                <HelpCircle className="w-5 h-5" />
                Help & Setup Guide
              </div>
              <div className="space-y-3">
                {[
                  { step: "1", title: "Clone & install vibevoice", time: "~2 min" },
                  { step: "2", title: "Configure API keys", time: "~1 min" },
                  { step: "3", title: "Start backend", time: "~5 min" },
                  { step: "4", title: "Start frontend", time: "~1 min" },
                ].map((s) => (
                  <div key={s.step} className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-accent/10 text-accent text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                      {s.step}
                    </div>
                    <div>
                      <div className="text-sm">{s.title}</div>
                      <div className="text-xs text-muted">{s.time}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="text-xs text-muted bg-white/[0.03] rounded-lg p-3 border border-white/5">
                <BookOpen className="w-3.5 h-3.5 inline mr-1 text-accent" />
                Full docs at <code className="text-foreground">docs/SETUP.md</code>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-16 sm:py-20 bg-white/[0.02]">
        <div className="max-w-4xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-12">
            <div className="text-xs font-semibold text-accent uppercase tracking-wider mb-2">Workflow</div>
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">How It Works</h2>
            <p className="text-muted">Topic → Script → Audio. In minutes.</p>
          </div>
          <div className="space-y-5">
            {[
              { step: "01", title: "Enter a Topic", desc: "Type any subject. The AI researches and writes a natural, conversational script in ~30 seconds." },
              { step: "02", title: "Choose Format & Language", desc: "Monologue, interview, or panel. English or 10 Indian languages. The app picks the best TTS engine automatically." },
              { step: "03", title: "Generate Audio Locally", desc: "VibeVoice synthesizes studio-quality speech on your Apple Silicon Mac or NVIDIA GPU. No internet after first download." },
            ].map((s) => (
              <div key={s.step} className="flex gap-5 rounded-xl border border-white/5 bg-white/[0.03] p-6">
                <div className="text-3xl font-black text-accent/30 shrink-0">{s.step}</div>
                <div>
                  <h3 className="text-lg font-semibold mb-1.5">{s.title}</h3>
                  <p className="text-sm text-muted leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Download */}
      <section id="download" className="py-16 sm:py-24">
        <div className="max-w-4xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-12">
            <div className="text-xs font-semibold text-accent uppercase tracking-wider mb-2">Get Started</div>
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">Try It Yourself</h2>
            <p className="text-muted">Download, configure keys, and generate your first podcast in under 10 minutes.</p>
          </div>

          <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5 mb-8">
            <h3 className="font-semibold mb-3 flex items-center gap-2 text-sm">
              <Monitor className="w-4 h-4 text-accent" />
              Requirements
            </h3>
            <div className="grid sm:grid-cols-2 gap-2">
              {[
                "macOS Apple Silicon (M1-M4) or Linux/Windows + NVIDIA GPU",
                "Python 3.10+",
                "Node.js 18+",
                "~15 GB disk space for models",
                "At least one LLM API key (free tiers available)",
              ].map((r) => (
                <div key={r} className="flex items-start gap-2 text-sm text-muted">
                  <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  {r}
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            {SETUP_STEPS.map((s, i) => (
              <motion.div
                key={s.title}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-xl border border-white/5 bg-white/[0.03] p-5"
              >
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center text-accent">{s.icon}</div>
                  <h3 className="font-semibold text-sm">{s.title}</h3>
                </div>
                <pre className="bg-black/30 rounded-lg p-3 overflow-x-auto">
                  <code className="text-xs font-mono text-foreground/80 whitespace-pre">{s.code}</code>
                </pre>
              </motion.div>
            ))}
          </div>

          <div className="mt-10 text-center">
            <a href="https://github.com/niranjannie/podcast-brain-pro" target="_blank" className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-accent text-slate-900 font-bold hover:brightness-110 transition-all shadow-xl shadow-accent/20 text-lg">
              <Github className="w-5 h-5" />
              Clone from GitHub
              <ExternalLink className="w-4 h-4" />
            </a>
            <p className="text-xs text-muted mt-4">
              Full docs: <code className="text-foreground">docs/SETUP.md</code> · <code className="text-foreground">docs/API_KEYS.md</code> · <code className="text-foreground">docs/ARCHITECTURE.md</code>
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-muted">
            <Mic className="w-4 h-4" />
            Podcast Brain Pro — Open Source AI Podcast Factory
          </div>
          <div className="flex items-center gap-6 text-sm text-muted">
            <a href="https://github.com/niranjannie/podcast-brain-pro" target="_blank" className="hover:text-foreground transition-colors">GitHub</a>
            <a href="https://github.com/niranjannie/podcast-brain-pro/blob/main/docs/SETUP.md" target="_blank" className="hover:text-foreground transition-colors">Docs</a>
            <a href="https://github.com/niranjannie/podcast-brain-pro/blob/main/LICENSE" target="_blank" className="hover:text-foreground transition-colors">MIT License</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
