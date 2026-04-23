# Podcast Brain Pro — Visibility & Growth Playbook

> Your repo: `https://github.com/niranjannie/podcast-brain-pro`  
> Your landing page: `https://frontend-chi-virid-53.vercel.app/landing`

---

## Phase 1: Foundation (Do This First)

### 1. GitHub Repo Polish

Your README is your storefront. Most visitors will land on GitHub first, not your landing page.

**README must-haves:**
- [ ] **Hero GIF/video** at the top — 10-15 seconds showing "type topic → get podcast" in one loop
- [ ] **One-liner** above the fold: *"Turn any topic into a studio-quality podcast — locally, in any language, with AI."*
- [ ] **Badges**: Build (passing), License (MIT), Stars, Python version, Node version
- [ ] **30-second quickstart** — copy-paste 3 commands to run
- [ ] **Audio embeds** — link to your landing page samples so people can hear before they install
- [ ] **Screenshot grid** — Settings UI, generated script, audio player, RSS feed
- [ ] **"Why this exists"** section — the story from your script (2-3 paragraphs)
- [ ] **Comparison table** — vs ElevenLabs, vs NotebookLM, vs Descript (highlight: free, local, open-source)
- [ ] **Contributing.md** link + `good first issue` labels

**Tools for badges:** [shields.io](https://shields.io)

### 2. Landing Page Conversion Checklist

Current landing page is good. To make it convert better:

- [ ] **Lead with emotion, not features** — Your script's "Imagine this..." hook should be the first thing people read
- [ ] **Social proof** — "Join X creators" or GitHub star count badge
- [ ] **One clear CTA above the fold** — "Star on GitHub" (primary) + "Try the Demo" (secondary)
- [ ] **Remove friction words** — Replace "This page is a static preview" with something positive like "Hear live samples below — clone to generate your own"
- [ ] **Add a "Star on GitHub" button** in the hero (not just "Download")
- [ ] **FAQ section** — addresses "Is it really free?", "Do I need a GPU?", "What languages?"
- [ ] **Newsletter signup** — Even a simple "Get notified of new features" form (use Buttondown or ConvertKit)

---

## Phase 2: Launch Channels

### Hacker News — "Show HN"

**Best time to post**: Tuesday–Thursday, 7–10 AM US Pacific Time (catches both US West Coast morning and East Coast lunch)

**Title options** (A/B test mentally):
- `Show HN: Podcast Brain Pro – Open-source AI podcast factory, runs locally`
- `Show HN: I built an open-source podcast generator that speaks 10 languages`
- `Show HN: Turn any topic into a podcast – open source, local, zero cloud fees`

**Body template** (keep it under 200 words):

```
I spent weekends recording, re-recording, and editing podcasts. So I built Podcast Brain Pro — an open-source AI podcast factory that runs entirely on your machine.

What it does:
• Type a topic → AI researches and writes a natural script
• Choose format: monologue, interview, or panel discussion
• Generate studio-quality audio locally (Apple Silicon / NVIDIA)
• Supports English + 10 Indian languages
• Outputs WAV + RSS feed + metadata JSON
• Zero cloud fees, zero subscriptions, fully MIT-licensed

Tech stack: FastAPI + PyTorch (VibeVoice TTS) + Next.js + Sarvam AI for Indic languages.

Live samples: https://frontend-chi-virid-53.vercel.app/landing
Repo: https://github.com/niranjannie/podcast-brain-pro

Would love feedback, especially on the audio quality and script generation. Happy to answer questions!
```

**HN tips:**
- Post the GitHub repo URL directly (not the landing page). HN trusts GitHub links more.
- Add a first comment yourself explaining the motivation + inviting questions.
- Reply to every comment within the first 2 hours. Engagement in the first hour determines ranking.
- Don't ask friends to upvote. HN detects voting rings. Organic engagement only.

---

### Reddit

**Subreddits to target** (post to one every 3-4 days, not all at once):

| Subreddit | Angle | Best Day/Time |
|-----------|-------|---------------|
| r/selfhosted | "Local AI podcast generator — no cloud, no subscriptions" | Weekend mornings |
| r/opensource | "I open-sourced my podcast generator — 10 languages, local GPU" | Weekday afternoons |
| r/MachineLearning | "Local TTS pipeline for multilingual podcasts — VibeVoice + Sarvam" | Weekday mornings |
| r/LocalLLaMA | "Fully local podcast generation — scripts + audio on your machine" | Any time |
| r/podcasting | "I built an AI tool that generates podcast episodes from a topic" | Weekday evenings |
| r/india | "Open-source podcast generator that speaks Hindi, Kannada, and 8 more Indian languages" | Weekend mornings IST |
| r/webdev | "Built a full-stack AI podcast factory — FastAPI + Next.js + local TTS" | Weekday afternoons |
| r/SideProject | "Weekend project: AI podcast generator that runs on my MacBook" | Weekend |

**Reddit post template** (adapt per subreddit):

```
[PROJECT] I built an open-source AI podcast generator that runs entirely on your machine

For the past few months, I've been obsessed with a simple question: what if creating a podcast was as easy as typing a sentence?

I spent entire weekends recording, editing, fixing mistakes. By the time one episode was done, I was exhausted. So I built **Podcast Brain Pro**.

**What it does:**
- Type any topic → AI writes a researched, natural script
- Choose format: monologue, interview, or panel
- Generate studio-quality audio locally on Apple Silicon / NVIDIA
- English + 10 Indian languages (Hindi, Kannada, Tamil, etc.)
- Zero cloud fees. Zero subscriptions. MIT licensed.

**Live demo (hear samples):** https://frontend-chi-virid-53.vercel.app/landing
**GitHub:** https://github.com/niranjannie/podcast-brain-pro

The audio is generated using VibeVoice (local PyTorch) and Sarvam AI for Indic languages. Scripts are powered by open-source LLMs.

Would love your thoughts — especially on the audio quality!
```

**Reddit rules:**
- Read each subreddit's rules before posting
- Don't post the same text to multiple subreddits simultaneously
- Engage genuinely in comments — answer questions, don't just drop links
- Cross-post only after the first post has traction (3+ days later)

---

### Product Hunt

**Launch checklist:**
- [ ] Create a Product Hunt account
- [ ] Prepare 3-5 GIFs/screenshots (600x400 or 1270x760)
- [ ] Write a tagline: *"Turn any topic into a podcast — locally, in any language"*
- [ ] Prepare maker comment: your personal story (use your script!)
- [ ] Line up 5-10 people to upvote/comment in the first hour (friends, colleagues)
- [ ] Launch on Tuesday at 12:01 AM PT (resets the daily leaderboard)

---

### Dev.to / Hashnode / Medium

Write **3 articles** over 3 weeks:

1. **"I Built an Open-Source Podcast Generator — Here's How"** — Technical deep dive. Walk through the architecture. Include code snippets. End with a CTA to star the repo.
2. **"Generating Multilingual Podcasts with Local AI"** — Focus on the TTS pipeline, VibeVoice, Sarvam integration. Target r/MachineLearning and HN.
3. **"From Idea to Podcast in 30 Seconds"** — Story-driven. Use your script as the backbone. Target general developer audience.

**CTA at the end of every article:**
> "If this sounds useful, give us a star on GitHub — it helps more than you know: [github.com/niranjannie/podcast-brain-pro](https://github.com/niranjannie/podcast-brain-pro)"

---

## Phase 3: Ongoing Growth

### Twitter/X Strategy

**Content mix (3-4 tweets/week):**
- **Demo videos** — Screen recording of "type topic → generate podcast" (15-30 seconds)
- **Before/after** — "What used to take 6 hours, now takes 30 seconds"
- **Language showcases** — "Here's a podcast in Kannada, generated from one sentence"
- **Behind the scenes** — "How VibeVoice TTS works under the hood"
- **User testimonials** — Even if it's just friends using it

**Pinned tweet:** Your best demo video + GitHub link

**Hashtags:** #OpenSource #AI #Podcast #TextToSpeech #IndicLanguages #BuildInPublic

### YouTube / TikTok

**Video ideas:**
- "I generated a podcast in 30 seconds using AI (completely free)"
- "This open-source tool generates podcasts in 10 languages"
- "From text to podcast: a full tutorial"
- Shorts: Side-by-side "Manual podcast creation vs AI podcast creation"

### Newsletters & Communities

Submit to:
- [Python Weekly](https://pythonweekly.com)
- [JavaScript Weekly](https://javascriptweekly.com)
- [Hacker Newsletter](https://hackernewsletter.com)
- [AI Engineer](https://ai.engineer)
- [Indie Hackers](https://indiehackers.com)
- [Awesome Selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) — PR your project

### Discord / Slack Communities

Join and contribute first, then share:
- MLOps Community Discord
- Latent Space Discord
- AI Engineer Discord
- LocalLLaMA Discord
- Indian tech communities (IndiDev, etc.)

**Rule: Help 10 times before you share once.**

---

## Phase 4: Retention & Loop

### GitHub Star Retargeting

Once you hit 50+ stars:
1. Use [GitHub Star Search](https://github.com/search) to find who starred similar projects
2. Look at repos your stargazers also starred — those are your next targets
3. Reach out to active contributors with personalized messages

### Milestone Marketing

Celebrate every milestone publicly:
- 100 stars → Twitter thread + Reddit update post
- 500 stars → Blog post: "What I learned from 500 stars"
- 1000 stars → Giveaway, merch, or feature announcement

### Public Roadmap

Create a GitHub Project board with:
- Upcoming features (Docker support, more languages, web UI improvements)
- "Good first issue" items for new contributors
- Community-requested features

---

## Quick-Start Action Plan (This Week)

| Day | Action |
|-----|--------|
| **Today** | Polish README with hero GIF + badges + quickstart |
| **Day 2** | Post to r/selfhosted |
| **Day 3** | Write Dev.to article #1 |
| **Day 4** | Post "Show HN" (Tuesday–Thursday, 7–10 AM PT) |
| **Day 5** | Post to r/opensource |
| **Day 6** | Create Twitter account, pin demo video tweet |
| **Day 7** | Post to r/LocalLLaMA + engage in all comment threads |

---

## Assets Checklist

- [ ] Hero GIF (10-15s, showing topic → script → audio)
- [ ] Screenshots (Settings, Script preview, Audio player, RSS feed)
- [ ] Demo video (60-90s, with your voiceover script)
- [ ] Logo/avatar (consistent across GitHub, Twitter, Product Hunt)
- [ ] One-liner/tagline
- [ ] FAQ (5-7 questions)
- [ ] Contributing guide
- [ ] Code of Conduct
- [ ] Issue templates (bug report, feature request)

---

*Last updated: April 2026*
