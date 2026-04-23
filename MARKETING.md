# Podcast Brain Pro — Realistic GitHub Visibility Plan

> Landing: https://frontend-chi-virid-53.vercel.app/landing  
> Repo: https://github.com/niranjannie/podcast-brain-pro

---

## What Actually Works for GitHub Stars

Based on research from projects that went from 0 → 1000+ stars, here's what actually moves the needle:

| Tactic | Effort | Impact | Do It? |
|--------|--------|--------|--------|
| Polished README with GIF | 2-3 hrs | **High** | ✅ Must |
| Hacker News "Show HN" | 30 min | **High** | ✅ Must |
| Reddit posts (2-3 subs) | 1 hr total | **Medium-High** | ✅ Do |
| Dev.to / Hashnode article | 3-4 hrs | **Medium** | ✅ Do 1 |
| Product Hunt launch | 2-3 hrs | **Medium** | ✅ Do |
| Awesome Selfhosted PR | 15 min | **Medium** | ✅ Easy win |
| Twitter/X account | 1 hr/week | **Low-Medium** | ⚠️ Optional |
| YouTube / TikTok | 5+ hrs each | **Low** for code | ❌ Skip |
| Paid ads | $$$ | **Low** for OSS | ❌ Skip |

---

## Week 1: Foundation (Do This First)

### 1. README That Converts (2-3 hours)

Your README is 80% of the battle. Most people star without ever running the code.

**Top section (above the fold):**
```
# Podcast Brain Pro

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/niranjannie/podcast-brain-pro/blob/main/LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node 18+](https://img.shields.io/badge/node-18+-blue.svg)](https://nodejs.org/)

> Turn any topic into a studio-quality podcast — locally, in any language, with AI.

[🎧 Live Samples](https://frontend-chi-virid-53.vercel.app/landing) · [📖 Docs](https://github.com/niranjannie/podcast-brain-pro/blob/main/docs/SETUP.md) · [⭐ Star](https://github.com/niranjannie/podcast-brain-pro)

[HERO GIF HERE — 10 seconds showing topic → script → audio]
```

