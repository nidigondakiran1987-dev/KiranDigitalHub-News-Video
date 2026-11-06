"""Render reviewed KiranDigitalHub news as bilingual Shorts and a long video."""
import asyncio
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import edge_tts
from PIL import Image, ImageDraw, ImageFont

ROOT = Path('output')
WORK = ROOT / 'work'
TE_VOICE = os.getenv('TE_VOICE', 'te-IN-ShrutiNeural')
EN_VOICE = os.getenv('EN_VOICE', 'en-IN-NeerjaNeural')


def locate_font(candidates):
    for name in candidates:
        if Path(name).is_file():
            return name
    raise FileNotFoundError('Install fonts-noto-core and fonts-dejavu-core; Telugu font missing')


TE_FONT = locate_font([
    '/usr/share/fonts/truetype/noto/NotoSansTelugu-Regular.ttf',
    '/usr/share/fonts/truetype/noto/NotoSansTeluguUI-Regular.ttf',
])
EN_FONT = locate_font(['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])


def run(cmd):
    subprocess.run(cmd, check=True)


def font(path, size):
    return ImageFont.truetype(path, max(12, size), layout_engine=ImageFont.Layout.RAQM if hasattr(ImageFont, 'Layout') else None)


def wrap(draw, text, fnt, width):
    lines = []
    for paragraph in str(text).splitlines():
        current = ''
        for word in paragraph.split():
            candidate = (current + ' ' + word).strip()
            if draw.textbbox((0, 0), candidate, font=fnt)[2] <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def fit_lines(draw, text, path, max_width, max_height, base_size, min_size, line_factor=1.45):
    for size in range(base_size, min_size - 1, -2):
        fnt = font(path, size)
        lines = wrap(draw, text, fnt, max_width)
        line_height = int(size * line_factor)
        if lines and len(lines) * line_height <= max_height and all(
            draw.textbbox((0, 0), line, font=fnt)[2] <= max_width for line in lines
        ):
            return fnt, lines, line_height
    raise ValueError('Text cannot fit without clipping; shorten the reviewed news script')


def slide(path, size, title, body, lang, source, date):
    w, h = size
    portrait = h > w
    im = Image.new('RGB', size, '#0b172a')
    d = ImageDraw.Draw(im)
    scale = w / 1080
    margin = int(65 * scale)
    footer = int((190 if portrait else 125) * scale)
    header_y = int((70 if portrait else 45) * scale)
    heading_y = int((285 if portrait else 165) * scale)
    d.rectangle((0, 0, w, max(8, int(14 * scale))), fill='#35c6dc')
    d.text((margin, header_y), 'KIRANDIGITALHUB', font=font(EN_FONT, int(42 * scale)), fill='#6be1ee')
    d.text((margin, header_y + int(72 * scale)), f'REVIEWED NEWS  |  {date}',
           font=font(EN_FONT, int(23 * scale)), fill='#b5c7df')

    title_area = int((325 if portrait else 170) * scale)
    tf, title_lines, tl = fit_lines(d, title, EN_FONT, w - 2 * margin, title_area,
                                    int((46 if portrait else 34) * scale), int(19 * scale))
    y = heading_y
    for line in title_lines:
        d.text((margin, y), line, font=tf, fill='white')
        y += tl
    y += int(30 * scale)
    d.line((margin, y, w - margin, y), fill='#35c6dc', width=max(2, int(3 * scale)))
    y += int(35 * scale)

    bottom = h - footer - int(35 * scale)
    available = bottom - y
    if available <= 0:
        raise ValueError('No room for body text')
    bf, body_lines, bl = fit_lines(d, body, TE_FONT if lang == 'te' else EN_FONT,
                                    w - 2 * margin, available,
                                    int((40 if portrait else 29) * scale), int(17 * scale))
    for line in body_lines:
        d.text((margin, y), line, font=bf, fill='#e4edf8')
        y += bl

    footer_top = h - footer
    d.rectangle((0, footer_top, w, h), fill='#122742')
    footer_font = font(EN_FONT, int(22 * scale))
    d.text((margin, footer_top + int(22 * scale)), f'SOURCE: {source[:55]}',
           font=footer_font, fill='#b5c7df')
    d.text((margin, footer_top + int(75 * scale)), 'kirandigitalhub.com | Manual review required',
           font=footer_font, fill='#6be1ee')
    im.save(path)


async def tts(text, voice, target):
    last = None
    for attempt in range(3):
        try:
            await edge_tts.Communicate(text=text, voice=voice, rate='-5%').save(str(target))
            if not target.exists() or target.stat().st_size < 1000:
                raise RuntimeError('TTS audio missing or too small')
            return
        except Exception as exc:
            last = exc
            await asyncio.sleep(2 * (attempt + 1))
    raise RuntimeError(f'Edge TTS failed: {last}')


def segment(png, mp3, mp4, w, h):
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
         '-loop', '1', '-framerate', '1', '-i', str(png), '-i', str(mp3),
         '-vf', f'fps=24,scale={w}:{h},format=yuv420p',
         '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '25',
         '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-ac', '2',
         '-shortest', '-movflags', '+faststart', str(mp4)])


def concat(parts, destination):
    manifest = WORK / f'concat_{destination.stem}.txt'
    manifest.write_text(''.join("file '" + str(p.resolve()).replace("'", "'\\''") + "'\n" for p in parts), encoding='utf-8')
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
         '-f', 'concat', '-safe', '0', '-i', str(manifest),
         '-c', 'copy', '-movflags', '+faststart', str(destination)])


async def main():
    data = json.loads((ROOT / 'news.json').read_text(encoding='utf-8'))
    items = data if isinstance(data, list) else data.get('items', [])
    if not isinstance(items, list):
        raise ValueError('news.json must be an array or contain an items array')
    if not items:
        print('No verified news selected; no MP4 files generated')
        return
    limit = max(1, int(os.getenv('MAX_NEWS', '5')))
    WORK.mkdir(parents=True, exist_ok=True)
    today = datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %b %Y')
    long_parts = []
    for i, item in enumerate(items[:limit], 1):
        title = str(item.get('headline', '')).strip()
        telugu = str(item.get('telugu', '')).strip()
        source_url = str(item.get('source', '')).strip()
        if not title or not telugu or not source_url.startswith('https://'):
            raise ValueError(f'News {i}: headline, telugu and HTTPS source are required')
        domain = urlparse(source_url).hostname or 'Official source'
        print(f'Rendering {i}/{min(len(items), limit)}: {title[:70]}', flush=True)
        aud_te, aud_en = WORK / f'{i:02}_te.mp3', WORK / f'{i:02}_en.mp3'
        await tts(telugu[:1800], TE_VOICE, aud_te)
        await tts(title[:1000], EN_VOICE, aud_en)
        for kind, size in [('short', (1080, 1920)), ('long', (1920, 1080))]:
            parts = []
            for lang, body, audio in [('te', telugu[:1800], aud_te), ('en', title[:1000], aud_en)]:
                png = WORK / f'{i:02}_{kind}_{lang}.png'
                mp4 = WORK / f'{i:02}_{kind}_{lang}.mp4'
                slide(png, size, title, body, lang, domain, today)
                segment(png, audio, mp4, *size)
                parts.append(mp4)
            if kind == 'short':
                concat(parts, ROOT / f'KDH_Short_{i:02}.mp4')
            else:
                long_parts.extend(parts)
    if long_parts:
        concat(long_parts, ROOT / 'KDH_Daily_Long.mp4')
    print('Finished. MP4 files saved in output/')


if __name__ == '__main__':
    asyncio.run(main())
