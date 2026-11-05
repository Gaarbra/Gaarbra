# Spotify minutes badge setup

The badge shows all-time listening minutes: a baseline from your Spotify data export plus plays tracked every hour by `.github/workflows/spotify.yml`. Everything below runs in a browser. No local setup is needed except step 7.

## 1. Request your extended streaming history

1. Go to your Spotify account's Privacy settings page (spotify.com, Account, Privacy settings).
2. Check **Extended streaming history** and request the data.
3. Confirm the request from the email Spotify sends. The export can take a few weeks to arrive. The hourly workflow can run in the meantime.

## 2. Create the Spotify developer app

1. Sign in at https://developer.spotify.com/dashboard and create an app.
2. Add this redirect URI exactly: `http://127.0.0.1:8888/callback`
3. Select **Web API** as the API used.
4. Open the app settings and copy the **Client ID** and **Client secret**.

## 3. Add the first repo secrets

In this repo on GitHub: **Settings, Secrets and variables, Actions, New repository secret**. Add:

| Name | Value |
|---|---|
| `SPOTIFY_CLIENT_ID` | Client ID from step 2 |
| `SPOTIFY_CLIENT_SECRET` | Client secret from step 2 |
| `SECRETS_PAT` | A personal access token (see below) |

To make `SECRETS_PAT`: GitHub **Settings, Developer settings, Personal access tokens, Fine-grained tokens, Generate new token**. Set repository access to only `Gaarbra/Gaarbra` and give it the repository permission **Secrets: Read and write**. This lets the token workflow save the refresh token for you.

## 4. Log in to Spotify

Pick any random word as your state (for example `kettle8391`). Put your client ID and state into this URL and open it in a browser:

```
https://accounts.spotify.com/authorize?response_type=code&scope=user-read-recently-played&redirect_uri=http%3A%2F%2F127.0.0.1%3A8888%2Fcallback&client_id=YOUR_CLIENT_ID&state=YOUR_STATE
```

Approve the login. The browser then tries to open `http://127.0.0.1:8888/callback?code=...` and shows a "can't connect" page. That is expected. Copy the whole URL from the address bar. Do the next step right away, because the code expires quickly and works only once.

## 5. Save the refresh token

Open the **Actions** tab, pick **Spotify token (one time)**, click **Run workflow**, paste the URL into `redirect_url` and your state word into `state`. When it finishes, `SPOTIFY_REFRESH_TOKEN` appears in your repo secrets. The token is masked in the logs.

If the run fails, repeat step 4 for a fresh code. You can delete `SECRETS_PAT` afterwards. You'll only need it again if you ever redo this step.

Alternative: if you'd rather do steps 4 and 5 on your own computer, run `python scripts/get_refresh_token.py` and add the printed token as the `SPOTIFY_REFRESH_TOKEN` secret yourself.

## 6. Run the minutes workflow

Open the **Actions** tab, pick **Spotify minutes**, and click **Run workflow**. After that it runs every hour at minute 17 and commits only when the minutes change.

Note: Spotify's recently played endpoint returns at most the last 50 tracks, so hourly runs are needed to catch everything. It reports full track length, not the exact time you listened.

## 7. When the export arrives

Unzip it and run:

```bash
python scripts/parse_history.py "path/to/Spotify Extended Streaming History"
```

It prints total minutes, minutes by year and your top 5 artists, then saves the baseline to `data/state.json`. Plays the workflow already tracked that the export also covers are dropped, so nothing is counted twice. Commit and push `data/state.json`. The next workflow run updates the badge.
