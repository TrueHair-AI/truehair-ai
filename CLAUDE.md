# Claude Code instructions for this repo

These rules apply to every worktree of this repo. Per-developer overrides
belong in `CLAUDE.local.md` (untracked).

## Use the repo's PR and issue templates

Before opening a PR or issue, read the matching template under `.github/`
and structure the body around its sections **verbatim** — same headings,
same order, same checklist items. Filling in the template is not optional.

### Pull requests

- Template: [.github/pull_request_template.md](.github/pull_request_template.md)
- Required sections (in order): `## Description`, `## Related Issues`,
  `## Changes Made`, `## Testing & Verification`, `## Checklist`
- The four checklist items at the bottom are the ones in the template —
  do not invent new ones, do not omit items. Tick the ones that apply.
- In `## Related Issues`, use `Closes #123` / `Fixes #123` so the issue
  auto-closes on merge.
- Do **not** use `gh pr create --fill`. `--fill` populates the body from
  commits and silently bypasses the template. Use `gh pr create --body
  "$(cat <<'EOF' ... EOF)"` with the full template body instead.

### Issues

- Forms live in [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/) (`bug_report.yml`,
  `feature_request.yml`). Pick the one that matches and fill in every field
  the form declares — don't author free-form issues.
- For `gh issue create`, pass `--template bug_report.yml` (or
  `feature_request.yml`) so the form is honored.

## Why this rule exists

Templates are the contract reviewers and triagers rely on. PRs that skip
sections (e.g. omitting the test plan or the self-review checklist) cost
review time and get bounced back. Following the template is cheaper than
re-writing the body after the first review pass.
