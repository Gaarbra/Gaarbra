"""Swap a Spotify login code for a refresh token and save it as a repo secret.

Run by .github/workflows/spotify-token.yml, so no local computer is needed.
Reads from the environment:
    REDIRECT_URL           full URL the browser landed on after the login
    EXPECTED_STATE         the state value you put in the login URL
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
    GH_TOKEN, GITHUB_REPOSITORY   used by `gh secret set`
The refresh token is masked in the logs and never printed.
"""

import os
import subprocess
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from get_refresh_token import exchange_code  # noqa: E402


def code_from_redirect(redirect_url, expected_state):
    """Pure: return the auth code from the redirect URL, or raise ValueError."""
    params = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url.strip()).query)
    if params.get("state", [None])[0] != expected_state:
        raise ValueError("state in the URL does not match the state you entered")
    if "error" in params:
        raise ValueError(f"Spotify returned an error: {params['error'][0]}")
    if "code" not in params:
        raise ValueError("no code in the URL (paste the whole address bar)")
    return params["code"][0]


def main():
    try:
        code = code_from_redirect(os.environ["REDIRECT_URL"], os.environ["EXPECTED_STATE"])
    except ValueError as err:
        sys.exit(f"Error: {err}")
    tokens = exchange_code(os.environ["SPOTIFY_CLIENT_ID"],
                           os.environ["SPOTIFY_CLIENT_SECRET"], code)
    refresh_token = tokens["refresh_token"]
    print(f"::add-mask::{refresh_token}")
    subprocess.run(
        ["gh", "secret", "set", "SPOTIFY_REFRESH_TOKEN",
         "--repo", os.environ["GITHUB_REPOSITORY"]],
        input=refresh_token, text=True, check=True)
    print("Saved SPOTIFY_REFRESH_TOKEN to repo secrets.")


if __name__ == "__main__":
    main()
