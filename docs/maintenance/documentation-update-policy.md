# Documentation update policy

Docs are part of the definition of done. Every feature, bug fix, API change, UI change, workflow change, or architecture change must **explicitly decide** whether documentation needs updates.

**Canonical policy:** this page. Agents and contributors should read it before shipping work.

---

## 1. Definition of done — docs decision

Before finishing any task, state one of:

- **Docs updated:** list files or sections changed (e.g. `docs/changelog.md`, `docs/reference/api-transactions.md`).
- **Docs not needed because:** one-line reason (e.g. internal refactor, no contract or user-visible change).

Do not skip this decision silently.

---

## 2. Diátaxis buckets — where updates belong

| Bucket | Use for | Typical paths |
|--------|---------|---------------|
| **Tutorial** | First-time learning, end-to-end beginner path | `docs/tutorials/` |
| **How-to** | One practical task or operational workflow | `docs/how-to/` |
| **Concept** | Why the system works this way | `docs/concepts/` |
| **Reference** | Exact facts — APIs, fields, commands, env vars, CSV, schema | `docs/reference/`, `docs/api-design.md`, `docs/database.md` |
| **Troubleshooting** | Symptom → cause → fix → verify | `docs/troubleshooting/` |
| **Changelog** | Dated user-visible or developer-relevant change | `docs/changelog.md` |
| **Decisions** | Durable architecture or product trade-off | `docs/decisions.md`, `docs/decisions/` |
| **Maintenance** | Agent workflow, docs rules, release checklist, audits | `docs/maintenance/` |

Add new pages to `mkdocs.yml` nav when they are reader-facing. Run `make docs-check` after nav changes.

Deep specs stay in place (`api-design.md`, `cash-ledger.md`, `product-rules.md`). Reference pages summarize and link — do not duplicate long tables.

---

## 3. Change type → documentation map

| Change | Update these (as applicable) |
|--------|------------------------------|
| **New API endpoint or changed response shape** | `docs/reference/api-*.md` · `docs/api-design.md` · `docs/changelog.md` · tests must cover contract |
| **New backend model, field, migration, or cache behavior** | `docs/reference/database-schema.md` or `docs/database.md` · `docs/concepts/*` if behavior changes · `docs/decisions.md` if durable trade-off · `docs/changelog.md` |
| **New frontend page or major UI behavior** | `docs/tutorials/*` or `docs/how-to/*` · `docs/reference/frontend-routes.md` · [visual backlog](docs-visual-backlog.md) if a screenshot helps · `docs/changelog.md` |
| **New Makefile command or workflow** | `docs/reference/make-commands.md` · `docs/how-to/*` if task-oriented · `README.md` if quickstart changes · `docs/changelog.md` |
| **New CSV / import format** | `docs/reference/csv-formats.md` · tutorial or how-to if user-facing · `docs/api-design.md` if API contract changed · `docs/changelog.md` |
| **New financial / accounting rule** | `docs/concepts/*` · `docs/decisions.md` · reference or database docs if fields changed · `docs/changelog.md` |
| **New data-safety rule** | `AGENTS.md` · `docs/concepts/data-safety.md` · `docs/troubleshooting/*` · `docs/changelog.md` |
| **Bug fix** | `docs/changelog.md` if user-visible or important · troubleshooting page if it prevents recurrence · fix affected reference or concept page if docs were wrong |

When unsure, prefer a short changelog line plus a link to the deep spec.

---

## 4. Final response checklist (agents / Cursor)

End every implementation task with:

| Item | Report |
|------|--------|
| **Code changed** | Files created / updated / deleted |
| **Tests run** | Commands + pass/fail (or skipped — docs-only) |
| **Docs** | **Docs updated:** … **or** **Docs not needed because:** … |
| **Data safety** | Confirm no destructive DB ops on live dev data (or what was approved) |
| **Follow-up** | Deferred items, screenshots, migrations to run, etc. |

Background agents in `docs/backlog/` also report `git diff --stat` and commit hash when applicable. See root `AGENTS.md`.

---

## 5. Validation

| Change type | Run |
|-------------|-----|
| Docs or nav only | `make docs-build` · `make docs-check` |
| Code + docs | Relevant code tests **plus** `make docs-check` |
| API contract | `make docs-check` (cross-checks `api-design.md` vs Django urls) |

**Expected:** `docs-check: OK`

Details: [Docs consistency checks](docs-consistency-checks.md)

---

## 6. Writing style

- Short sentences. One purpose per page.
- Copy-paste commands with **expected output** where it helps verification.
- Link to deep specs instead of duplicating long details.
- No marketing language.
- Screenshots only when they explain a workflow — see [visual backlog](docs-visual-backlog.md).
- Use [doc page templates](doc-page-templates.md) for structure.

---

## Related

- [Cursor maintenance workflow](cursor-maintenance-workflow.md)
- [Release checklist](release-checklist.md)
- [Audit docs vs code](../how-to/audit-docs-vs-code.md)
- Root contributor rules: [agents.md](../agents.md) (canonical `AGENTS.md` at repository root)
