"""Gmail OAuth2 credential management."""

import json
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from src.config import settings

logger = logging.getLogger("ghostpost.gmail.auth")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_credentials() -> Credentials:
    """Load OAuth2 credentials from token.json, refreshing if expired."""
    token_path = settings.GMAIL_TOKEN_FILE

    with open(token_path) as f:
        token_data = json.load(f)

    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        logger.info("Refreshing expired Gmail token")
        creds.refresh(Request())
        # Save refreshed token
        with open(token_path, "w") as f:
            json.dump(json.loads(creds.to_json()), f)
        logger.info("Token refreshed and saved")

    return creds
