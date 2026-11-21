# Podcast Brain Pro — agent skill package

This folder is the packaged version of Podcast Brain Pro for AI agent platforms that
follow the open SKILL.md standard (Claude Code, Codex CLI, Cursor, OpenClaw, Gemini
CLI, Copilot, and anything that speaks the Agensi MCP).

```
skill/podcast-brain-pro/
├── SKILL.md                      the skill itself
├── scripts/validate_script.py    stdlib-only checker for an episode JSON
└── reference/
    ├── script-format.md          the script contract, durations, languages, voices
    └── local-tts.md              running VibeVoice locally, the TTS API, the RSS feed
```

## Build the upload zip

```bash
cd skill
rm -f podcast-brain-pro-skill.zip
zip -r podcast-brain-pro-skill.zip podcast-brain-pro
```

Upload the zip at <https://www.agensi.io/sell>.

## What the skill can and cannot do

It carries the **scriptwriting workflow**: research a topic, write a timed episode in
English or 10 Indian languages in monologue, interview or panel format, mark delivery
(`[[pause:0.8]]`, `[[style:calm]]`), validate the result, and hand it to whatever TTS
the environment has.

It does **not** carry the VibeVoice models. They are ~15 GB and a skill is delivered as
text through the agent connection, so the local TTS path stays a documented reference
pointing at this repository.

## Before you publish it

1. Check the frontmatter fields against the platform's own specification
   (`name`, `description`, `trigger`, `version`, `compatible_agents`).
2. Run one episode end to end in a real agent. A security scan plus a human review
   will reject a skill that does not work.
3. Read the disclosure note in `docs/ROADMAP_NEXT_LEVEL.md`: the local VibeVoice model
   embeds an audible AI-generated disclaimer and a watermark, and its model card
   restricts use to research and development. A commercial listing has to say so.
