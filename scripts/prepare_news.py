
import os
import json
import datetime
from zoneinfo import ZoneInfo

from google.auth import default
from googleapiclient.discovery import build

sheet_id = os.environ["GOOGLE_SHEET_ID"]

credentials, _ = default(
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets.readonly"
    ]
)

service = build(
    "sheets", "v4",
    credentials=credentials,
    cache_discovery=False
)

result = service.spreadsheets().values().get(
    spreadsheetId=sheet_id,
    range="'News Database'!A1:AZ"
).execute()

rows = result.get("values", [])
if not rows:
    raise RuntimeError("News Database is empty")

headers = rows[0]
today = datetime.datetime.now(
    ZoneInfo("Asia/Kolkata")
).strftime("%Y-%m-%d")

news = []

for values in rows[1:]:
    row = dict(zip(headers, values))

    if row.get("Verification_Status", "").strip() != "Approved":
        continue

    if row.get("Date_IST", "").strip() != today:
        continue

    if not row.get("Source_URL", "").startswith("https://"):
        continue

    news.append({
        "id": row.get("News_ID", ""),
        "headline": row.get("English_Headline", ""),
        "telugu": row.get("Telugu_Script", ""),
        "source": row.get("Source_URL", "")
    })

os.makedirs("output", exist_ok=True)

with open("output/news.json", "w", encoding="utf-8") as f:
    json.dump(news, f, ensure_ascii=False, indent=2)

print(f"Approved news selected: {len(news)}")
