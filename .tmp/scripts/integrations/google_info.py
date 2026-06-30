"""
google_info.py — Fetch Google Docs/Sheets file metadata.

Usage:
    python scripts/integrations/google_info.py --file-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
    python scripts/integrations/google_info.py --file-id "<id>" --output .tmp/project/google_info.json

Requires either:
  - GOOGLE_SERVICE_ACCOUNT_JSON=path/to/service_account.json in .env, OR
  - A google_token.json created via: python scripts/integrations/google_auth.py --setup
"""

import argparse
import json
import os
from pathlib import Path

from load_env import load_env; load_env()

SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]


def get_credentials():
    """Return Google credentials from service account or OAuth token."""
    sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_path and Path(sa_path).exists():
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)

    token_path = Path("scripts/integrations/google_token.json")
    if token_path.exists():
        from google.oauth2.credentials import Credentials

        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        return creds

    raise EnvironmentError(
        "No Google credentials found. Set GOOGLE_SERVICE_ACCOUNT_JSON in .env "
        "or run: python scripts/integrations/google_auth.py --setup"
    )


def get_file_metadata(file_id: str) -> dict:
    from googleapiclient.discovery import build

    creds = get_credentials()
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    file = (
        service.files()
        .get(
            fileId=file_id,
            fields="id,name,mimeType,modifiedTime,createdTime,webViewLink,owners,size",
        )
        .execute()
    )

    return {
        "file_id": file.get("id"),
        "name": file.get("name"),
        "mime_type": file.get("mimeType"),
        "url": file.get("webViewLink"),
        "created_time": file.get("createdTime"),
        "modified_time": file.get("modifiedTime"),
        "owners": [o.get("emailAddress") for o in file.get("owners", [])],
        "size_bytes": file.get("size"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Google Drive file metadata")
    parser.add_argument("--file-id", required=True, help="Google Drive file ID")
    parser.add_argument("--output", default=None, help="Path to save JSON output")
    args = parser.parse_args()

    result = get_file_metadata(args.file_id)
    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
