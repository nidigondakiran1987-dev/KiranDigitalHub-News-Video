"""Read today's approved, source-linked news from Google Sheets (IST)."""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

from google.auth import default
from googleapiclient.discovery import build

REQUIRED = ['News_ID', 'Date_IST', 'Verification_Status', 'Source_URL', 'English_Headline', 'Telugu_Script']

def main():
    sheet_id = os.environ['GOOGLE_SHEET_ID'].strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,}', sheet_id):
        raise ValueError('GOOGLE_SHEET_ID must be the spreadsheet ID, not its full URL')
    creds, _ = default(scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    api = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    response = api.spreadsheets().values().get(spreadsheetId=sheet_id, range="'News Database'!A1:AZ", valueRenderOption='FORMATTED_VALUE').execute()
    rows = response.get('values', [])
    if not rows:
        raise RuntimeError('News Database is empty')
    headers = [str(x).strip() for x in rows[0]]
    missing = [x for x in REQUIRED if x not in headers]
    if missing:
        raise RuntimeError('Missing required sheet headers: ' + ', '.join(missing))
    today = datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y-%m-%d')
    seen_urls, seen_titles, selected = set(), set(), []
    for raw in rows[1:]:
        row = dict(zip(headers, raw))
        status = str(row.get('Verification_Status', '')).strip().casefold()
        if status != 'approved':
            continue
        date = str(row.get('Date_IST', '')).strip()
        # Accept ISO date or a Sheets display format, but never infer ambiguous US-style dates.
        if date != today:
            continue
        url = str(row.get('Source_URL', '')).strip()
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            continue
        title = str(row.get('English_Headline', '')).strip()
        telugu = str(row.get('Telugu_Script', '')).strip()
        if not (url and title and telugu):
            continue
        if url in seen_urls or title.casefold() in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(title.casefold())
        selected.append({'id': str(row.get('News_ID', '')).strip(), 'title_en': title,
                         'script_te': telugu, 'source_url': url,
                         'category': str(row.get('Category', '')).strip()})
    Path('output').mkdir(exist_ok=True)
    Path('output/news.json').write_text(json.dumps({'date_ist': today, 'items': selected}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'IST date {today}: {len(selected)} approved unique items selected')
    if not selected:
        print('No approved news available. No video will be created.')

if __name__ == '__main__':
    main()
