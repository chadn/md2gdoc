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

## Limits worth knowing

- A Doc created by hand in the Docs UI is outside `drive.file`. Let the script create the Doc with `init`, or use
  the broader `drive` scope, which Google lists as restricted: verification and a security assessment before it
  can be in production.
- Quotas do not matter at any sync cadence: Drive allows 325,000 units per minute per user.

Sources: PT-002.md and design.md "Google API facts"; Google's upload guide,
https://developers.google.com/workspace/drive/api/guides/manage-uploads
