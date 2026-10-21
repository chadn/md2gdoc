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
| `native Doc` | A Google Docs document (`application/vnd.google-apps.document`), not a `.md` file stored in Drive | - | Google file | domain |
| `push` | Markdown file to Doc: replace the whole Doc with the file's content, same link | - | - | domain |
| `pull` | Doc to markdown file: export the Doc as markdown and normalize it | - | download, fetch | domain |
| `sync` | Pull, three-way merge against the snapshot, then push; the only command that writes both sides | - | - | domain |
| `normalizer` | Reversible rewrite applied to both sides before any comparison, undoing Google's export noise | - | cleaner | domain |
| `snapshot` | Normalized content at the last successful sync, kept in the state file; the merge base | - | baseline, cache | domain |
| `state file` | JSON next to the markdown file: Doc id, link, Drive `version`, snapshot | - | sidecar | domain |
| `api-edited` | Conflict-marker label for the markdown side, the side the script writes; `local` was ruled out | - | ours | domain |
| `hand-edited` | Conflict-marker label for changes made in the Google Docs UI; `doc` was ruled out | - | remote, theirs | domain |
| `#qa-gate` | Work on the QA gate and the evidence it produces: its workflow, script, doctor audit, and every `t_qa` a gated run writes | - | #review-gate | tag |
| QA gate | The independent adversarial examination a change takes before it lands, and the record it leaves; `chadkit/workflows/qa-gate.md` | gate | review gate, QA review, code review gate | project-management |
| light gate | The QA gate's tier for a minor change: the doer's session manages, one reviewer on a cheap language model verifies and answers one validation line; which changes take it is decided by the rules in `chadkit/workflows/qa-gate.md`, never by choice | - | quick review, small gate, lite gate | project-management |
| full gate | The QA gate's tier for a significant change: a judge validates against all goals and the standing questions before the reviewer's findings, on the strongest language model, with a verdict; which changes take it is decided by the rules in `chadkit/workflows/qa-gate.md`, never by choice | - | big gate, deep review, heavy gate | project-management |
| verification | Checking that work was built right: it meets the quality bar and conventions; the reviewer's job in the QA gate | verified | - | project-management |
| validation | Checking that the right work was built: it does the task's intent under the goals; the judge's job in the QA gate | validated | - | project-management |
