# Hacker News "Show HN" Launch Kit

> Repo: https://github.com/niranjannie/podcast-brain-pro  
> Landing: https://frontend-chi-virid-53.vercel.app/landing

---

## The Post

**URL to submit:** `https://github.com/niranjannie/podcast-brain-pro`

*(HN prefers direct GitHub links over landing pages. The repo is the destination.)*

**Title:** (Pick ONE — no A/B testing on HN, choose the best)

```
Show HN: Podcast Brain Pro – Open-source AI podcast factory, runs locally
```

**Alternative titles** (if the above doesn't feel right):
```
Show HN: Turn any topic into a podcast – open source, local, zero cloud fees
Show HN: I built an open-source podcast generator that speaks 10 languages
Show HN: Local AI podcast pipeline – from topic to audio in 30 seconds
```

**Body:**

```
I spent weekends recording, re-recording, and editing podcasts. So I built Podcast Brain Pro — an open-source AI podcast factory that runs entirely on your machine.

What it does:
• Type a topic → AI researches and writes a natural script
• Choose format: monologue, interview, or panel discussion
• Generate studio-quality audio locally (Apple Silicon / NVIDIA)
• English + 10 Indian languages (Hindi, Kannada, Tamil, etc.)
• Outputs WAV + RSS feed + metadata JSON
• Zero cloud fees, zero subscriptions, MIT licensed

Tech stack: FastAPI + PyTorch (VibeVoice TTS) + Next.js + Sarvam AI for Indic languages.

Live samples: https://frontend-chi-virid-53.vercel.app/landing
GitHub: https://github.com/niranjannie/podcast-brain-pro

I built this because I wanted to create podcasts without the studio, the editing, or the voice actors. The interview/panel modes use multi-agent script generation so speakers interrupt, disagree, and follow up like real people.

Would love feedback, especially on the audio quality and script generation. Happy to answer questions!
```

---

## First Comment (Post This Immediately After Submitting)

```
A bit more context since people are asking:

The audio synthesis is entirely local. For English, it uses VibeVoice (a 1.5B parameter PyTorch model, ~2GB). For Indian languages, it uses Sarvam AI's Bulbul API.

Script generation uses an LLM chain with Tavily web search — so if you type "quantum computing," it actually researches the topic before writing the script, not just hallucinates.

The "panel" mode is my favorite. It generates 2-3 speakers with distinct personalities who interrupt each other, disagree, and ask follow-ups. It sounds surprisingly natural.

Setup takes about 10 minutes if you have the GPU requirements (Apple Silicon M1+ or NVIDIA). All the code is MIT licensed.

Happy to answer any technical questions!
```

---

## Optimal Posting Time

**Best window:** Tuesday–Thursday, 7:00–10:00 AM Pacific Time

Why:
- Catches US West Coast morning commuters
- Catches US East Coast lunch browsers
- European afternoon audience is still active
- Avoids Monday (too much corporate news) and Friday (weekend dip)

**Avoid:**
- Major tech event days (Apple keynotes, Google I/O, etc.)
- Holidays
- Late night US / early morning Europe

---

## Engagement Strategy

**First 2 hours are critical.** HN's ranking algorithm weighs early engagement heavily.

1. **Post at the optimal time** (see above)
2. **Add your first comment immediately** — explains motivation, answers obvious questions
3. **Reply to EVERY comment within the first 2 hours** — even if it's just "Thanks!"
4. **Be humble and technical** — HN loves makers who answer technical questions honestly
5. **Don't argue with critics** — "That's fair, I'll look into it" goes further than defensiveness
6. **Don't ask friends to upvote** — HN detects voting rings and will penalize you

---

## What to Expect

**Good signs:**
- Comments asking technical questions
- "This is cool" + specific feedback
- People sharing use cases

**Bad signs:**
- "How is this different from X?" (be ready with a comparison)
- "Why would anyone use this?" (don't take it personally)
- Crickets (happens — try again in a few weeks with improvements)

**HN research says:** Average repo gains ~121 stars in 24h, ~289 in a week from a successful HN post.

---

## Follow-Up Posts

After 2-3 weeks, you can post again with:
- A major update/new feature
- A technical blog post about the architecture
- A "What I learned from launching on HN" post

**Don't** post the same thing twice. HN mods will flag it.

---

## Emergency Kit: Handling Common HN Comments

| Comment | Your Response |
|---------|--------------|
| "How is this different from NotebookLM?" | "NotebookLM is great for summaries but doesn't generate natural dialogue or support Indian languages. PBP focuses on podcast-specific formats (interview/panel) and local audio synthesis." |
| "Why not just use ElevenLabs?" | "ElevenLabs is excellent but costs ~$0.30/minute and requires cloud. PBP generates audio locally for free after model download." |
| "The audio quality isn't great" | "Fair point — this uses open-source TTS models, not proprietary ones. The tradeoff is local/free vs cloud/paid. I'd love specific feedback on what sounds off!" |
| "What's the business model?" | "There isn't one — it's a passion project. MIT licensed, completely free." |
| "I don't see why anyone would use this" | "Totally fair — it's niche. I built it for creators who want to produce multilingual audio content without studio time. If that's not you, no worries!" |

---

*Ready to launch. Pick a Tuesday or Thursday morning and go!*
