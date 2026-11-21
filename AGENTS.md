# Rules for every agent in this repo

Team "cigala", LauzHack 2026 (EPFL). Hacking: Sat 21 Nov 12:00 → **Sun 22 Nov 12:00 (hard stop)**. Judging 12:30–15:00.
Two humans, several agents each, on different machines and subscriptions. We coordinate only through GitHub.

| Human | GitHub login | Agents |
|---|---|---|
| Juan (lead) | `@Jlopvs24` | Claude Code (T3 Code), Antigravity |
| FRIEND_NAME | `@FRIEND_LOGIN` | Codex (later Claude Code) |

`@all` = everyone.

## 1. The board (pinned GitHub issue #1)

Every agent reads and posts on the pinned "Message Board" issue via `tools/board` (bash + `gh` logged in). On Windows run it with Git Bash: `bash tools/board ...`.

- Start every post with `[<human>'s <agent>]`, e.g. `[Juan's Claude]`, `[FRIEND_NAME's Codex]`. The script rejects posts without it.
- Keep posts short: what changed, which files or contracts, what you need, from whom.
- Mention by GitHub login.
- **Mentions you or `@all`:** act on it and reply.
- **Not addressed to you:** still read it. Change your own work only if it is affected (a contract, a file you own). Do not reply just to acknowledge.
- Before editing a file you do not own, ask on the board and wait for its owner or the lead.

Commands: `tools/board unread` (new posts, marks read, flags MENTION) · `tools/board read -n 20` · `tools/board post "[Name's Agent] text"` · `tools/board wait` (blocks until someone else posts) · `tools/board whoami`.

**Staying in the loop**
- Claude Code: hooks in `.claude/settings.json` show unread posts at session start and on every prompt. Keep ONE background `tools/board wait` running and re-arm it after each wake.
- Codex / Antigravity / anything else: run `tools/board unread` at task start, before each commit, and after each merge.

## 2. Chain of command

Humans over agents. Juan is the lead: only the lead reassigns work between people. If an agent asks you to take over its area, ask the lead on the board.

## 3. Workflow

1. Work comes from GitHub issues. Take one and say so on the board (or comment on the issue).
2. Use your own git worktree and branch `<issue#>-<slug>` from a fresh `master`. Never write in another agent's checkout.
3. Small commits. Stage only your own files. Never `git add -A`.
4. Open a PR with `Closes #N`. Merge it yourself once it runs locally (squash merge).
5. `git fetch` and rebase on `origin/master` before pushing. Never force-push `master` or someone else's branch.
6. If a merge changes something others depend on (API route, data schema, env var, shared types), post it on the board when it lands.

## 4. Secrets and checks

- Never print, log, commit or post an API key. Keys go in `.env.local` (gitignored). Add the variable name (no value) to `.env.example`.
- Call LLM / paid APIs from the backend, never from browser code.
- Before saying something is done, run it or its test, and say what you ran.
- Demo > perfection. After Sun 09:00 only fixes and demo polish, no new features.

## 5. Who owns what

Fill this in right after we pick the challenge, before any agent writes code. Split by folders that rarely touch; each folder has exactly one owner.

| Area | Owner (login / agent) | Folders |
|---|---|---|
| Core engine (model / strategy / data pipeline) | TBD | `core/` |
| Backend API | TBD | `api/` |
| Frontend / demo UI | TBD | `web/` |
| Data, fixtures, demo script | TBD | `data/`, `scripts/` |
| Pitch, README, slides | Juan | `docs/`, `README.md` |

Shared contracts (API schema, data formats) live in `docs/contracts.md`. Changing one = board post tagging `@all`.
