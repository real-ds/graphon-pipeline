# Google Sheets Export Options

If you can't create a GCP service account (or get `iam.disableServiceAccountCreation` errors),
here are your alternatives, ranked from easiest to most powerful:

## Option 1: Manual CSV Upload (Easiest — Works Now!)

The CSVs in `data/exports/` are already correctly formatted and named.

1. Go to https://sheets.google.com/create
2. Rename "Sheet1" to **"Startups"**
3. **File → Import → Upload** `data/exports/startups.csv`
   - Import location: **"Replace current sheet"**
   - Separator type: **"Comma"**
4. Repeat for each tab (right-click "+" to add new sheets):

| Tab Name | CSV File |
|---|---|
| Startups | `data/exports/startups.csv` |
| Products | `data/exports/products.csv` |
| Research Papers | `data/exports/research_papers.csv` |
| Jobs | `data/exports/jobs.csv` |
| News | `data/exports/news.csv` |
| Entity Mapping Log | `data/exports/entity_mapping.csv` |

5. Click **Share → "Anyone with the link" → "Viewer"**
6. Copy the shareable URL — this is what you submit.

## Option 2: OAuth2 with Your Personal Google Account

1. Go to https://console.cloud.google.com → **APIs & Services → Credentials**
2. Click **"+ Create Credentials" → "OAuth 2.0 Client ID"**
3. Application type: **Desktop app**
4. Name: `graphone-pipeline`
5. Download the JSON
6. Save it as `credentials/oauth_client.json`
7. Run: `python scripts/export_to_sheets_oauth.py`
8. Browser opens → log in with your Google account → grant permission
9. Script creates a new spreadsheet with all 6 tabs populated
10. The script prints the spreadsheet URL

The OAuth token is cached at `credentials/oauth_token.json` so subsequent runs skip the browser.

## Option 3: Fix the Service Account (If You Have Owner Permissions)

If you have Owner/Admin on the GCP project:

1. Go to https://console.cloud.google.com/iam-admin/iam
2. Find your account
3. Click **Edit** (pencil icon)
4. Add role: **Service Account Admin** + **Service Account Token Creator**
5. Save
6. Try creating the service account again

Or ask your GCP org admin to enable service account creation at:
https://console.cloud.google.com/iam-admin/org-policies

## Recommendation

**Use Option 1 (Manual CSV Upload)** for the submission — it's the fastest and doesn't require any setup. The CSVs are already correctly formatted and contain all 5,000+ records.
