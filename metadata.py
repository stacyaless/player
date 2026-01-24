# metadata.py
import os
import io
import re
from PIL import Image
from mutagen.id3 import ID3, APIC
from mutagen import File as MutagenFile

try:
    from tinytag import TinyTag
except ImportError:
    TinyTag = None

def get_default_cover():
    return Image.new('RGB', (800, 800), color='#222222')

def get_track_info(path):
    title = os.path.basename(path)
    artist = "Unknown"
    duration = 0
    cover = get_default_cover()

    if TinyTag:
        try:
            t = TinyTag.get(path, image=True)
            if t.title: title = t.title
            if t.artist: artist = t.artist
            if t.duration: duration = t.duration
        except: pass
    
    size = os.path.getsize(path)
    if duration < 15 and size > 1024*1024:
        duration = size / (16*1024)

    try:
        f = MutagenFile(path)
        pil = None
        if f.tags and isinstance(f.tags, ID3):
            for k, v in f.tags.items():
                if k.startswith("APIC"):
                    pil = Image.open(io.BytesIO(v.data))
                    break
        elif hasattr(f, 'pictures') and f.pictures:
            pil = Image.open(io.BytesIO(f.pictures[0].data))
        elif f.tags and 'covr' in f.tags:
            pil = Image.open(io.BytesIO(f.tags['covr'][0]))
        
        if pil:
            cover = pil.convert("RGB")
    except: pass

    return title, artist, duration, cover

def parse_lrc_content(lrc_text):
    lyrics = {}
    times = []
    lines = lrc_text.splitlines()
    for line in lines:
        matches = re.findall(r'\[(\d+):(\d+\.?\d*)\]', line)
        text = re.sub(r'\[.*?\]', '', line).strip()
        if matches and text:
            for m in matches:
                min_v, sec_v = int(m[0]), float(m[1])
                time_key = min_v * 60 + sec_v
                lyrics[time_key] = text
                times.append(time_key)
    times.sort()
    return lyrics, times

def get_lyrics(audio_path):
    lrc_text = None
    try:
        audio = MutagenFile(audio_path)
        if audio.tags and isinstance(audio.tags, ID3):
            for key in audio.tags.keys():
                if key.startswith("USLT"):
                    lrc_text = str(audio.tags[key])
                    break
        elif hasattr(audio, 'tags') and 'LYRICS' in audio.tags:
            lrc_text = audio.tags['LYRICS'][0]
    except: pass

    if not lrc_text:
        base = os.path.splitext(audio_path)[0]
        lrc_path = base + ".lrc"
        if os.path.exists(lrc_path):
            try:
                with open(lrc_path, 'r', encoding='utf-8') as f:
                    lrc_text = f.read()
            except: pass

    if lrc_text:
        return parse_lrc_content(lrc_text)
    return {}, []
