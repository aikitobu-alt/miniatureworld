# AI Shorts Pipeline

Fully-automated YouTube Shorts pipeline for **@myminiatureworld4u**:

```
topic (auto-generated)
 → script (OpenAI gpt-4o-mini → structured JSON)
 → voiceover (ElevenLabs)
 → AI scenes (Kling via fal.ai; Runway optional)
 → assembly (ffmpeg: 9:16, burned captions, music bed, audio mix)
 → upload (YouTube Data API v3, as a Short)
 → daily cron (GitHub Actions)
```

Every stage is a pluggable module — swap providers by editing `config.yaml` or
adding a new `video_providers/*.py`.

---

## Quick start

```bash
# 1. Install
git clone <this repo>
cd shorts-pipeline
python -m venv .venv && source .venv/bin/activate
pip install -e .
sudo apt-get install -y ffmpeg   # macOS: brew install ffmpeg

# 2. Configure secrets
cp .env.example .env
#   fill in OPENAI_API_KEY, ELEVENLABS_API_KEY, FAL_KEY
#   (leave YT_* blank for now — see "YouTube setup" below)

# 3. Edit config.yaml — especially your preferred ElevenLabs voice_id

# 4. Drop a few royalty-free music loops into assets/music/ (optional)

# 5. Verify
shorts check

# 6. Generate one Short (no upload)
shorts generate

# 7. Generate + upload
shorts run
```

Each run writes to `outputs/<timestamp>_<slug>/` with the script JSON, each
scene clip, the voiceover mp3, and `final.mp4`.

---

## YouTube setup (one-time, ~10 minutes)

You need three values: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

1. Go to <https://console.cloud.google.com/projectcreate> → create a project
   (name it "shorts-pipeline"). Make sure the project is selected.
2. Open <https://console.cloud.google.com/apis/library/youtube.googleapis.com>
   → click **Enable**.
3. Open <https://console.cloud.google.com/apis/credentials/consent>:
   - User type: **External** → Create
   - App name: `shorts-pipeline`, your email for support + developer contact
   - **Scopes**: add `https://www.googleapis.com/auth/youtube.upload`
   - **Test users**: add the Google account that owns `@myminiatureworld4u`
   - Publish status can stay "Testing" — the refresh token from a test user
     works indefinitely.
4. Open <https://console.cloud.google.com/apis/credentials>:
   - **Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Copy the **Client ID** and **Client Secret**.
5. Run the interactive flow to get a refresh token:
   ```bash
   shorts oauth --client-id <CLIENT_ID> --client-secret <CLIENT_SECRET>
   ```
   It opens a browser. Sign in with the YouTube channel's Google account,
   approve, and the command prints three values — put them in `.env` (or in
   GitHub Actions secrets if using the scheduler).

---

## Providers & swapping

Edit `config.yaml`:

```yaml
providers:
  llm:
    model: "gpt-4o-mini"
  tts:
    provider: "elevenlabs"  # or "openai" or "none"
    voice_id: "EXAVITQu4vr4xnSDxMaL"
  video:
    provider: "kling"       # or "runway" or "stills"
```

- **`kling`** (default, cheap): Kling v1.6 via fal.ai, ~$0.10–0.20 per 5s clip.
- **`runway`** (premium): Runway Gen-3 Turbo. Higher quality, ~$0.50/5s. Set
  `RUNWAY_API_KEY` in `.env`.
- **`stills`** (cheapest): OpenAI `gpt-image-1` + ffmpeg Ken Burns motion.
  No video API bill. Good for testing.

---

## Daily scheduling

### Option A — GitHub Actions (recommended, "while you sleep")

1. Push this repo to a **private** GitHub repo.
2. In repo settings → **Secrets and variables → Actions → New repository secret**,
   add: `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `FAL_KEY`, `YT_CLIENT_ID`,
   `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`, (optional `RUNWAY_API_KEY`).
3. The workflow in `.github/workflows/daily.yml` runs at 12:00 UTC every day
   and uploads a new Short. Adjust the cron to your audience's peak time.

### Option B — local cron

```cron
0 12 * * *  cd /path/to/shorts-pipeline && /path/to/.venv/bin/shorts run >> cron.log 2>&1
```

---

## CLI reference

```bash
shorts check              # verify config + API keys
shorts topics --n 10      # print 10 fresh topic candidates
shorts generate           # end-to-end generate, no upload
shorts generate --no-tts  # skip voiceover
shorts run                # generate + upload
shorts run --no-upload    # same as `generate`
shorts oauth --client-id ... --client-secret ...   # YouTube OAuth flow
shorts assemble-only script.json scenes/           # re-stitch a run
```

---

## Costs (rough, per Short)

| Stage          | Provider          | Cost |
| -------------- | ----------------- | ---- |
| Script + topic | OpenAI gpt-4o-mini | ~$0.002 |
| Voiceover ~80w | ElevenLabs Turbo   | ~$0.02 |
| 5 × 5s video   | Kling v1.6         | ~$0.75 |
| 5 × 5s video   | Runway Gen-3 Turbo | ~$2.50 |
| 5 × stills     | gpt-image-1        | ~$0.20 |
| Upload         | YouTube API        | free  |

Baseline (Kling path) ≈ **$0.80 / Short**. 30 shorts/month ≈ **$24**.

---

## Directory layout

```
shorts_pipeline/
  cli.py              # typer CLI
  config.py           # config + env loading
  models.py           # pydantic dataclasses
  llm.py              # OpenAI wrapper
  topics.py           # LLM → fresh topic candidates (deduped)
  script.py           # topic → structured Script JSON
  tts.py              # ElevenLabs / OpenAI TTS
  video_providers/    # kling, runway, stills (swap via config)
  assemble.py         # ffmpeg: 9:16, captions, music, audio mix
  youtube.py          # YouTube Data API v3 upload
  state.py            # SQLite topic/upload log
  pipeline.py         # end-to-end orchestration
assets/music/         # royalty-free loops (drop-in)
outputs/              # per-run artifacts
.github/workflows/daily.yml   # cron scheduler
config.yaml           # user-editable config
.env.example          # required env vars
```

---

## Growth-strategy guardrails (baked in)

- Titles generated under the **H.O.O.K.E.D.** formula (hook / number / question /
  superlative / specificity).
- Hashtags validated for relevance per topic — no `#automobile` on farming
  shorts ever.
- First scene prompt is forced to open on motion in frame 1 (no static wides).
- Last scene visually loops back to the first to maximize replay-retention.
- Every scene ≤ 8s; captions ≤ 6 words; voiceover ≤ 100 words.
- Deduped topic log in SQLite to prevent repeats.