**Must-include sections:**
1. **One-line description** (what it does, who it's for)
2. **30-second quickstart** — 3 copy-paste commands
3. **Live audio samples link** — your landing page
4. **Screenshot grid** — 3-4 images of UI + generated output
5. **"Why I built this"** — 2-3 paragraphs (use your script)
6. **Comparison** — vs ElevenLabs (paid/cloud) vs NotebookLM (no audio)
7. **Features list** — bullet points, not paragraphs
8. **Requirements** — Mac M1+ or NVIDIA GPU
9. **Contributing** — link to CONTRIBUTING.md

**Badges:** [shields.io](https://shields.io) — License, Python version, Node version, Build status

### 2. Swap Landing Page (30 min)

Replace `frontend/app/landing/page.tsx` with `page-conversion.tsx` content. It has:
- Emotional hero ("Your ideas deserve to be heard")
- Pain points section
- Draggable audio samples
- FAQ accordion
- "Star on GitHub" CTAs everywhere

### 3. One Dev.to Article (3-4 hours)

Write ONE article: **"I Built an Open-Source Podcast Generator — Here's How"**

Structure:
- Hook: "I spent weekends recording podcasts. Now it takes 30 seconds."
- The problem (your script, condensed)
- The solution (architecture diagram)
- Technical deep dive (TTS pipeline, script generation)
- Live samples link
- CTA: "Star the repo if you find it useful"

Post to: Dev.to + cross-post to Hashnode

---

## Week 2: Launch

### Day 1: Hacker News "Show HN"

**Best time:** Tuesday or Thursday, 7–10 AM Pacific

**Title:**
```
Show HN: Podcast Brain Pro – Open-source AI podcast factory, runs locally
```

**Body:**
```
I spent weekends recording, re-recording, and editing podcasts. So I built Podcast Brain Pro — an open-source AI podcast factory that runs entirely on your machine.

What it does:
• Type a topic → AI researches and writes a natural script
• Choose format: monologue, interview, or panel discussion
• Generate studio-quality audio locally (Apple Silicon / NVIDIA)
• English + 10 Indian languages
• Outputs WAV + RSS feed + metadata JSON
• Zero cloud fees, MIT licensed

Tech: FastAPI + PyTorch (VibeVoice TTS) + Next.js + Sarvam AI for Indic languages.

Live samples: https://frontend-chi-virid-53.vercel.app/landing
GitHub: https://github.com/niranjannie/podcast-brain-pro

Would love feedback on the audio quality. Happy to answer questions!
```

**Immediately after posting, add this comment:**
```
A bit more context:

Audio synthesis is entirely local using VibeVoice (1.5B param PyTorch model, ~2GB). For Indian languages it uses Sarvam AI's Bulbul API.

Script generation uses an LLM chain with Tavily web search — so "quantum computing" actually gets researched before scripting, not hallucinated.

The panel mode is my favorite. It generates 2-3 speakers with distinct personalities who interrupt and disagree. Setup takes ~10 min if you have Apple Silicon or NVIDIA.
```

**Rules:**
- Reply to every comment in first 2 hours
- Don't ask friends to upvote (HN detects rings)
- Be humble. HN hates hype.

### Day 3: Reddit r/selfhosted

**Title:** `[Showcase] Open-source AI podcast generator that runs entirely locally — no cloud, no subscriptions`

**Body:** Use template from `docs/REDDIT_POSTS.md`

### Day 5: Reddit r/opensource

**Title:** `[Project] Podcast Brain Pro — open-source AI podcast generator, 10 languages, runs locally`

**Body:** Use template from `docs/REDDIT_POSTS.md`

### Day 7: Awesome Selfhosted PR

Submit a PR to https://github.com/awesome-selfhosted/awesome-selfhosted

This is an easy win — curated lists drive consistent long-term traffic.

---

## Week 3: Product Hunt

**Why:** Product Hunt drives sustained traffic, not just a spike.

**Prep:**
- 3-5 screenshots (600x400 or 1270x760)
- Tagline: "Turn any topic into a podcast — locally, in any language"
- Maker comment: your personal story (2-3 paragraphs from your script)

**Launch day:**
- Tuesday at 12:01 AM PT (resets daily leaderboard)
- Ask 5-10 developer friends to upvote/comment in first hour
- Reply to every comment

---

## Ongoing (1 hour/week)

### Twitter/X (Optional)

If you want to do social, keep it minimal:
- 2-3 tweets/week
- Mix: demo GIFs, language showcases, "how it works" threads
- Hashtags: #OpenSource #BuildInPublic #AI #IndicLanguages

### Engage in Communities

Spend 30 min/week in:
- HN comment sections on AI/audio posts (add value, then mention your project if relevant)
- r/MachineLearning, r/LocalLLaMA (help first, share second)
- Dev.to (comment on related articles)

**Rule:** Help 5 times, promote 1 time.

---

## Milestones to Celebrate

| Stars | Action |
|-------|--------|
| 50 | Tweet about it |
| 100 | Reddit "update" post + blog reflection |
| 250 | HN "What I learned" post |
| 500 | Product Hunt re-launch with new features |
| 1000 | Community giveaway or merch |

---

## What NOT to Do

❌ Don't spam every subreddit at once — space posts 2-3 days apart  
❌ Don't buy stars or use star-exchange sites — GitHub detects this  
❌ Don't ignore issues/PRs — responsiveness is the #1 factor in retention  
❌ Don't launch on holidays or during major tech events  
❌ Don't make a video — for code projects, written content converts better

---

## Quick Checklist

- [ ] README has hero GIF + badges + 30-sec quickstart
- [ ] Landing page swapped to conversion version
- [ ] One Dev.to article published
- [ ] HN "Show HN" posted (Tue/Thu morning PT)
- [ ] 2 Reddit posts (r/selfhosted, r/opensource)
- [ ] Awesome Selfhosted PR submitted
- [ ] Product Hunt launched

---

*Realistic timeline: 3 weeks to 100+ stars if you execute consistently.*
