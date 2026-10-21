# Project log

### PLR-20261021-01 t_feedback [PT-002,PT-003,PT-009,PD-001,PG-01,PG-02,PT-004,PT-005,PT-006,PT-007,PT-008] Direction for the sync script

- Date: 2026-10-21
- Source: Chad, during PT-002 (the Direction section of PT-002.md)
- Summary: Build an own script for two-way sync of a task list where either side can add, edit, or complete tasks; reusable by other projects with --help and in-file comments; conflict markers are api-edited and hand-edited, never local or doc; whole-document replace for v1 with targeted edits later; a new Cloud project owned by md2gdoc holds the OAuth client. The spike closed by promotion into PT-003 to PT-009 and PD-001.
- Related: PG-01, PG-02, PD-001
- Action: PT-003, PT-004, PT-005, PT-006, PT-007, PT-008, PT-009

### PLR-20261021-02 t_qa [PT-002,PG-01,PG-02,PG-04,PT-009,PD-001,PLR-20261021-01,PT-001,PT-007,PT-006] Full gate on the ChadKit adoption and the PT-002 spike

- Date: 2026-10-21
- Summary: 4 confirmed, 0 refuted, 3 declined; judge and reviewer claude-fable-5-1, full tier; gate user-ck@f95f135; session 2a707704-fea6-44bc-80be-8bbbde1bdf6f. Double-loop: the right thing was built as scoped; the doubt was the record, not the work. Applied: PT-002 now cites PG-01, PG-02, PG-04; traces of a document outside this repository removed from PT-002.md and the native-only rule written as a config override; C-prime spelled C' in PT-009; Auth setup step 1 and the assumptions list updated to the decided project and PD-001; README's trailing blank line restored; ours, theirs and remote restored to the Avoid column of the marker labels. Declined: task ids renumbered within the branch (the owner asked for this history to be rewritten before any merge and nothing on main cites the old numbering); PLR-20261021-01 rewritten rather than appended (same instruction; the earlier text sits in main's first commit, the owner's to amend); README's 'everything markdown can do' contradicts PG-04 and fixture 01 (the owner wrote it and was told; owner's call). Verdict, judged by claude-fable-5-1: Verification 70 (validate clean, doctor 2 allowed notes, findings 1-3 confirmed against the model's Tasks, Log and Ubiquitous Language); Validation, task intent 85 (PT-002 line met in PT-002.md; PT-001 met; both cited no goal, applied first); Validation, goals PG-01 90 (PT-007 conflict exit 2, tick wins in Script design), PG-02 85 (drive.file, PEP 723, --help in PT-006), PG-04 75 (fixture 01 pins code loss; README.md:8 says otherwise); Consistency 65 (reuses the model's spike-promotion shape; departs from id stability and append-only log, findings 1 and 3); Score 76
- Related: PT-001, PT-002
- Tags: #qa-gate

