# `ig_content/` — Instagram posting queue

Drop Reels (`.mp4`, `.mov`) or photos (`.jpg`, `.jpeg`, `.png`) here.

The daily job picks the **next unposted file (sorted by filename)** once per day, generates a caption + hashtags with Gemini, and posts it to Instagram.

## Naming tip

Filename becomes part of the LLM prompt. A descriptive name → a better caption:

```
01-tiny-rice-harvest.mp4        # good
02-olive-oil-first-drop.mp4     # good
video_final_final_v3.mp4        # bad
```

## Deduplication

Already-posted files are tracked in `data/instagram.db`. Re-adding the same filename will be skipped.

## Hosting (how Instagram reaches your file)

Instagram's Graph API requires a **publicly-accessible HTTPS URL** for the media. On GitHub Actions this is handled automatically — the file is served at:

```
https://raw.githubusercontent.com/<owner>/<repo>/<branch>/ig_content/<filename>
```

If you run locally instead, set `PUBLIC_MEDIA_BASE_URL` to an S3/Cloudflare R2/etc. bucket you control.
