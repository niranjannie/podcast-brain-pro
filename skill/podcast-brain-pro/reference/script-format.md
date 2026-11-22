# Script format reference

Contract taken from the Podcast Brain Pro backend (`voice-service/main.py`). If the local
service is running, these are literally its request and response models.

## Request (script generation)

```
POST /podcast/generate
```

| Field | Type | Required | Rules |
|---|---|---|---|
| `topic` | string | yes | free text |
| `duration_minutes` | int | no | 2-30, default 2. Snap to the table below. |
| `format` | string | no | `monologue` \| `interview` \| `panel`, default `monologue` |
| `speakers` | string[] | no | max 3 items; used only if the count matches the format |
| `language` | string | no | see language codes below, default `en` |

## Response (script generation)

```
POST /podcast/generate -> PodcastScriptResponse
```

```json
{
  "topic": "Nation building: India vs China",
  "duration_minutes": 5,
  "format": "panel",
  "language": "hi-IN",
  "script": [{ "speaker": "Host", "content": "..." }],
  "word_count": 812,
  "generation_time_seconds": 21.4
}
```

`script` is a list of turns, each `{ "speaker": string, "content": string }`. The order is
playback order.

## Duration to word budget

| duration_minutes | target words | max tokens |
|---|---|---|
| 2 | 300 | 800 |
| 5 | 750 | 1500 |
| 10 | 1500 | 2500 |
| 15 | 2250 | 3500 |
| 30 | 4500 | 5500 |

## Speaker defaults

| format | speakers |
|---|---|
| `monologue` | `Host` |
| `interview` | `Host`, `Guest` |
| `panel` | `Host`, `Guest A`, `Guest B` |

Custom names are accepted only when the count matches the format. Names are matched
case-insensitively when parsing "Speaker: text" back into turns, then normalised to the
canonical spelling.

## Language codes

`en`, `hi-IN`, `ta-IN`, `te-IN`, `kn-IN`, `bn-IN`, `mr-IN`, `gu-IN`, `ml-IN`, `pa-IN`, `od-IN`

| code | language |
|---|---|
| `en` | English |
| `hi-IN` | Hindi |
| `ta-IN` | Tamil |
| `te-IN` | Telugu |
| `kn-IN` | Kannada |
| `bn-IN` | Bengali |
| `mr-IN` | Marathi |
| `gu-IN` | Gujarati |
| `ml-IN` | Malayalam |
| `pa-IN` | Punjabi |
| `od-IN` | Odia |

## Delivery directives

Delivery markers live inline in `content` and are stripped before synthesis:

| Marker | Effect |
|---|---|
| `[[pause:0.8]]` | Insert 0.8 s of silence after the text before the marker (0.3 - 1.2 s, capped at 10 s) |
| `[[style:calm]]` | Change delivery for the rest of that turn. Styles: `neutral`, `calm`, `narrative`, `serious`, `warm`, `excited` |

Styles map to the synthesis settings of the engine in use: for the local VibeVoice path
they change the guidance scale (a looser scale is more expressive), for the Sarvam path
they change pace and temperature. A style marker applies until the next marker.

## Voice selection

`GET /voices` returns the presets on disk:

```json
{
  "longform": [{ "id": "en-Carter_man", "language": "en", "gender": "man", "name": "Carter" }],
  "streaming": [{ "id": "en-Carter_man", "language": "en", "gender": "man", "name": "Carter" }],
  "cloned": [],
  "styles": ["calm", "excited", "narrative", "neutral", "serious", "warm"]
}
```

`POST /tts/longform` takes `voice_names`: one voice id per speaker, in the order the
speakers first appear in the script. When it is omitted, the engine matches the speaker
name against the voice file names and then hands out the remaining voices, so two hosts
never share one voice.

## Loudness

Every export is normalised to -16 LUFS with a true peak ceiling of -1.5 dBTP, and the
measurement is stored in the episode metadata under `loudness`. Set `NORMALIZE_LOUDNESS=false`
to turn it off. The pass needs `ffmpeg` on the machine.

## TTS request

```
POST /tts/longform
```

| Field | Type | Notes |
|---|---|---|
| `script` | list of dicts | the turn list, `{"speaker": ..., "content": ...}` |
| `voice_names` | string[] | one voice per speaker, in the same order as the speakers |
| `engine` | string | `vibevoice` (default), `kokoro`, `qwen3-tts`, or `chatterbox` |
| `duration_minutes` | int | original episode length, retained for rerendering |
| `extras` | object | optional validated show notes, chapters, captions, and clip selections |
| `cfg_scale` | float | 1.3 default for longform, 1.5 for realtime |
| `save_to_disk` | bool | default true |
| `topic` | string | used for the output filename |
| `format` | string | `monologue` \| `interview` \| `panel` |
| `language` | string | language code |

Single-turn synthesis uses `POST /tts/realtime` with `{ "text", "speaker_name", ... }`.

## Related endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness |
| `GET /models/status` | which TTS/ASR models are loaded |
| `GET /engines` | install/runtime health and preset voices for optional engines |
| `POST /podcast/extras` | refresh show notes, chapters, captions, and clip selections without rewriting |
| `POST /tts/engine` | single-voice preview with Kokoro, Qwen3-TTS, or a consented clone |
| `POST /tts/clone` | consent-gated cloning; Qwen requires `reference_text` |
| `GET /config`, `POST /config` | read and write provider keys |
| `GET /feed/podcast.rss` | RSS feed for generated episodes |
| `POST /asr/transcribe` | transcribe an audio file |
