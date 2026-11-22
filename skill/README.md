# Podcast Brain Pro — agent skill package

This folder packages the scriptwriting and production workflow for AI agent platforms that
follow the open SKILL.md standard. It can drive the application's local/cloud engines,
consent-gated cloning, show notes, chapters, social clips, and RSS APIs when the user has
the service installed.

```
skill/podcast-brain-pro/
├── SKILL.md                      the skill itself
├── scripts/validate_script.py    stdlib-only checker for an episode JSON
└── reference/
    ├── script-format.md          the script contract, durations, languages, voices
    └── local-tts.md              local/cloud engines, cloning, chapters, RSS
```

## Build the upload zip

```bash
cd skill
rm -f podcast-brain-pro-skill.zip
zip -r podcast-brain-pro-skill.zip podcast-brain-pro
```

Upload the zip at <https://www.agensi.io/sell>.

## What the skill can and cannot do

It carries the **production workflow**: research and write a timed episode, validate it,
refresh show notes and chapters, select source-grounded social clips, and drive an installed
Podcast Brain Pro service or another available TTS tool.

It does **not** carry application code or model weights. Buyers who want local audio install
the repository and its chosen engines. The skill never pretends those downloads or services
exist when they do not.

## Before you publish it

1. Check the frontmatter fields against the platform's own specification
   (`name`, `description`, `trigger`, `version`, `compatible_agents`).
2. Run one episode end to end in a real agent. A security scan plus a human review
   will reject a skill that does not work.
3. Read the disclosure note in `docs/ROADMAP_NEXT_LEVEL.md`: the local VibeVoice model
   embeds an audible AI-generated disclaimer and a watermark, and its model card
   restricts use to research and development. A commercial listing has to say so.
