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
./skill/build_package.sh
```

That builds `skill/podcast-brain-pro-skill.zip` from the source in this folder, checks
the archive, refuses to package a `.DS_Store`, and prints the version it built.

**Always rebuild rather than syncing a copy by hand.** A hand-synced copy drifted once:
the staged zip was still version 1.1.0 — no AI disclosure, no disclosure check in the
validator, and the old token budget that truncated scripts mid-sentence — while the
source had moved on. Uploading that would have shipped an episode generator that
produces audio with no disclosure on it.

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
4. The skill's own output carries an AI disclosure, in the episode's language, because
   Article 50 of the EU AI Act requires it for synthetic audio. The validator enforces
   it. Do not remove it to "save" a few words.

## Marketplace packaging rules

If you upload this to a marketplace, the listing, its description, its sample outputs
and this package must not link to, promote or upsell a paid version of the skill or any
related product sold elsewhere. The links here point at a free MIT-licensed repository,
which is fine today. If you ever publish a paid version anywhere, remove those links
from this package and from the listing before you upload an update.
