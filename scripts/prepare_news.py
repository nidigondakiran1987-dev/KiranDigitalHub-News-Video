
import os
import json
import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

from google.auth import default
from googleapiclient.discovery import build

TIMEZONE = ZoneInfo("Asia/Kolkata")
SHEET_NAME = "News Database"
SHEET_ID = os.environ["GOOGLE_SHEET_ID"]

today = datetime.datetime.now(TIMEZONE).date()

credentials, _ = default(
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)

service = build(
    "sheets",
    "v4",
    credentials=credentials,
    cache_discovery=False
)

result = service.spreadsheets().values().get(
    spreadsheetId=SHEET_ID,
    range=f"'{SHEET_NAME}'!A1:AZ",
    valueRenderOption="FORMATTED_VALUE"
).execute()

rows = result.get("values", [])

if not rows:
    raise RuntimeError("News Database is empty")

headers = [str(h).strip() for h in rows[0]]

required = [
    "News_ID",
    "Date_IST",
    "English_Headline",
    "Telugu_Script",
    "Source_URL",
    "Verification_Status"
]

missing = [h for h in required if h not in headers]

if missing:
    raise RuntimeError(f"Missing columns: {missing}")

def parse_sheet_date(value):
    value = str(value).strip()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    return None

news = []
seen_urls = set()
seen_ids = set()

for values in rows[1:]:
    row = dict(zip(headers, values))

    status = str(
        row.get("Verification_Status", "")
    ).strip().lower()

    if status != "verified":
        continue

    published_date = parse_sheet_date(
        row.get("Date_IST", "")
    )

    if published_date != today:
        continue

    source = str(row.get("Source_URL", "")).strip()
    headline = str(row.get("English_Headline", "")).strip()
    telugu = str(row.get("Telugu_Script", "")).strip()
    news_id = str(row.get("News_ID", "")).strip()

    parsed_url = urlparse(source)

    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or not headline
        or not telugu
        or not news_id
    ):
        continue

    if source in seen_urls or news_id in seen_ids:
        continue

    seen_urls.add(source)
    seen_ids.add(news_id)

    news.append({
        "id": news_id,
        "headline": headline,
        "telugu": telugu,
        "source": source
    })

os.makedirs("output", exist_ok=True)

output_path = "output/news.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(news, f, ensure_ascii=False, indent=2)

print(f"Today IST: {today.isoformat()}")
print(f"Verified news selected: {len(news)}")
print(f"JSON saved: {output_path}")

if not news:
    print("No verified news found for today.")

