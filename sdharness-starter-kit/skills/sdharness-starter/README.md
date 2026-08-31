# sdharness-starter — concierge skill

A Claude Code skill that helps you **learn, adopt, and customize** the SD Harness starter kit. Ask
Claude Code things like *"help me learn the SD Harness starter kit"*, *"run the bake-like-a-pro
example"*, or *"help me author a new method"* and it walks you through Levels 100 → 300, grounded in
this repo's own `docs/`.

> Claude Code only, for now.

## Install (pick one)

**A. Copy into your Claude Code skills dir** (simplest):
```bash
cp -r skills/sdharness-starter/skills/sdharness-starter ~/.claude/skills/sdharness-starter
```
Then in Claude Code the skill is available as `/sdharness-starter` (and triggers automatically on
relevant asks).

**B. Add this repo as a Claude Code plugin** (the skill ships a `.claude-plugin/plugin.json`):
point Claude Code's plugin config at `skills/sdharness-starter/` in your checkout.

## How it's structured

```
skills/sdharness-starter/
├── .claude-plugin/plugin.json                 # Claude Code plugin marker
├── README.md                                  # this file
└── skills/sdharness-starter/
    ├── SKILL.md                               # the concierge (learn → adopt → customize)
    └── references/
        ├── run-the-example.md                 # Level 100 — get a green run
        ├── understand-the-architecture.md     # Level 200 — the two-harness loop + gates
        └── customize-and-extend.md            # Level 300 — author a method/strategy/skill
```

The references are progressive-disclosure companions: the SKILL.md tells the agent when to read
each, and each hands off to the matching `docs/…` in the repo for full detail (single source of
truth — the references summarize and point, they don't fork the docs).

## Note

This skill is for a **developer using Claude Code on this repo** (onboarding + customization). It is
deliberately *not* wired into the `loop` method's `skills` list — that list is for skills the coding
agent uses *while building* (e.g. `frontend-design`), a different job.
