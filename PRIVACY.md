# Privacy Policy

md2gdoc is an open-source command-line script, [md2gdoc.py](md2gdoc.py), that syncs markdown files with Google Docs.
It runs only on the computer of the person who runs it. There is no md2gdoc server, account, or service; no one
but that person receives any data.

Effective date: 2026-10-22.

## Google data accessed

| What | Details |
|---|---|
| Scope | `https://www.googleapis.com/auth/drive.file` by default; `https://www.googleapis.com/auth/drive` only for a profile you log in with `--scope drive`, to sync Docs the script did not create |
| APIs | Google Drive API and Google Docs API |
| Reach | Under `drive.file`, only Google Docs the script created; no other file in your Google Drive is visible to it. Under `drive`, every file that Google account can open. |
| Read | The content and basic metadata (id, title, version) of those Docs |
| Written | The content of those Docs, replaced or edited to match your markdown files; new Docs the script creates |

## How the data is used

- Solely to sync the content of those Docs with markdown files you choose, at your command or on a schedule you set.
- Never sold, shared, or transferred to anyone.
- Never used for advertising, analytics, profiling, or training AI or machine-learning models.
- Not read by any human except you.

## Where data is stored

On your own computer, or in a repository you keep there:

| File | Contents |
|---|---|
| `client_secret.json`, in a profile folder under your config directory (`~/.config/md2gdoc`, `%APPDATA%\md2gdoc` on Windows, or the folder `MD2GDOC_CONFIG_DIR` names) | The OAuth client from your own Google Cloud project |
| `token.json`, in the same folder | Your OAuth token for the scope you chose |
| Your markdown files and the script's state file beside them | Doc content, Doc ids, and a snapshot used for merging; both go wherever you push that repository |

Data leaves your computer only in requests to Google's APIs, over HTTPS, and in your own pushes of that repository.
Deleting these files deletes everything md2gdoc has stored.

## Revoking access

- Remove md2gdoc at [Google Account > Third-party apps & services](https://myaccount.google.com/connections).
- Delete the profile's `token.json`.

## Google API Services User Data Policy

md2gdoc's use and transfer of information received from Google APIs adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements.

## Contact and changes

Questions: open an issue at [github.com/chadn/md2gdoc/issues](https://github.com/chadn/md2gdoc/issues). Changes to
this policy are made in this file; its git history is the record.
