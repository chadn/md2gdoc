# Setup

One-time Google Cloud steps before the first sync. The *Recommended setup* comes first; why it looks this way, the
other setups, and a reference of every relevant scope follow. Claims marked **To verify:** are not yet tested; the
full list is in [To verify](#to-verify).

## Recommended setup

Your main Google account, the `drive.file` scope. The script can reach only the Docs it created; nothing else in your
Drive is visible to it.

1. Create a project: [console.cloud.google.com/projectcreate](https://console.cloud.google.com/projectcreate).
   Name it `md2gdoc`, or anything.
2. Enable two APIs: [enable Drive API](https://console.cloud.google.com/flows/enableapi?apiid=drive.googleapis.com)
   and [enable Docs API](https://console.cloud.google.com/flows/enableapi?apiid=docs.googleapis.com). Drive reads
   and writes whole Docs; the Docs API edits part of one (PT-009) and costs nothing to enable now.
3. Configure consent: [Google Auth platform > Branding](https://console.cloud.google.com/auth/branding). If it says
   the platform is not configured yet, click **Get started**:
   - App name `md2gdoc`, your email as support email, **Next**.
   - Audience **External**, **Next**. **Internal** appears only for Google Workspace accounts; see
     [Internal app](#internal-app-for-a-google-workspace-account).
   - Your email as contact, **Next**, agree to the User Data Policy, **Continue**, **Create**.
4. Check [Branding](https://console.cloud.google.com/auth/branding) has **App name**, **User support email**,
   **Developer contact information** and a **Privacy policy** link filled in, then **Save**. The privacy link must
   be a public page; this repository's is [PRIVACY.md](../PRIVACY.md) at its GitHub URL. **Publish app** in step 6
   stayed greyed out until the privacy link was saved, with the other three fields already filled (2026-10-22;
   Google's pages do not say so, they list the link only as needed to submit for verification). Leave the logo
   empty: a logo on a published external app triggers brand verification (Google's page lists the display name
   too; an unverified app still shows its name on the consent screen).
5. Add the scope: [Data Access](https://console.cloud.google.com/auth/scopes) > **Add or remove scopes** >
   **Manually add scopes** > paste `https://www.googleapis.com/auth/drive.file` > **Add to table** > **Update** >
   **Save**.
6. Publish: [Audience](https://console.cloud.google.com/auth/audience) > **Publish app** > **Confirm**. Status becomes
   **In production**, so the token does not expire weekly. If **Publish app** is greyed out, go back to step 4,
   save the Branding form, and reload the Audience page; everything still works in Testing meanwhile, with the
   weekly login described under [Testing status](#testing-status). A token issued while in Testing keeps its
   7-day expiry: delete `token.json` after publishing and sign in once more.
7. Create the client: [Clients](https://console.cloud.google.com/auth/clients) > **Create client** > type
   **Desktop app** > **Create**. Download the JSON from the dialog right away and save it as `client_secret.json`
   next to [md2gdoc.py](../md2gdoc.py).
8. First run: the first command that needs Google opens a browser; sign in and allow. The consent screen names
   the one scope and may carry a notice about not seeing links to a Privacy Policy, which does not block
   **Continue**. The
   token is cached in `token.json` and refreshes itself. Let the script create each Doc; `drive.file` cannot see
   Docs made by hand.

`client_secret.json` and `token.json` stay out of git; [.gitignore](../.gitignore) lists both.

## Why the recommended setup looks this way

| Choice | Why | Alternative |
|---|---|---|
| Drive API and Docs API | Drive reads and writes whole Docs (`files.export`, `files.update`), creates and finds them; Docs edits part of a Doc, see [Docs API](#docs-api) | Drive alone, if targeted edits are never wanted |
| `drive.file` | Narrowest scope that can write; non-sensitive, so no Google verification | `drive`, see [Other setups](#other-setups) |
| OAuth Desktop app client | Script runs on your machine, one browser login, then unattended | Service-account setup |
| External + In production | Testing status expires the token after 7 days; `drive.file` needs no verification to publish | Internal for Workspace accounts; [Testing status](#testing-status) |
| Main account | Docs are owned by you and stay in your Drive; simplest | Secondary-account setup |
| Script creates each Doc | `drive.file` cannot see a Doc made by hand in the Docs UI | Secondary-account setup, Service-account setup |

## Other setups

Each one trades the recommended setup's narrow reach for something it cannot do: open Docs made by hand, run
without a consent screen, or skip publishing. The table compares every combination; the sections below give steps
for the ones worth running. The script itself requests `drive.file` through the desktop flow and nothing else yet,
so the secondary-account and service-account setups need a script option that no task owns (the `idea` row in
[features.md](features.md)); their console steps are written down so that option has a path to follow.

| Setup | Docs reachable | Hand-made Docs | Verification | Consent screen | If `token.json` leaks |
|---|---|---|---|---|---|
| Recommended setup (main, `drive.file`) | Docs the script created | No | None | Normal | Those Docs only |
| Secondary-account setup (secondary, `drive`) | Everything shared with secondary | Yes, once shared | Unverified, allowed | Unverified warning | All Docs shared with it |
| Main account, `drive` | Every file in your Drive | Yes | Unverified, allowed | Unverified warning | Your whole Drive |
| Main account, `documents` (Docs API only) | Every Google Doc you can open | Yes | Unverified, allowed | Unverified warning | All your Docs |
| Service-account setup | Everything shared with the service account | Yes, once shared | None | None | All Docs shared with it; key never expires |
| Internal (Workspace), any scope | Per scope | Per scope | None | Normal | Per scope |
| Testing status, any of the above | Same | Same | None | Unverified warning | Same; token dies after 7 days |

### *Secondary-account setup*

For syncing Docs made by hand. A separate Google account used only by md2gdoc, with the broad `drive` scope. The
scope reaches everything that account can open, which is only what you share with it.

Differences from the Recommended setup:

1. Create a Google account for md2gdoc, e.g. a new Gmail address.
2. Step 5: add `https://www.googleapis.com/auth/drive` instead of `drive.file`.
3. Step 6: publish anyway. `drive` is a restricted scope, so the consent screen shows **Google hasn't verified this
   app**; click **Advanced** > **Go to md2gdoc (unsafe)**. Unverified apps are capped at 100 users for the project's
   lifetime, irrelevant for one person.
4. Share each Doc to sync from your main account with the secondary account as **Editor**.
5. Step 8: sign in as the secondary account, not your main one. A private browser window avoids picking the wrong
   account.

Side effects:

- Pushes show the secondary account's name in the Doc's version history.
- Docs the script creates are owned by the secondary account; share them with your main account.
- Unsharing a Doc revokes the script's access to it.
- Any Doc set to "anyone with the link can edit" is writable by the script if it has the Doc's id.

### Internal app for a Google Workspace account

An Internal app can be authorized only by accounts in one Google Workspace organization, such as a company domain.
The option appears only when the Cloud project belongs to that organization; a personal `@gmail.com` account
cannot use it.

If you have one, pick **Internal** in step 3 and skip step 6. Internal apps have no 7-day token expiry, no
verification, and no unverified-app screen, for any scope.

### Testing status

Skip step 6 and leave the app in **Testing**. It works for any account listed as a test user:

1. [Audience](https://console.cloud.google.com/auth/audience) > **Test users** > **Add users** > the exact email you
   will sign in with in step 8 > **Save**.
2. Signing in with any other account fails with an access-denied error.

Test users see a "Google hasn't verified this app" screen before the consent screen; **Continue** is the right
button. Once the app is published that screen is gone and only two remain: the account picker and the consent
screen (both seen 2026-10-22).

Cost: Google ends a test user's authorization 7 days after consent, refresh token included, so step 8's browser
login repeats every week. Fine for trying things out; not for unattended runs.

### *Service-account setup*

A service account is a robot identity owned by the Cloud project. No consent screen, no Branding, no publishing,
no token expiry; it reaches only Docs shared with its email.

1. Do steps 1 and 2 of the Recommended setup; skip steps 3 to 8.
2. [Service accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) > **Create service account** >
   name `md2gdoc` > **Create and continue** > skip roles > **Done**.
3. Open it > **Keys** > **Add key** > **Create new key** > **JSON**. Save the file next to
   [md2gdoc.py](../md2gdoc.py) and add its name to [.gitignore](../.gitignore).
4. Share each Doc with the service account's email (`md2gdoc@<project-id>.iam.gserviceaccount.com`) as **Editor**.

Side effects:

- The JSON key never expires; anyone holding it can edit every Doc shared with the account. Delete the key in the
  console to revoke.
- Pushes show the service account's name in the Doc's version history.
- If **Add key** is refused, the project sits under an organization whose policy
  `iam.disableServiceAccountKeyCreation` blocks keys; override it for the project or use another setup.
- A service account has no Drive storage of its own (community reports say none at all for accounts created
  after April 2025), so it cannot create Docs in a personal Drive; create them as a person and share them.
  **To verify:** updating a shared Doc counts against the owner's quota, so the push still works.
- **To verify:** a Doc owned by a personal Gmail account can be shared with a service account email without
  errors.

### Docs API

Enabled in step 2; needed only to edit part of a Doc instead of replacing all of it (`documents.batchUpdate`,
PT-009). It works with every setup above.

- `batchUpdate` accepts `drive.file`: Google's Docs API scopes page lists it as non-sensitive and recommended, so
  no scope change is needed. Confirmed 2026-10-22 with an insert on a scratch Doc under this project's client.
- The Docs API's own scope `documents` reads and edits every Google Doc the account can open, by id. Drive calls
  (`files.export`, `files.update`, finding Docs by name) reject it, so it suits a Docs-API-only script.
  It is sensitive: publishing shows the unverified-app screen, like `drive`.
- A `drive` scope on your main account works with both APIs, but a leaked `token.json` exposes every file in your
  Drive.

## Reference

### Scopes that can read or write a Doc

| Scope | API | Read Doc | Write Doc | Reach | Tier | Fit for two-way sync |
|---|---|---|---|---|---|---|
| `drive.file` | Drive, Docs | Yes | Yes | Files the app created, or opened with it via Picker / "Open with" | Non-sensitive | Yes, recommended |
| `drive` | Drive, Docs | Yes | Yes | Every file the account can open; also share, move, delete | Restricted | Yes, Secondary-account setup |
| `drive.readonly` | Drive, Docs | Yes | No | Every file the account can open | Restricted | No, cannot write |
| `documents` | Docs | Yes | Yes | Every Google Doc the account can open | Sensitive | Only with Docs API calls; Drive calls reject it |
| `documents.readonly` | Docs | Yes | No | Every Google Doc the account can open | Sensitive | No |
| `drive.metadata`, `drive.metadata.readonly` | Drive | No | No | Names, ids, timestamps; no content | Restricted | No |
| `drive.appdata` | Drive | No | No | A hidden app-private folder only | Non-sensitive | No |

Tiers decide whether Google verification is needed; an unverified app with a sensitive or restricted scope shows
the warning to every user, you included:

- **Non-sensitive:** publish freely.
- **Sensitive:** Google verification, or the unverified-app screen and the 100-user cap.
- **Restricted:** verification plus an annual security assessment if the data reaches your servers, or the
  unverified-app screen and the 100-user cap.

### Two kinds of Google access

Two different credentials touch this project's Docs; do not confuse them.

| | Google Drive connector on claude.ai | The script's own OAuth client |
|---|---|---|
| Set up | Once, in claude.ai settings | The steps above |
| Grant held by | Anthropic | `token.json` next to the script |
| Runs | Only inside a Claude session | Anywhere, unattended |
| Updates a Doc in place | No; every write is a new file and link | Yes |
| Used for | The Docs behind [tests/fixtures/](../tests/fixtures/); probing Google's converter in a spike | Everything the script does |

Under `drive.file` each path sees only what it created: a Doc the connector made is invisible to the script, and the
reverse.

### Limits worth knowing

- A Doc created by hand in the Docs UI is outside `drive.file`; let the script create it, or use the
  Secondary-account setup or Service-account setup.
- Quotas do not matter at any sync cadence: Drive allows 325,000 units per minute per user; the Docs API allows 60
  writes per minute per user.
- The console shows a client secret only at creation; if it is lost, **Add Secret** on the client's page makes a
  new one (at most two at a time).

### To verify

Every **To verify:** claim in this file, for whoever tests them. Remove a line once tested, and fix the text it
points to if the test disagrees.

- [Recommended setup](#recommended-setup) step 6: the token issued on 2026-10-22 under In production still
  refreshes after 2026-10-29, which is the 7-day mark.
- [Service-account setup](#service-account-setup): updating a shared Doc counts against the owner's quota.
- [Service-account setup](#service-account-setup): a personal Gmail account can share a Doc with a service account.

### Sources

- Drive scopes and tiers:
  [Choose Google Drive API scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- Docs scopes: [Choose Google Docs API scopes](https://developers.google.com/workspace/docs/api/auth)
- Testing expiry, publishing, 100-user cap, Internal:
  [Manage App Audience](https://support.google.com/cloud/answer/15549945)
- Logo and links: [Submit for brand verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification)
- Service-account storage: [Fivetran, service accounts have no storage quota](https://fivetran.com/docs/activations/destinations/available-destinations/google-drive/troubleshooting/service-accounts-storage-quota);
  the April 2025 date: [an n8n community thread](https://community.n8n.io/t/upload-file-google-drive-node-with-service-account-not-working/147750)
- Client secrets: [Setting up OAuth 2.0](https://support.google.com/cloud/answer/6158849)
- Console steps: [Docs API Python quickstart](https://developers.google.com/workspace/docs/api/quickstart/python)
- Upload and convert: [Drive upload guide](https://developers.google.com/workspace/drive/api/guides/manage-uploads)
- Docs API quotas: [Docs API usage limits](https://developers.google.com/docs/api/limits)
- Project evidence: [design.md](design.md) "Google API facts"
