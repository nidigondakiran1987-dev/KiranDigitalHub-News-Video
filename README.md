# KiranDigitalHub News Video — GitHub Actions

Produces up to five **manually approved** news items per run from a Google Sheet: one Telugu+English narrated 1080×1920 short per item and one combined 1920×1080 long video. Text appears on slides (visual subtitles); this release does not create separate SRT captions or word-synchronized subtitles.

## Requirements

1. GitHub repository: `nidigondakiran1987-dev/KiranDigitalHub-News-Video`.
2. Google Cloud Sheets API enabled in `kirandigitalhub-news-video`.
3. Google Sheets spreadsheet shared with the service account **Viewer** permission.
4. Google Cloud Workload Identity Federation provider trusts GitHub repository and has `roles/iam.workloadIdentityUser` on the service account for the appropriate principal. The service account also needs permission to read the shared spreadsheet. No service account JSON key required.
5. GitHub Actions repository secrets:
   - `GCP_WORKLOAD_IDENTITY_PROVIDER` = `projects/529519213557/locations/global/workloadIdentityPools/kirandigitalhub-github/providers/kirandigitalhub-github-actions` (confirm against your provider's actual full resource name)
   - `GCP_SERVICE_ACCOUNT` = `kirandigitalhub-news-reader@kirandigitalhub-news-video.iam.gserviceaccount.com`
   - `GOOGLE_SHEET_ID` = spreadsheet ID between `/d/` and `/edit`
6. `GCP_PROJECT_ID` is optional for this workflow.

## Spreadsheet fields

`News Database` tab must have these exact headers: `News_ID`, `Date_IST`, `Verification_Status`, `Source_URL`, `English_Headline`, `Telugu_Script`. `Category` is optional. Set `Verification_Status` to `Approved` only after human review, and `Date_IST` as `yyyy-MM-dd` in Asia/Kolkata. The script does not fetch unapproved items or fabricate article summaries.

## Upload and run

- Upload the contents of this ZIP into the repository root (not inside an extra folder).
- If `.github/workflows/news-video.yml` already exists, replace it with the supplied workflow.
- GitHub → Actions → KiranDigitalHub News Video → Run workflow → `main`.
- After success: open run → Artifacts → `KiranDigitalHub-News-Review` → download ZIP of `news.json` and MP4s.

## Important limitations

- **Manual workflow only**: no recurring schedule, no automatic publishing to YouTube or WhatsApp.
- Deduplication is **within each run**, based on source URL/headline. Cross-run history is **not tracked**, so rerunning may produce the same videos. Add a reviewed persistent `Video Queue` tracking mechanism before enabling scheduling.
- English narration uses only the approved English headline; Telugu narration uses the existing Telugu script. No invented English article text.
- Edge TTS is an unofficial network-dependent interface; it can fail or change, and has no uptime guarantee. No paid API key is required.
- GitHub-hosted runners and artifact storage have plan-dependent quotas and retention. Cloud billing is not automatically required by this workflow, but review Google Cloud API quotas and any billing configuration before enabling services.
- No generated MP4s are included in this ZIP; they require a live run with approved data and internet access.
- Telugu font rendering requires Pillow with libraqm shaping support and Noto Sans Telugu. The Ubuntu package installs fonts; if text looks incorrect, verify `PIL.features.check('raqm')`.
- Google Cloud provider IAM and exact issuer/audience configuration must match your GitHub repository and branch; these are not testable from this ZIP.
