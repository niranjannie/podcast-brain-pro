import os
import json
from datetime import datetime, timezone
from urllib.parse import quote
from xml.sax.saxutils import escape
from typing import Dict, Any

# The pipeline writes 24 kHz mono 16-bit WAV, i.e. 48000 bytes per second. The old
# estimate assumed 44.1 kHz stereo and produced durations about 3.7x too long.
WAV_BYTES_PER_SECOND = 48000


def seconds_to_hms(total_seconds: int) -> str:
    """Convert seconds to HH:MM:SS for iTunes duration."""
    total_seconds = int(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def generate_podcast_rss(
    output_dir: str,
    base_url: str = "http://localhost:8000",
    channel_title: str = "Podcast Brain Pro",
    channel_description: str = "AI generated podcasts, rendered locally",
    channel_author: str = "Podcast Brain Pro",
    channel_language: str = "en-us",
    channel_category: str = "Technology",
    channel_image: str = "",
    channel_email: str = "",
    explicit: bool = False,
) -> str:
    """Generate a podcast RSS 2.0 feed with <enclosure> tags for each episode.

    Episodes are the ``.wav`` files in ``output_dir``. When a transcript sidecar exists
    next to an episode, a Podcasting 2.0 ``<podcast:transcript>`` element is emitted.

    Apple Podcasts requires channel artwork, an author, an owner, a category and an
    explicit flag, so those are all emitted here; set ``PODCAST_IMAGE_URL`` and
    ``PODCAST_EMAIL`` before submitting the feed anywhere.
    """
    base_url = base_url.rstrip("/")
    files = []
    for f in os.listdir(output_dir):
        if f.endswith(".wav"):
            path = os.path.join(output_dir, f)
            stat = os.stat(path)
            files.append({
                "filename": f,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                "path": path,
            })
    files.sort(key=lambda x: x["created_at"], reverse=True)

    items = []
    for f in files:
        metadata: Dict[str, Any] = {}
        meta_path = os.path.splitext(f["path"])[0] + ".json"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    metadata = json.load(mf)
            except Exception:
                pass

        title = metadata.get("topic") or metadata.get("title") or f["filename"].replace(".wav", "").replace("_", " ")
        description = metadata.get("description") or f"Generated podcast episode: {title}"
        # UTC, and labelled as UTC. Local time with a +0000 suffix made episodes look
        # like they were published in the future.
        pub_date = f["created_at"].strftime("%a, %d %b %Y %H:%M:%S +0000")
        enclosure_url = f"{base_url}/outputs/{quote(f['filename'])}"

        duration_sec = metadata.get("duration_seconds")
        if duration_sec is None and metadata.get("duration_minutes"):
            duration_sec = int(metadata["duration_minutes"] * 60)
        if duration_sec is None:
            duration_sec = int(f["size_bytes"] / WAV_BYTES_PER_SECOND)

        duration_hms = seconds_to_hms(duration_sec)

        transcript_tag = ""
        transcript_path = os.path.splitext(f["path"])[0] + ".transcript.json"
        if os.path.exists(transcript_path):
            transcript_url = f"{base_url}/outputs/{quote(os.path.basename(transcript_path))}"
            transcript_tag = (
                f'\n      <podcast:transcript url="{escape(transcript_url)}" '
                f'type="application/json" rel="captions"/>'
            )

        # A stable guid: the enclosure URL changes on a rename or a host move, and
        # podcast clients would re-download the whole back catalogue.
        episode_id = metadata.get("episode_id")
        if episode_id:
            guid = f'<guid isPermaLink="false">{escape(str(episode_id))}</guid>'
        else:
            guid = f"<guid>{escape(enclosure_url)}</guid>"

        item = f"""    <item>
      <title>{escape(str(title))}</title>
      <description>{escape(str(description))}</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{escape(enclosure_url)}" length="{f['size_bytes']}" type="audio/wav"/>
      <itunes:duration>{duration_hms}</itunes:duration>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>{'true' if explicit else 'false'}</itunes:explicit>
      {guid}{transcript_tag}
    </item>"""
        items.append(item)

    items_xml = "\n".join(items)
    last_build = datetime.now(tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    feed_url = f"{base_url}/feed/podcast.rss"
    image_xml = f'\n    <itunes:image href="{escape(channel_image)}"/>' if channel_image else ""
    owner_xml = ""
    if channel_email:
        owner_xml = (
            f"\n    <itunes:owner><itunes:email>{escape(channel_email)}</itunes:email>"
            f"<itunes:name>{escape(channel_author)}</itunes:name></itunes:owner>"
        )

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0" xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
  <channel>
    <title>{escape(channel_title)}</title>
    <description>{escape(channel_description)}</description>
    <itunes:summary>{escape(channel_description)}</itunes:summary>
    <language>{escape(channel_language)}</language>
    <itunes:author>{escape(channel_author)}</itunes:author>
    <itunes:category text="{escape(channel_category)}"/>
    <itunes:explicit>{'true' if explicit else 'false'}</itunes:explicit>{image_xml}{owner_xml}
    <link>{escape(base_url)}</link>
    <atom:link href="{escape(feed_url)}" rel="self" type="application/rss+xml"/>
    <lastBuildDate>{last_build}</lastBuildDate>{items_xml}
  </channel>
</rss>"""
    return rss
