# Tasks

- [x] PT-001 [#spike,#migration] Adopt ChadKit: follow the model's bootstrapping sequence (`chadkit model` locates it): inspect what exists, map docs to artifacts, create only what is missing, tool the pain point first, record decisions and terms as they surface. Create goals based on README.md. Close by promotion. Completed: 2026-10-21
- [x] PT-002 [PG-01,PG-02,PG-04] [#spike] AI read/write of native Google Docs: feature breakdown of reading and writing a native Doc from markdown, with pros, cons, and side effects per path; see PT-002.md. Close by promotion. Completed: 2026-10-21
- [ ] PT-003 [PG-02] Create the Google Cloud OAuth desktop client with the `drive.file` scope and save `client_secret.json` outside git, in a new Cloud project owned by md2gdoc (docs/setup.md).
- [ ] PT-004 [PG-01] [needs:PT-003] Prove on a scratch Doc that in-place `files.update` with `text/markdown` keeps the Doc's link, and settle the other two items under docs/design.md "What is not proven".
- [ ] PT-005 [PG-04] Write the normalizer with tests/fixtures/ as its test cases: normalize(out) == normalize(in) for every pair, checkbox state preserved (rules in docs/design.md "Script design").
- [ ] PT-006 [PG-01,PG-02] [needs:PT-004,PT-005] Build the single-file CLI: `init`, `pull`, `push`, `status`, each with `--dry-run`; state file; PEP 723 metadata; `--help` covering setup, files, and exit codes; tests under `tests/`.
- [ ] PT-007 [PG-01] [needs:PT-006] Add `sync`: three-way merge on normalized lines, `api-edited`/`hand-edited` conflict markers with exit 2, Drive `version` push guard with normalized-export comparison, re-pull after push; borrow per docs/design.md "Borrowed pieces".
- [ ] PT-008 [PG-01] [needs:PT-007] First real sync: this repository's chadkit/tasks.md with a Doc the script created; dogfood, decided 2026-10-21.
- [ ] PT-009 [PG-01] [needs:PT-007] Replace whole-document push with targeted Docs API `batchUpdate` edits so comments and formatting on untouched paragraphs survive (PD-001 option C'); first verify a checkbox state can be set by request.
- [x] PT-010 [PG-03] [#qa-gate] Adopt the QA gate: local `chadkit/workflows/qa-gate.md` following the shared user-ck procedure, `scripts/gate-checks.sh`, the config block, and the gate rows in language.md. Completed: 2026-10-21
- [x] PT-011 [PG-03,PG-01,PG-02,PG-04] Rewrite the goals as direction only: adopters named in PG-02, data safety in PG-01, PG-04 aspirational to match the README, Review section dropped in favour of PT-009 under PD-001. Completed: 2026-10-21
- [x] PT-012 [PG-04,PG-02,PG-03] [#docs] Create docs/: features.md (every known feature with its status), similar.md, setup.md, design.md (moved from PT-002.md); fixtures/ moves under tests/; LICENSE; gate paths. Completed: 2026-10-21
- [ ] PT-013 [PG-04] [#spike] Code blocks, single backtick and triple backtick: find a treatment better than not possible; candidates and edge cases in PT-013.md. Close by promotion.
