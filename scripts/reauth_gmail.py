"""Re-authorize Gmail OAuth2 with updated scopes.

Run on a machine with a browser, or use the URL-based flow on headless servers.
Reads client_id/client_secret from existing token.json to avoid needing credentials.json.
"""

import json

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]

# Build client config from existing token (no credentials.json needed)
with open("token.json") as f:
    token = json.load(f)

client_config = {
    "installed": {
        "client_id": token["client_id"],
        "client_secret": token["client_secret"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

print("Opening browser for Google sign-in...")
print("If on a headless server, copy the URL and complete auth in a local browser.\n")

creds = flow.run_local_server(port=8090, open_browser=False)

with open("token.json", "w") as f:
    f.write(creds.to_json())

print("\nToken saved to token.json with scopes:", SCOPES)
print("Restart the API: pm2 restart ghostpost-api")
