# Gmail API Setup for GhostPost

## 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing): **GhostPost**
3. Note the Project ID

## 2. Enable Gmail API

1. Go to **APIs & Services > Library**
2. Search for **Gmail API**
3. Click **Enable**

## 3. Configure OAuth Consent Screen

1. Go to **APIs & Services > OAuth consent screen**
2. Select **External** user type (or Internal if using Workspace)
3. Fill in:
   - App name: **GhostPost**
   - User support email: your email
   - Developer contact: your email
4. Add scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/gmail.labels`
5. Add your Gmail address as a **test user**
6. Save

## 4. Create OAuth Credentials

1. Go to **APIs & Services > Credentials**
2. Click **+ CREATE CREDENTIALS > OAuth client ID**
3. Application type: **Desktop app**
4. Name: **GhostPost Desktop**
5. Download the JSON file

## 5. Install Credentials

```bash
# Copy the downloaded JSON to the project root
cp ~/Downloads/client_secret_*.json /home/athena/ghostpost/credentials.json
```

The filename must match `GMAIL_CREDENTIALS_FILE` in `.env` (default: `credentials.json`).

## 6. Generate Token (First-Time Auth)

```bash
cd /home/athena/ghostpost
.venv/bin/python3.12 -c "
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels',
]

flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)

import json
with open('token.json', 'w') as f:
    f.write(creds.to_json())

print('Token saved to token.json')
"
```

> **Note:** This opens a browser for Google sign-in. If running on a headless server, use `flow.run_console()` instead of `flow.run_local_server()`, or run the auth flow locally and copy `token.json` to the server.

## 7. Verify

```bash
.venv/bin/python3.12 -c "
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_authorized_user_file('token.json')
service = build('gmail', 'v1', credentials=creds)
profile = service.users().getProfile(userId='me').execute()
print(f'Connected as: {profile[\"emailAddress\"]}')
print(f'Messages: {profile[\"messagesTotal\"]}')
"
```

## Security Notes

- **Never commit** `credentials.json` or `token.json` to git (both are in `.gitignore`)
- Token auto-refreshes; if it expires completely, re-run step 6
- Keep scopes minimal — only request what GhostPost needs
