# The Mental Model — one Pilot ⇄ Agent loop, at three scales

> Part of **SD Harness**. Companion reads: [Harness Engineering](harness-engineering.md) · [Loop Engineering](loop-engineering.md) · [The Compounding Cycle](compound-engineering.md).  ·  **Level 100**

**Start here.** The kit has a doc for each idea — harness, loop, and the compounding cycle — but they
are easy to mistake for three separate systems. They aren't. They're **the same Pilot ⇄ Agent loop,
seen at three time-scales.** This page is the map; the others are the deep dives.

![The mental model — every run is a Pilot ⇄ Agent loop: the Agent writes code, an outer Pilot reviews and gates each turn with GO or NO_GO and steers the next. The same self-driving harness loop runs at three scales — per turn (harness engineering), per run (loop engineering, RESEARCH→PLAN→BUILD→VERIFY), and across runs (the compounding cycle). The Agent writes; the Pilot calls it done.](../assets/mental-model.png)

## One loop

Every run is a single loop: the **Pilot** prompts the coding agent → the agent produces output +
artifacts → the harness gates and steers → repeat, turn by turn, until the work is verified. That's
it. The industry calls this the **agentic loop** — "LLMs autonomously using tools in a loop," where
it's "crucial for the agents to gain ground truth from the environment at each step"
([Anthropic, *Building Effective Agents*](https://www.anthropic.com/engineering/building-effective-agents)).

The three "engineerings" are just three questions you ask *about that loop*, at three time scales.

## The three axes

| Axis | The question | Time scale | In the kit | Deep dive |
|------|--------------|-----------|-----------|-----------|
| **Harness engineering** | Is *this turn* sound? — **STRUCTURE** | within a turn | deterministic gates (`phase_authority`), a read-only Pilot verdict, kill switches, generator/evaluator split | [harness-engineering.md](harness-engineering.md) |
| **Loop engineering** | Are we *still heading to the goal*? — **DURATION** | across turns, one run | the SD Loop `RESEARCH→PLAN→BUILD→VERIFY`, a runnable VERIFY check, checkpoints, stall/budget caps | [loop-engineering.md](loop-engineering.md) |
| **The compounding cycle** | Does *this run make the next one better*? — **MEMORY** | across runs & a team | the `agent-context/` seed read before, `sdharness compound` written after | [compound-engineering.md](compound-engineering.md) |

### Harness — structure per turn
A coding agent left alone is stochastic; a harness wraps it in a **deterministic** outer layer that
decides whether a turn may proceed. Anthropic draws exactly this line — "workflows" (predefined code
paths) vs. "agents" (self-directed) — and makes the control **deterministic on purpose**: Claude
Code hooks are "user-defined … [that] execute automatically," and *"unlike CLAUDE.md instructions
which are advisory, hooks are deterministic"*
([Claude Code hooks](https://code.claude.com/docs/en/hooks) · [best practices](https://code.claude.com/docs/en/best-practices)).
Their best-practice gates — a Stop hook that "blocks the turn from ending until it passes," a `/goal`
condition "re-checked by a separate evaluator after every turn," and a **verification subagent** so
"the agent doing the work isn't the one grading it" — are the same three moves the kit ships:
artifact gates, a separate Pilot, and the generator/evaluator split (LangChain calls the last one
[LLM-as-judge](https://docs.langchain.com/langsmith/llm-as-judge)).

### Loop — duration across turns
One good turn isn't a finished job. Loop engineering keeps the agent going toward a goal across many
turns — and the key move is **giving it a runnable check so it closes its own act→verify→iterate
loop**, instead of making the human the verification loop. The kit's SD Loop does this literally:
VERIFY isn't done until `loop-docs/integration-report.json` is green, and `goal.md` / `progress.md`
are the durable state the loop drives across turns (the "explore → plan → code → commit with durable
state" pattern; Cognition's Devin and Every's `/lfg` are hands-off versions of the same idea).

### Compounding — memory across runs
A run that throws away what it learned starts every future run from zero. The compounding cycle makes
each run **deposit durable knowledge** the next one reads first, so the next run starts smarter. This
is the read-before/write-after cycle: the kit stages `agent-context/` (LESSONS/QUALITY/STEERING)
*before* a run and `sdharness
compound` promotes a run's `progress.md` Patterns into the seed *after*. It's bounded by Anthropic's
**context engineering** — a finite token budget degrades with "context rot," so mature setups curate
what they inject rather than paste everything
([Anthropic, *Effective context engineering*](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)).

## Input and outcome

Two ideas frame the loop rather than being axes of it:

- **Input — [setting up for success](loop-engineering.md#setting-the-loop-up-for-success--the-input).**
  The quality of the intent bundle is the biggest lever on the result: lean direction + rich
  resources. Garbage in, autonomous garbage out.
- **Outcome — [increasing autonomy](loop-engineering.md#increasing-autonomy--the-outcome).** As the
  three axes get stronger, the human moves **reviewer → decision-maker → supervisor**. Autonomy isn't
  the input; it's what a well-built loop *earns* — and it "scales as models improve" (Anthropic).

And the positioning: the built-in loop inside Claude Code / Kiro / Codex is the **inner** harness;
SD Harness is the **outer** loop that adds the structure, duration, and memory a self-driving inner
loop can't give itself. See
[How is this different?](harness-engineering.md#how-is-this-different-from-just-running-claude-code--kiro--codex).

## How the kit jump-starts these techniques — the value

The kit isn't just a definition of these ideas; it's a **running baseline** so a team gets the value
without building the scaffolding first. Per axis:

| Axis | What the kit gives you on day one | The value |
|------|-----------------------------------|-----------|
| **Harness** | Deterministic artifact gates + a separate fail-closed Pilot verdict + kill switches, already wired | Fewer escaped defects and safe **unattended runs** — the harness catches "built but not working," and a runaway agent stops itself |
| **Loop** | The SD Loop with a real VERIFY gate + checkpoints | The agent **finishes long, multi-session goals** on its own, proving the result end-to-end instead of leaving a human to check every turn |
| **Compound** | A curated seed staged in + `sdharness compound` to write back | **Faster onboarding** (new work starts from accumulated lessons) and **team knowledge sharing** (promote lessons via review) — each run raises the floor |

## The one-liner

> **Harness engineering makes a turn trustworthy. Loop engineering makes a run finish the job.
> The compounding cycle makes every run raise the floor for the next.** Same loop, three axes —
> better input and more autonomy are what you get out.

Read next: [Harness Engineering](harness-engineering.md) → [Loop Engineering](loop-engineering.md) →
[The Compounding Cycle](compound-engineering.md), or trace it in code via [How it works](../how-it-works.md).
