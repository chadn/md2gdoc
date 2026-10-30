# Ubiquitous Language

Terms this project pins down so humans and agents use one word per concept.
The Scope column's valid values are defined in this same table: each is a row whose own Scope is `scope`,
so adding a value means adding its row. For more, see Ubiquitous Language in the ChadKit
model (`chadkit model` says where it is).

| Term | Meaning | Allowed aliases | Avoid | Scope |
|------|---------|-----------------|-------|-------|
| `scope` | Values of the Scope column itself; each value used in this table gets a row like these | - | - | scope |
| `tag` | Task and log record tags; the one scope value tooling interprets - tag rows drive the undefined-tag checks and `language check` tag matching | - | - | scope |
| `domain` | Terms of the project's own subject matter | - | - | scope |
| `project-management` | General methodology terms the project has adopted | - | - | scope |
| `#spike` | A task whose deliverable is knowledge or direction, not a change to materials; closes by promotion into tasks, a log record, a decision, or a goal edit (see Promotion in the ChadKit model, `chadkit model` says where) | - | research, investigation, discovery, planning | tag |
| `#migration` | Adoption of ChadKit into a repository that already has history to consolidate | - | adoption, brownfield, import, onboarding | tag |
| `#docs` | Work on the documents under `docs/` and the README: the feature list, the similar-solutions list, and what a user reads before syncing | - | documentation (as a tag) | tag |
| `native Doc` | A Google Docs document (`application/vnd.google-apps.document`), not a `.md` file stored in Drive | - | Google file | domain |
| `import` | Google's conversion of markdown sent as `text/markdown` into a native Doc, by `files.create` or `files.update`; what it drops or reshapes is the converter's loss | conversion | upload (for the conversion) | domain |
| `push` | Markdown file to Doc, same link: the *edit path* where the diff allows, else the *whole replace* | - | - | domain |
| `edit path` | A push as Docs API requests on the changed paragraphs only, so comments and formatting elsewhere stay (PT-009) | - | targeted edits, hybrid | domain |
| `whole replace` | A push as `files.update` with the file's push form, which re-imports the whole Doc and orphans its comments; the script then carries them over | - | full replace, fallback | domain |
| `pull` | Doc to markdown file: export the Doc as markdown and normalize it | - | download, fetch | domain |
| `pending suggestion` | A change proposed in the Doc's Suggesting mode and not yet accepted or rejected; the export cannot tell it from the text, so `pull`, `sync` and `init --doc` stop while one exists (PT-028) | - | tracked change, suggested edit | domain |
| `attach` | `init FILE --doc ID`: bind a new or empty markdown file to a Doc that exists, writing the state file and a first pull; the only way to sync a Doc the script did not create | - | - | domain |
| `footer` | The three paragraphs at the end of a synced file and its Doc, `md2gdoc sync last change: <date time>`, the file's path from the repository root, the Doc's link; never a change; off with `--no-footer` (PT-034) | - | - | domain |
| `Doc-only change` | A sync or pull where the file has not changed since the last sync and the Doc has; the file keeps its own form and the Doc's changes are carried onto it (PT-034) | - | one-sided pull, Doc-side change | domain |
| `two forms` | The file's form, `local`, the normalized file with its HTML comments and its own shape, and the Doc's form, `snapshot`, the normalized export; never compared, a change on one side is carried onto the other by `replay()` (PT-034) | the file's form, the Doc's form | - | domain |
| `sync` | Pull, three-way merge in the file's form, then push; the only command that writes both sides | - | - | domain |
| `normalizer` | Reversible rewrite applied to both sides before any comparison, undoing Google's export noise | - | cleaner | domain |
| `snapshot` | The Doc's form at the last successful sync, kept in the state file: the normalized export, from which the Doc's changes are read (`two forms`) | - | baseline, cache, merge base | domain |
| `state file` | JSON next to the markdown file: Doc id, link, Drive `version`, snapshot, the file's normalized text at the last sync (`local`, the file's form), and `footer: false` after `--no-footer` | - | sidecar | domain |
| `api-edited` | Conflict-marker label for the markdown side, the side the script writes; `local` was ruled out | - | ours | domain |
| `code run` | A Doc paragraph of monospace lines, one per code line, standing in for a fenced code block; a push sends one, a pull folds it back into a fence | - | monospace block, code paragraph | domain |
| `push form` | The markdown the script sends to Google in place of the file: the file plus the rewrites that keep Google's import from losing content (code runs, entity indents); never written back to the file | - | wire format, upload form | domain |
| `profile` | One folder under the config directory, named for a Google account, holding that account's `client_secret.json` and `token.json`; the token remembers the scope chosen at the first login; picked by `--account NAME` or `MD2GDOC_ACCOUNT`, else `default` | account profile | credentials set | domain |
| `config directory` | The per-user folder holding every profile: `MD2GDOC_CONFIG_DIR`; else `%APPDATA%\md2gdoc` on Windows; else `$XDG_CONFIG_HOME/md2gdoc` or `~/.config/md2gdoc`; never inside a repository | - | settings folder, dotfolder | domain |
| `hand-edited` | Conflict-marker label for changes made in the Google Docs UI; `doc` was ruled out | - | remote, theirs | domain |
| `#qa-gate` | Work on the QA gate and the evidence it produces: its workflow, script, doctor audit, and every `t_qa` a gated run writes | - | #review-gate | tag |
| `#outcome` | A `t_qa` record of how a task turned out in use, opening with good, mixed or bad; evidence for verdict calibration at the next double-loop review, never counted as a gate run (the shared qa-gate workflow, Outcomes) | - | result, retrospective | tag |
| `#source-links` | Records about an assertion in `.md` prose that names no linked source: the feedback on it, each gate finding confirming it and each `t_qa` whose findings include one; a tracked issue of the documentation focus (Q-sources in user-ck's `chadkit/workflows/docs-gate.md`) | - | citations, references (as a tag) | tag |
| `#exec-summary` | Records about an executive summary that misses its bar: the feedback on it, each gate finding confirming it and each `t_qa` whose findings include one; a tracked issue of the documentation focus (Classes in user-ck's `chadkit/workflows/docs-gate.md`) | - | summary, TL;DR (as a tag) | tag |
| QA gate | The independent adversarial examination a change takes before it lands, and the record it leaves; `chadkit/workflows/qa-gate.md` | gate | review gate, QA review, code review gate | project-management |
| light gate | The QA gate's tier for a minor change: the doer's session manages, one reviewer on a cheap language model (on the documentation focus's model when the change takes that focus) verifies and answers one validation line; which changes take it is decided by the rules in [chadkit/workflows/qa-gate.md](workflows/qa-gate.md), never by choice | - | quick review, small gate, lite gate | project-management |
| full gate | The QA gate's tier for a significant change: a judge validates against all goals and the standing questions before the reviewer's findings, on the strongest language model, with a verdict; which changes take it is decided by the rules in `chadkit/workflows/qa-gate.md`, never by choice | - | big gate, deep review, heavy gate | project-management |
| documentation focus | The QA gate's focus for prose a reader acts on, run by user-ck's `chadkit/workflows/docs-gate.md` at the revision `workflows.docs-gate.from` names, on the language model that file names, by the agent `docs-gate-reviewer`; which changes take it is that file's rule, with this repository's parts under Documentation in [chadkit/workflows/qa-gate.md](workflows/qa-gate.md) | documentation gate | docs gate, docs review, prose review | project-management |
| tracked issue | A documentation defect Chad follows across his projects as a tag, carried by every record about it, so its trend can be counted; the tags are the `tag` rows that say so | - | known issue, recurring finding | project-management |
| verification | Checking that work was built right: it meets the quality bar and conventions; the reviewer's job in the QA gate | verified | - | project-management |
| validation | Checking that the right work was built: it does the task's intent under the goals; the judge's job in the QA gate | validated | - | project-management |
