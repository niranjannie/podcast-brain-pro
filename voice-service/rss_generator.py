import os
import json
from datetime import datetime
from xml.sax.saxutils import escape
from typing import Optional, Dict, Any


def seconds_to_hms(total_seconds: int) -> str:
    """Convert seconds to HH:MM:SS for iTunes duration."""
    total_seconds = int(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def generate_podcast_rss(output_dir: str, base_url: str = "http://localhost:9876") -> str:
    """Generate a podcast RSS 2.0 feed with <enclosure> tags for each .wav file."""
    files = []
    for f in os.listdir(output_dir):
        if f.endswith(".wav"):
            path = os.path.join(output_dir, f)
            stat = os.stat(path)
            files.append({
                "filename": f,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime),
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
        pub_date = f["created_at"].strftime("%a, %d %b %Y %H:%M:%S +0000")
        enclosure_url = f"{base_url}/outputs/{f['filename']}"

        duration_sec = metadata.get("duration_seconds")
        if duration_sec is None and metadata.get("duration_minutes"):
            duration_sec = int(metadata["duration_minutes"] * 60)
        if duration_sec is None:
            # Rough estimate for 44.1kHz 16-bit stereo WAV (~176KB/s)
            duration_sec = int(f["size_bytes"] / 176400)

        duration_hms = seconds_to_hms(duration_sec)

        item = f"""    <item>
      <title>{escape(str(title))}</title>
      <description>{escape(str(description))}</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{escape(enclosure_url)}" length="{f['size_bytes']}" type="audio/wav"/>
      <itunes:duration>{duration_hms}</itunes:duration>
      <guid>{escape(enclosure_url)}</guid>
    </item>"""
        items.append(item)

    items_xml = "\n".join(items)

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
  <channel>
    <title>AI_VOICEVIBE Podcast</title>
    <description>AI-generated podcasts powered by Microsoft VibeVoice</description>
    <language>en-us</language>
    <itunes:author>AI_VOICEVIBE</itunes:author>
    <itunes:category text="Technology"/>
    <itunes:image href="https://via.placeholder.com/1400x1400.png?text=AI_VOICEVIBE+Podcast"/>
    <link>{base_url}</link>
{items_xml}
  </channel>
</rss>"""
    return rss
