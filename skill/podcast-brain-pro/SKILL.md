---
name: podcast-brain-pro
description: Turn any topic into a finished podcast episode - a research-grounded script in English or 10 Indian languages, in monologue, two-host interview, or three-person panel format, plus optional local VibeVoice TTS audio and an RSS feed.
trigger: podcast, podcast script, episode script, make a podcast, turn this topic into a podcast, audio episode, show notes, podcast brain pro
version: 1.0.0
compatible_agents: claude, claude-code, codex, cursor, chatgpt, openclaw, gemini-cli, copilot, cline, kiro, grok
---

# Podcast Brain Pro

Topic in, episode out. This skill encodes the scriptwriting rules that come from the
Podcast Brain Pro open-source pipeline (MIT, github.com/niranjannie/podcast-brain-pro),
so the agent produces a script that can be fed straight into TTS without rewriting.

## 1. Collect the brief

Ask for at most three missing details in one message. If the user does not answer, use the
defaults below and say which defaults you used.

| Input | Default | Allowed |
|---|---|---|
| topic | required | free text |
| format | `monologue` | `monologue`, `interview`, `panel` |
| duration_minutes | `5` | `2`, `5`, `10`, `15`, `30` |
| language | `en` | `en`, `hi-IN`, `ta-IN`, `te-IN`, `kn-IN`, `bn-IN`, `mr-IN`, `gu-IN`, `ml-IN`, `pa-IN`, `od-IN` |
| speakers | format default | up to 3 names |

Default speakers: `monologue` -> `Host`; `interview` -> `Host`, `Guest`;
`panel` -> `Host`, `Guest A`, `Guest B`. If the user supplies custom speaker names, use
exactly those, in order, one per role.

Language names: English, Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, Gujarati,
Malayalam, Punjabi, Odia.

## 2. Ground the script in facts

- If a web search or fetch tool is available, research the topic first and keep notes.
- Use only what you can attribute. Do not invent statistics, quotes, dates, or names.
- If you could not research, write the script from general knowledge and open with one
  honest framing line instead of pretending to fresh facts.
- Keep research notes to roughly 4000 characters of useful context; drop the rest.

## 3. Write the script

**Length budget (words of spoken content):**

| duration_minutes | words |
|---|---|
| 2 | 300 |
| 5 | 750 |
| 10 | 1500 |
| 15 | 2250 |
| 30 | 4500 |

**Monologue**
- One speaker (`Host`) speaking throughout.
- Plain spoken text only: no markdown, no bullet points, no headings, no sound-effect cues
  or stage directions - they break TTS.
- Open with the topic and why it matters now, develop it, present more than one side
  fairly, close with a brief sign-off.

**Interview and panel**
- Every turn starts with the speaker name and a colon, exactly: `Host: Welcome back...`
- `Host` opens by introducing the show and the topic, then asks the first question.
- Real back-and-forth: follow-ups, one disagreeing point, a clarification, a second
  question that changes the topic slightly. No turn may be a rephrasing of the last one.
- Keep every turn in the same voice, but make the voices differ in vocabulary and stance.
- The last turn is a short wrap by `Host`.

**Both**
- Conversational register. Short sentences. Read it out loud in your head; if a sentence
  cannot be spoken without pausing to parse it, rewrite it.
- No hype, no clickbait, no fear-mongering, no filler openings like "In today's episode".
- Specific beats general: concrete examples, numbers you can source, names, places, dates.
- Never end mid-thought. No trailing "Let me know if you want..." inside the script.

**Delivery directions**
Mark the beats you want heard, inline where they belong. The audio engine renders both:
- `[[pause:0.8]]` - insert 0.8 seconds of silence after the text before it. Use 0.3 to
  1.2 seconds, at a question, before an answer, after a key fact, at the end of a section.
- `[[style:calm]]` - switch delivery for the rest of that turn. One of `neutral`,
  `calm`, `narrative`, `serious`, `warm`, `excited`. Use at most twice per script.

**Indian-language scripts**
- Write the entire script in the target language. Do not mix English sentences in.
- Indic scripts need more detail for the same length budget because the model tokenises
  them at roughly 1.5x the characters - fill the budget with examples, history, context,
  and multiple viewpoints rather than shortening the episode.
- Keep speaker names as given (usually Latin script names are fine and are how the voices
  are matched).

## 4. Return two things

**a. A JSON block** matching this contract exactly - this is what the TTS step consumes:

```json
{
  "topic": "string",
  "duration_minutes": 5,
  "format": "interview",
  "language": "en",
  "script": [
    { "speaker": "Host", "content": "Welcome back to the show..." },
    { "speaker": "Guest", "content": "Thanks for having me..." }
  ]
}
```

`script` is a flat, ordered list of turns. `content` is the spoken text only - never
include the speaker name inside `content`. Delivery markers (`[[pause:0.8]]`,
`[[style:calm]]`) stay in `content`: the audio engine renders them as real silence and
a different delivery setting.

**b. A plain transcript** for the user to read, with `Speaker: text` per line.

## 5. Validate before you claim it works

Run the bundled checker on the JSON you produced:

```bash
python3 scripts/validate_script.py episode.json
```

It checks the enum values, the speaker count against the format, the word count against
the duration budget, empty turns, and speaker-name drift. Fix what it reports and re-run
until it passes. If it cannot run (no Python, no write access), do the same checks by hand
and state that you did.

## 6. Audio (only if the user wants audio)

**Local, private path - VibeVoice on the user's own machine**
Requires macOS Apple Silicon or a CUDA GPU, Python 3.10+, and roughly 15 GB of disk for
the models. Setup and the exact API calls are in `reference/local-tts.md`.

Give every host a different voice. The local service exposes the available presets at
`GET /voices` and accepts one voice id per speaker in `voice_names`, in the order the
speakers first appear in the script.

**Hosted path**
If the environment exposes a TTS tool (ElevenLabs, MiniMax, HeyGen, Sarvam, or any other),
use it per turn, keyed by speaker name, and stitch the results. Report per-turn cost
before a long episode so the user can stop.

Every export is normalised to podcast loudness (-16 LUFS, -1.5 dBTP) and the measurement
is recorded next to the episode, so the file is ready for a podcast host.

Never invent a download URL for audio. If neither path is available, deliver the script and
say plainly that audio needs one of the two setups above.

## 7. RSS and distribution

If the user wants to publish, produce an RSS item alongside the audio: title, description,
publication date, duration, and an enclosure pointing at the final file. `reference/local-tts.md`
shows the feed format the open-source project emits.

## Reference

- `reference/script-format.md` - the full script contract, durations, languages, speakers,
  and the JSON schema the TTS endpoint expects.
- `reference/local-tts.md` - running VibeVoice locally, the HTTP API, and the RSS feed.
