# Setup

One-time steps before the first sync. Everything a human must do is here; what the script does on first run is at
the end. The CLI's `--help` will repeat the short form once PT-006 writes it.

## 1. Google Cloud project

1. In the Google Cloud console create a project for this tool (PT-003 creates this repository's own; any Google
   account can make its own).
2. Enable the **Google Drive API**. The Docs API is not needed for whole-document sync.

## 2. OAuth consent screen

1. User type **External**.
2. Add one scope: `https://www.googleapis.com/auth/drive.file`. The script can then see only files it created;
   nothing else in Drive is reachable.
3. Set publishing status to **In production**. `drive.file` is a non-sensitive scope, so no Google verification is
   needed. Left in **Testing**, refresh tokens expire after 7 days and you log in through a browser every week.

## 3. Credentials

1. Create an OAuth client ID of type **Desktop app**.
2. Download its JSON as `client_secret.json` next to the script.
3. Keep `client_secret.json` and the generated `token.json` out of git; the repository's `.gitignore` already
   lists both.

## 4. First run

The first command that needs Google opens a browser once (`InstalledAppFlow.run_local_server`), then the cached
`token.json` refreshes itself. No further human step unless the token is revoked.

## Two kinds of Google access

Two different credentials touch this project's Docs; do not confuse them.

- **The Google Drive connector on a claude.ai account.** Authorised once in claude.ai settings; Anthropic holds the
  OAuth grant and every Claude session on that account gets Drive tools from it. Nothing is stored in this
  repository or on disk. This is what created the Docs behind `tests/fixtures/` and what a spike uses to probe
  Google's converter without any setup. It cannot replace a Doc's content in place, exists only inside a Claude
  session, and carries whatever scope was granted at claude.ai.
- **The script's own OAuth client**, the steps above. Needed for everything from PT-004 onward: in-place update
  on one link, unattended runs with no Claude involved, and the narrow `drive.file` scope. Its `client_secret.json`
  and `token.json` live next to the script and stay out of git.

A Doc the connector created is invisible to the script under `drive.file`, and the reverse; each path sees only
what it made.

## Limits worth knowing

- A Doc created by hand in the Docs UI is outside `drive.file`. Let the script create the Doc with `init`, or use
  the broader `drive` scope, which Google lists as restricted: verification and a security assessment before it
  can be in production.
- Quotas do not matter at any sync cadence: Drive allows 325,000 units per minute per user.

Sources: PT-002.md and design.md "Google API facts"; Google's upload guide,
https://developers.google.com/workspace/drive/api/guides/manage-uploads
