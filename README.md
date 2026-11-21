<img src="assets/icon.svg" width="64" height="64" alt="">

# lauzhack-26-cigala

LauzHack 2026 @ EPFL. Project TBD (challenge chosen at kickoff).

## How we work (2 humans, N agents, 1 repo)

Agents on different machines and subscriptions (Claude Code in T3, Antigravity, Codex) coordinate through GitHub only:

- **Board** = pinned issue #1. Agents post/read/wait with `tools/board` (bash + `gh`). Rules in [`AGENTS.md`](AGENTS.md).
- **Tasks** = GitHub issues. One issue → one branch/worktree → one PR (`Closes #N`).
- **No collisions** = owner table in `AGENTS.md` §5: each folder belongs to one agent.

Board kit adapted from [azizu06/hackathon-agent-board](https://github.com/azizu06/hackathon-agent-board).

## Setup per teammate (5 min)

```bash
gh auth login                       # once
git clone https://github.com/Jlopvs24/lauzhack-26-cigala && cd lauzhack-26-cigala
bash tools/board whoami             # prints your GitHub login
bash tools/board read -n 5          # you should see the board posts
```

- **Claude Code**: hooks are committed in `.claude/settings.json`; accept them on first launch. `CLAUDE.md` imports `AGENTS.md`.
- **Codex**: reads `AGENTS.md` automatically. First message of each session: *"Read AGENTS.md, run `tools/board unread`, then take issue #N."*
- **Antigravity**: tell it to follow `AGENTS.md` (or add it as a workspace rule).
- Parallel agents on one laptop → one git worktree each: `git worktree add ../cigala-12-api -b 12-api origin/master`.

## Picking the challenge (first 30 min)

Paste each sponsor's challenge text into `docs/challenges.md`, then run in Claude Code:

> Read docs/challenges.md. For each challenge extract prize, judging criteria, required tech and data provided. Brainstorm two ideas per challenge that 2 people + agents can demo in 24h. Mark ideas that hit more than one challenge (e.g. IMC + a bank). Rank by demo strength and by how much a quant/fintech angle makes us stand out.

Then split the chosen plan into issues and fill the owner table.
