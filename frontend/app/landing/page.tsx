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
  Star,
  Clock,
  Wallet,
  Lock,
} from "lucide-react";

const PROMO_AUDIO = {
  title: "Hear Podcast Brain Pro in Action",
  subtitle: "AI-narrated product story",
  file: "/samples/podcast-brain-pro-promo.wav",
};

const SAMPLES = [
  {
    lang: "English",
    flag: "🇺🇸",
    title: "Interview — AI Future Discussion",
    file: "/samples/english-interview.wav",
    staticDuration: "5:12",
    format: "Interview",
    model: "Longform 1.5B",
  },
  {
    lang: "English",
    flag: "🇺🇸",
    title: "Panel — Technology Trends",
    file: "/samples/english-panel.wav",
    staticDuration: "3:42",
    format: "Panel",
    model: "Longform 1.5B",
  },
  {
    lang: "Hindi",
    flag: "🇮🇳",
    title: "Nation Building: India vs China",
    file: "/samples/hindi-nation-building.wav",
    staticDuration: "4:49",
    format: "Interview",
    model: "Sarvam Bulbul",
  },
  {
    lang: "Hindi",
    flag: "🇮🇳",
    title: "Delhi Air Pollution & Government",
    file: "/samples/hindi-delhi-air.wav",
    staticDuration: "4:04",
    format: "Panel",
    model: "Sarvam Bulbul",
  },
  {
    lang: "Kannada",
    flag: "🇮🇳",
    title: "Bangalore News Update",
    file: "/samples/kannada-bangalore-news.wav",
    staticDuration: "3:04",
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

const PAIN_POINTS = [
  {
    icon: <Clock className="w-5 h-5" />,
    title: "Hours of recording",
    desc: "One episode used to take an entire weekend.",
  },
  {
    icon: <Wallet className="w-5 h-5" />,
    title: "Expensive voice actors",
    desc: "Professional narration costs $100–500 per hour.",
  },
  {
    icon: <Mic className="w-5 h-5" />,
    title: "Studio equipment",
    desc: "Microphones, mixers, soundproofing... it adds up.",
  },
  {
    icon: <Lock className="w-5 h-5" />,
    title: "Locked into platforms",
    desc: "Cloud tools own your data and charge monthly.",
  },
];

const USE_CASES = [
  {
    icon: <BookOpen className="w-5 h-5" />,
    title: "Education",
    desc: "Turn lesson plans into multilingual audio. Students learn better when they can listen.",
  },
  {
    icon: <Radio className="w-5 h-5" />,
    title: "News & Journalism",
    desc: "Auto-generate audio briefings in regional languages. Reach audiences who prefer to listen.",
  },
  {
    icon: <Mic className="w-5 h-5" />,
    title: "Content Creators",
    desc: "Repurpose blog posts into podcasts. Batch-produce episodes without a recording setup.",
  },
  {
    icon: <Cpu className="w-5 h-5" />,
    title: "Enterprise",
    desc: "Training audio in 10 languages. Onboarding podcasts. Product explainers at scale.",
  },
  {
    icon: <Volume2 className="w-5 h-5" />,
    title: "Accessibility",
    desc: "Convert documents to audio. Make content available to visually impaired audiences.",
  },
  {
    icon: <Headphones className="w-5 h-5" />,
    title: "Developers",
    desc: "Build voice-enabled apps, custom assistants, CMS audio integrations.",
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

const FAQ = [
  {
    q: "Is it really free?",
    a: "Yes. Podcast Brain Pro is MIT licensed and completely free. The only costs are your own compute (electricity) and optional LLM API calls for script generation.",
  },
  {
    q: "Do I need a GPU?",
    a: "Audio synthesis runs on Apple Silicon (M1-M4) or NVIDIA GPUs. For script generation, you only need an internet connection and a free LLM API key.",
  },
  {
    q: "What languages are supported?",
    a: "English plus 10 Indian languages: Hindi, Kannada, Tamil, Telugu, Marathi, Bengali, Gujarati, Malayalam, Punjabi, and Assamese.",
  },
  {
    q: "How does the audio quality compare to ElevenLabs?",
    a: "Open-source TTS models trade some quality for being free and local. The English longform model sounds very natural. Indic languages use Sarvam AI's commercial-grade API.",
  },
  {
    q: "Can I use this commercially?",
    a: "Absolutely. MIT license means you can use, modify, and sell it without restrictions.",
  },
  {
    q: "How long does setup take?",
    a: "About 10 minutes if you have Python and Node installed. Downloading the TTS models takes the longest (~5 min on fast internet).",
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
    if (audio.readyState >= 1) setDuration(audio.duration || 0);
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

      <div className="space-y-1 select-none">
        <div
          ref={barRef}
          className="h-2 w-full rounded-full bg-surface-3 cursor-pointer overflow-hidden"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
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

function MiniPlayer({ file, title, lang, flag, staticDuration, format, model }: any) {
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [dragging, setDragging] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const barRef = useRef<HTMLDivElement>(null);

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
      } catch {}
      setLoading(false);
    }
  };

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onEnd = () => setPlaying(false);
    const onPause = () => setPlaying(false);
    const onPlay = () => { setPlaying(true); setLoading(false); };
    const onLoaded = () => setDuration(audio.duration || 0);
    const onTime = () => {
      if (!dragging) {
        setCurrentTime(audio.currentTime);
        setProgress(audio.duration ? (audio.currentTime / audio.duration) * 100 : 0);
      }
    };
    if (audio.readyState >= 1) setDuration(audio.duration || 0);
    audio.addEventListener("ended", onEnd);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("loadedmetadata", onLoaded);
    audio.addEventListener("timeupdate", onTime);
    return () => {
      audio.removeEventListener("ended", onEnd);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("loadedmetadata", onLoaded);
      audio.removeEventListener("timeupdate", onTime);
    };
  }, [dragging]);

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

  useEffect(() => {
    if (!dragging) return;
    const up = () => setDragging(false);
    window.addEventListener("mouseup", up);
    return () => window.removeEventListener("mouseup", up);
  }, [dragging]);

  return (
    <div className="rounded-xl border border-border bg-surface-2 p-4 hover:border-accent/30 transition-colors">
      <div className="flex items-center gap-4">
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
        <div className="text-xs text-muted font-mono shrink-0">
          {formatTime(currentTime)} / {duration > 0 ? formatTime(duration) : staticDuration}
        </div>
      </div>
      <div className="mt-3 select-none">
        <div
          ref={barRef}
          className="h-1.5 w-full rounded-full bg-surface-3 cursor-pointer overflow-hidden"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
        >
          <div
            className="h-full bg-accent rounded-full"
            style={{ width: `${progress}%`, transition: dragging ? "none" : "width 0.1s linear" }}
          />
        </div>
      </div>
      <audio ref={audioRef} src={file} preload="metadata" />
    </div>
  );
}

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-white/5 rounded-xl bg-white/[0.02] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-white/[0.02] transition-colors"
      >
        <span className="font-medium text-sm">{q}</span>
        <span className={`text-muted transition-transform ${open ? "rotate-180" : ""}`}>▼</span>
      </button>
      {open && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          className="px-4 pb-4 text-sm text-muted leading-relaxed"
        >
          {a}
        </motion.div>
      )}
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
            <a href="https://github.com/niranjannie/podcast-brain-pro" target="_blank" className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-slate-900 text-sm font-semibold hover:brightness-110 transition-all">
              <Star className="w-4 h-4" />
              <span className="hidden sm:inline">Star on GitHub</span>
            </a>
          </div>
        </div>
      </nav>

      {/* Hero — Story-Driven */}
      <section className="relative overflow-hidden pt-16 pb-20 sm:pt-24 sm:pb-32">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-accent/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="max-w-4xl mx-auto px-4 sm:px-6 relative">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }} className="text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5" />
              Open Source · MIT License · 100% Free
            </div>

            <h1 className="text-4xl sm:text-6xl font-black tracking-tight leading-[1.1]">
              Your ideas deserve to be{" "}
              <span className="bg-gradient-to-r from-accent via-indigo-400 to-purple-400 bg-clip-text text-transparent">
                heard
              </span>
            </h1>

            <p className="text-lg sm:text-xl text-muted max-w-2xl mx-auto leading-relaxed">
              Podcast Brain Pro turns any topic into a studio-quality podcast — locally, in any language, with AI.
              No studio. No subscriptions. Just your machine and an idea.
            </p>

            {/* Promo Audio Player */}
            <div className="max-w-xl mx-auto pt-4">
              <div className="flex items-center gap-2 mb-3 justify-center">
                <Music className="w-4 h-4 text-accent" />
                <span className="text-xs font-semibold text-accent uppercase tracking-wider">Hear It In Action</span>
                <span className="text-xs text-muted">— AI voice clone narrating the story</span>
              </div>
              <AudioPlayer src={PROMO_AUDIO.file} title={PROMO_AUDIO.title} subtitle={PROMO_AUDIO.subtitle} showWave />
            </div>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
              <a href="https://github.com/niranjannie/podcast-brain-pro" target="_blank" className="flex items-center gap-2 px-8 py-4 rounded-xl bg-accent text-slate-900 font-bold hover:brightness-110 transition-all shadow-xl shadow-accent/20 text-lg">
                <Star className="w-5 h-5" />
                Star on GitHub
              </a>
              <a href="#samples" className="flex items-center gap-2 px-6 py-4 rounded-xl bg-white/[0.05] border border-white/10 text-foreground font-semibold hover:bg-white/[0.08] transition-all">
                <Play className="w-5 h-5" />
                Hear More Samples
              </a>
            </div>

            {/* Stats */}
            <div className="flex flex-wrap justify-center gap-4 sm:gap-6 pt-6">
              {STATS.map((s) => (
                <div key={s.label} className="flex items-center gap-2.5 px-5 py-3 rounded-xl bg-white/[0.03] border border-white/5">
                  <span className="text-accent">{s.icon}</span>
                  <div className="text-left">
                    <div className="text-xl font-bold text-foreground">{s.value}</div>
                    <div className="text-[11px] text-muted uppercase tracking-wider">{s.label}</div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* Prominent Static Preview Banner */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 -mt-8 mb-8">
        <div className="rounded-xl border border-accent/20 bg-accent/5 p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center text-accent shrink-0">
            <Download className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-foreground">
              This page is a static preview with audio samples.
            </p>
            <p className="text-xs text-muted mt-1">
              The full app with podcast generation runs at <code className="text-accent">localhost:3000</code> after you clone the repo and set it up locally. It takes about 10 minutes.
            </p>
          </div>
          <a href="https://github.com/niranjannie/podcast-brain-pro" target="_blank" className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-slate-900 text-sm font-semibold hover:brightness-110 transition-all shrink-0">
            <Github className="w-4 h-4" />
            Clone & Setup
          </a>
        </div>
      </section>

      {/* Pain Points */}
      <section className="py-16 sm:py-20 bg-white/[0.02]">
        <div className="max-w-4xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-12">
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">Creating a podcast used to be hard</h2>
            <p className="text-muted">Most ideas never become podcasts because the barrier is too high.</p>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            {PAIN_POINTS.map((p, i) => (
              <motion.div
                key={p.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex items-start gap-4 p-5 rounded-xl border border-white/5 bg-white/[0.03]"
              >
                <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center text-red-400 shrink-0">
                  {p.icon}
                </div>
                <div>
                  <h3 className="font-semibold mb-1">{p.title}</h3>
                  <p className="text-sm text-muted">{p.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Solution — How It Works */}
      <section className="py-16 sm:py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-12">
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">Now it takes 30 seconds</h2>
            <p className="text-muted">Topic → Script → Audio. One click each.</p>
          </div>
          <div className="space-y-5">
            {[
              { step: "01", title: "Type a Topic", desc: "Enter any subject — \"The future of quantum computing\" or \"India's space program.\" The AI researches it using web search and writes a natural, conversational script." },
              { step: "02", title: "Choose Your Format", desc: "Monologue for storytelling. Interview for two perspectives. Panel for a lively discussion with interruptions and disagreements." },
              { step: "03", title: "Generate Audio Locally", desc: "VibeVoice synthesizes speech on your Apple Silicon Mac or NVIDIA GPU. For Indian languages, Sarvam AI delivers native-quality narration. No cloud. No fees." },
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

      {/* App Preview — Actual localhost:3000 UI */}
      <section className="py-16 sm:py-20 bg-white/[0.02]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-10">
            <div className="text-xs font-semibold text-accent uppercase tracking-wider mb-2">App Preview</div>
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">What You Get After Setup</h2>
            <p className="text-muted">This is the actual interface that runs at <code className="text-accent">localhost:3000</code> once you install locally.</p>
          </div>
          <div className="grid md:grid-cols-2 gap-5">
            <div className="rounded-xl border border-white/5 bg-white/[0.03] overflow-hidden">
              <img src="/screenshots/app-main.png" alt="Main app interface with episode configuration" className="w-full" />
              <div className="p-4">
                <div className="text-sm font-semibold">Episode Configuration</div>
                <div className="text-xs text-muted mt-1">Enter a topic, choose format, pick language, and generate.</div>
              </div>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.03] overflow-hidden">
              <img src="/screenshots/app-settings.png" alt="Settings modal with API key configuration" className="w-full" />
              <div className="p-4">
                <div className="text-sm font-semibold">Settings & API Keys</div>
                <div className="text-xs text-muted mt-1">Configure LLM providers and TTS engines. Saved locally.</div>
              </div>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.03] overflow-hidden">
              <img src="/screenshots/app-help.png" alt="Help modal with setup guide" className="w-full" />
              <div className="p-4">
                <div className="text-sm font-semibold">Built-in Setup Guide</div>
                <div className="text-xs text-muted mt-1">Step-by-step help right inside the app.</div>
              </div>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.03] overflow-hidden">
              <img src="/screenshots/app-fullpage.png" alt="Full app page showing system status and all controls" className="w-full" />
              <div className="p-4">
                <div className="text-sm font-semibold">System Status & Controls</div>
                <div className="text-xs text-muted mt-1">Monitor model cache, choose voice cast, and track generation.</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Architecture */}
      <section className="py-16 sm:py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-10">
            <div className="text-xs font-semibold text-accent uppercase tracking-wider mb-2">Architecture</div>
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">How It Works Under the Hood</h2>
            <p className="text-muted">Fully open source. Every layer is yours to inspect and modify.</p>
          </div>
          <div className="rounded-xl border border-white/5 bg-white/[0.03] p-6 sm:p-8">
            <img src="/architecture.svg" alt="System architecture diagram" className="w-full max-w-2xl mx-auto" />
            <div className="mt-8 grid sm:grid-cols-2 gap-4 text-sm">
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                <div>
                  <span className="font-medium text-foreground">React Frontend</span>
                  <span className="text-muted"> — Next.js 14 + Tailwind CSS</span>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 rounded-full bg-purple-500 mt-1.5 shrink-0" />
                <div>
                  <span className="font-medium text-foreground">FastAPI Backend</span>
                  <span className="text-muted"> — Python, async endpoints</span>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                <div>
                  <span className="font-medium text-foreground">Script Generation</span>
                  <span className="text-muted"> — LLM chain + Tavily web search</span>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                <div>
                  <span className="font-medium text-foreground">Local TTS</span>
                  <span className="text-muted"> — VibeVoice 1.5B (PyTorch)</span>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 rounded-full bg-orange-500 mt-1.5 shrink-0" />
                <div>
                  <span className="font-medium text-foreground">Indic TTS</span>
                  <span className="text-muted"> — Sarvam AI Bulbul API</span>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-2 h-2 rounded-full bg-gray-500 mt-1.5 shrink-0" />
                <div>
                  <span className="font-medium text-foreground">Output</span>
                  <span className="text-muted"> — WAV + JSON + RSS feed</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Audio Samples */}
      <section id="samples" className="py-16 sm:py-20 bg-white/[0.02]">
        <div className="max-w-3xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-10">
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">Hear It Yourself</h2>
            <p className="text-muted">Real episodes generated from a single sentence. Zero editing.</p>
          </div>
          <div className="space-y-3">
            {SAMPLES.map((s) => (
              <MiniPlayer key={s.file} {...s} />
            ))}
          </div>
        </div>
      </section>

      {/* Use Cases */}
      <section className="py-16 sm:py-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-12">
            <div className="text-xs font-semibold text-accent uppercase tracking-wider mb-2">Who It's For</div>
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">Built For Everyone</h2>
            <p className="text-muted max-w-xl mx-auto">From classrooms to newsrooms — if you have something to say, this helps you say it.</p>
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

      {/* Tech Stack Preview */}
      <section className="py-16 sm:py-20 bg-white/[0.02]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-12">
            <div className="text-xs font-semibold text-accent uppercase tracking-wider mb-2">Open Source</div>
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">Fully Transparent</h2>
            <p className="text-muted">Every line of code is yours to read, modify, and build on.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-5">
            <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5 space-y-4">
              <div className="flex items-center gap-2 text-accent font-semibold">
                <Settings className="w-5 h-5" />
                Your Keys, Your Control
              </div>
              <div className="space-y-2.5 text-sm">
                {["Dialogram API","GitHub Models","Groq (optional)","Sarvam API","Tavily (optional)"].map((k) => (
                  <div key={k} className="flex items-center justify-between py-1.5 border-b border-white/5 last:border-0">
                    <span className="text-muted">{k}</span>
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted">Saved locally. Never leaves your machine.</p>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5 space-y-4">
              <div className="flex items-center gap-2 text-accent font-semibold">
                <Eye className="w-5 h-5" />
                Architecture
              </div>
              <div className="space-y-2 text-sm">
                {[
                  { color: "bg-blue-500", text: "React Frontend (Next.js 14)" },
                  { color: "bg-purple-500", text: "FastAPI Backend (Python)" },
                  { color: "bg-amber-500", text: "Script Generation (LLM Chain)" },
                  { color: "bg-emerald-500", text: "VibeVoice TTS (Local GPU)" },
                  { color: "bg-orange-500", text: "Sarvam AI (Indic Languages)" },
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${item.color}`} />
                    <span className="text-muted text-xs">{item.text}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted">Audio synthesis runs locally. Cloud only for script LLMs.</p>
            </div>
            <div className="rounded-xl border border-white/5 bg-white/[0.03] p-5 space-y-4">
              <div className="flex items-center gap-2 text-accent font-semibold">
                <HelpCircle className="w-5 h-5" />
                Setup in 10 Minutes
              </div>
              <div className="space-y-3">
                {[
                  { step: "1", title: "Clone & install", time: "~2 min" },
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
              <p className="text-xs text-muted">Full docs in <code className="text-foreground">docs/SETUP.md</code></p>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16 sm:py-20">
        <div className="max-w-3xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-10">
            <h2 className="text-2xl sm:text-3xl font-bold mb-3">Questions? Answered.</h2>
          </div>
          <div className="space-y-3">
            {FAQ.map((f) => (
              <FaqItem key={f.q} q={f.q} a={f.a} />
            ))}
          </div>
        </div>
      </section>

      {/* CTA Banner */}
      <section className="py-16 sm:py-24">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 text-center space-y-8">
          <h2 className="text-3xl sm:text-5xl font-black tracking-tight">
            Your voice doesn't need a studio.
            <br />
            <span className="bg-gradient-to-r from-accent via-indigo-400 to-purple-400 bg-clip-text text-transparent">
              It just needs an idea.
            </span>
          </h2>
          <p className="text-lg text-muted max-w-xl mx-auto">
            Join the open-source community. Star the repo, try it locally, and bring your ideas to life.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a href="https://github.com/niranjannie/podcast-brain-pro" target="_blank" className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-accent text-slate-900 font-bold hover:brightness-110 transition-all shadow-xl shadow-accent/20 text-lg">
              <Star className="w-5 h-5" />
              Star on GitHub
              <ExternalLink className="w-4 h-4" />
            </a>
            <a href="https://github.com/niranjannie/podcast-brain-pro/blob/main/docs/SETUP.md" target="_blank" className="inline-flex items-center gap-2 px-6 py-4 rounded-xl bg-white/[0.05] border border-white/10 text-foreground font-semibold hover:bg-white/[0.08] transition-all">
              <BookOpen className="w-5 h-5" />
              Read the Docs
            </a>
          </div>
          <p className="text-xs text-muted">
            MIT Licensed · Free forever · Community driven
          </p>
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
