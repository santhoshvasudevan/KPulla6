# Doc page templates

Reusable patterns for MkDocs pages. Inspired by Stripe (API), Tailwind (example + result), Vercel (Next/Related), and Supabase (quickstart success criteria).

**When to update docs:** [Documentation update policy](documentation-update-policy.md) · **Which bucket:** tutorial, how-to, concept, reference, troubleshooting, changelog, decisions, or maintenance.

## Writing style

- Short sentences. One purpose per page.
- Copy-paste commands; show **expected output** when it helps verification.
- Link to deep specs (`api-design.md`, `product-rules.md`) — do not duplicate long tables.
- No marketing language.
- Screenshots only when they explain a workflow — [visual backlog](docs-visual-backlog.md).

---

## 1. Tutorial page

```markdown
# [Task title]

One-line goal.

## Prerequisites
- Commands + links

## Steps
### 1. ...
### 2. ...

## You are done when…
- [ ] Observable success criterion

## Troubleshooting
- Link near likely failure

## Next
- Next tutorial

## Related
- Concept or reference link
```

---

## 2. How-to page

```markdown
# [Problem title]

## Use this when
- Bullet conditions

## Before you start
- Preconditions

## Steps
1. ...

## Verify
- Command + expected output

## Related
- Deep spec links
```

---

## 3. API reference page

```markdown
# [Resource name]

## Base URL
http://127.0.0.1:8000/api/v1

## [METHOD] /path

**Auth:** Session | Public

### Parameters
| Name | In | Required | Description |

### Example request
\`\`\`bash
curl ...
\`\`\`

### Example response
\`\`\`json
{ }
\`\`\`

### Errors
| Status | When |

### Deep spec
Link to api-design.md § section
```

---

## 4. Troubleshooting page

```markdown
# [Symptom]

## Symptom
What the user sees.

## Likely causes
- Bullet list

## Quick checks
\`\`\`bash
command
\`\`\`
**Expected:** ...

## Fix
Steps.

## Verify
How to confirm resolved.

## Related
- Links
```

---

## Visual placeholders

When a UI example helps, use:

```markdown
!!! note "Screenshot placeholder"
    **Capture:** Short description
    **Shows:** What the reader should see
    **Backlog:** [Docs visual backlog](docs-visual-backlog.md)
```

---

## Related

- [Documentation update policy](documentation-update-policy.md)
- [Docs consistency checks](docs-consistency-checks.md)
- [Docs visual backlog](docs-visual-backlog.md)
