# Git and GitHub guide

Applies when the user asks for branches, commits, pushes, issues, pull requests, reviews, or merges.

## Branches and commits

- The usual base branch is `develop`; verify the current branch, worktree state, and remote state before acting.
- Do not mix or overwrite unrelated user changes.
- When an issue exists, name the branch `<type>/<issue>-<short-description>` as defined in `SPEC_DRIVEN_DEVELOPMENT.md`.
- Do not work directly on `main` or `develop` when preparing a branch or pull request.
- Keep commits cohesive and exclude unrelated formatting, generated artifacts, secrets, and private data.

## Publishing

Creating or modifying issues, labels, milestones, branches, commits, pushes, or pull requests requires an explicit user request for that action. Local implementation does not imply permission to publish it.

Before pushing or opening a pull request:

1. Review the complete diff.
2. Run the checks relevant to the changed areas.
3. Check for secrets, sensitive data, generated files, and unrelated changes.
4. Link the issue and record verification evidence in the pull request.
5. Use a draft pull request when the work is incomplete.

Do not merge without explicit user authorization. Even with authorization, do not merge while required CI fails, acceptance criteria remain incomplete, review threads or decisions are unresolved, blocking dependencies are open, or a migration lacks a safe execution and rollback plan.

Do not rewrite shared history or use destructive Git operations unless the user explicitly requests the exact operation.
