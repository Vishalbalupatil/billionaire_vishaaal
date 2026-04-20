"""Helper for the daily Kite login flow.

Usage:
    python scripts/zerodha_login.py

Opens the login URL for the user, then prompts for the ``request_token`` from
the redirect URL, exchanges it for an access token, and prints it. Paste the
returned token into ``KITE_ACCESS_TOKEN`` in ``.env``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from billionaire.broker.zerodha_client import ZerodhaClient  # noqa: E402


def main() -> int:
    client = ZerodhaClient()
    url = client.login_url()
    print("1) Open this URL in a browser and complete login/2FA:\n", url)
    print("\n2) Zerodha will redirect to your redirect URL with ?request_token=...")
    token = input("\n3) Paste the request_token here: ").strip()
    if not token:
        print("No token entered.")
        return 1
    access = client.generate_session(token)
    print(f"\nAccess token: {access}")
    print("\nAdd this to .env as KITE_ACCESS_TOKEN=...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
