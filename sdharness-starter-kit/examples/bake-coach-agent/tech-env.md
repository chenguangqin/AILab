# Technical Environment — "Bake Coach" agent on the Bake Like a Pro site

## Summary
| Attribute | Value |
|---|---|
| Project type | Brownfield — **add an AI agent to the existing `bake-like-a-pro` frontend** |
| Languages / runtimes | **Python 3.11+** (agent) · **TypeScript on Node.js 20+** (frontend) |
| Package managers | uv or pip (Python) · npm (frontend) |
| Deploy target | **none required (local only)** — backend via `agentcore dev`, frontend via `npm run dev`. Cloud `agentcore deploy` is an optional stretch. |

## Frameworks & services (directional — confirm specifics against the docs)
| Layer | Choice |
|---|---|
| Agent framework | **Strands Agents** |
| Agent hosting | **Amazon Bedrock AgentCore Runtime** |
| Model | **Amazon Bedrock** — a Claude model |
| Frontend | **React + Vite + TypeScript + Tailwind** (the existing bake-like-a-pro stack) |
| Frontend↔agent | `fetch` to the agent's invocation endpoint; base URL from a config/env var |

## Read the authoritative docs FIRST (do this in RESEARCH)

This stack moves fast, so **do not assume the API from memory** — the exact SDK entrypoint
(`BedrockAgentCoreApp`), the HTTP contract (invocation + health-check paths, host, port), and the
local-run command are defined by the official docs. In RESEARCH, read these and pin the specifics
you'll build against into `research.md` (with the doc URL and the date you read it):

- **What AgentCore Runtime is** — https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html
- **The HTTP service contract** (invocation + `/ping` health-check paths, host, port) —
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html
- **Get started *without* the AgentCore CLI** — the SDK-native path this build uses: wrap the agent in
  `BedrockAgentCoreApp` from the `bedrock-agentcore` Python SDK and run it locally with plain
  `python app.py` (no CLI, no container, no CDK) —
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-custom.html
- **bedrock-agentcore Python SDK** — https://github.com/aws/bedrock-agentcore-sdk-python
- **Strands Agents docs** — https://strandsagents.com/ (agent definition + registering tools)

If tooling has changed since these notes were written, **trust the docs over this file** — and note the
delta in `research.md`. (AgentCore also has an `agentcore` CLI for containerized deploys; this local
workshop build deliberately uses the simpler SDK-native `python app.py` path instead — no CLI needed.)

> **If the AWS documentation MCP is wired into the harness** (see the "Add an MCP server" exercise in
> Customize the harness), prefer it over these static URLs: use the MCP to look up the *current*
> AgentCore Runtime contract and Strands usage during RESEARCH. The MCP gives live, authoritative AWS
> knowledge; fall back to the URLs above only if no AWS MCP is available.

## Agent contract (verify against the runtime overview doc)
The agent must expose the runtime's **invocation endpoint** (accepts a prompt, returns a result) and
its **health-check endpoint**, be **runnable locally** for testing, and register **at least one tool**
on the Strands agent (e.g. a recipe-scaling / bakers'-percentage calculator) so it demonstrably uses
tools. Take the exact paths, request/response shapes, host/port, and dev command **from the docs
above** — that's the source of truth, not this summary.

## Constraints & prohibitions
- **Build on the existing site — do not rebuild it.** Preserve the current design system, the
  course name, the 5 modules, the 3 prices, and the enroll flow. Add the chat widget on top.
- **Local-first.** Everything must run and be verified locally. **No required cloud deploy**, no
  CDK/Cognito/S3 as part of "done." (`agentcore deploy` is a clearly-marked optional stretch.)
- Keep the agent's model on **Amazon Bedrock** (`CLAUDE_CODE_USE_BEDROCK` environment applies to the
  harness's own coder; the *built agent* invokes Bedrock via Strands' Bedrock model provider).
- **The browser must reach the agent same-origin, via a Vite dev-server proxy — not a direct
  `fetch` to the agent's port.** Configure `server.proxy` (and `preview.proxy`) in `vite.config.ts` so
  the widget calls a relative `/api/...` path that Vite forwards server-side to the agent
  (`/api` → `http://localhost:<AGENT_PORT>`, stripping the `/api` prefix). Do **not** point the widget
  at `http://localhost:<port>` directly: in a hosted browser IDE the page runs on the user's laptop,
  where that port doesn't exist, so a direct call fails. Same-origin `/api` keeps the agent private and
  works behind a sub-path proxy. Make the agent base overridable by env for own-machine use, but the
  **default and the tested path is same-origin `/api`**.
- No leftover stubs, TODOs, or lorem-ipsum.

## Validation commands (these prove milestones and the VERIFY seam)
> The *shape* of the checks is fixed below; the exact local-run command, endpoint paths, host and
> port come from the runtime docs you read in RESEARCH — use those, not placeholders.

**Backend (agent):**
- Install the agent's Python dependencies — exit 0.
- Start the agent locally (the runtime's documented local-dev command), then a scripted check:
  - a `POST` to the documented **invocation endpoint** with `{"prompt":"what is 15% of 240g?"}`
    returns a well-formed result whose answer contains the correct **tool-assisted** value (**36**) —
    proving the agent used its calculator tool, not just chatted.
  - a `GET` to the documented **health-check endpoint** returns a healthy status.

**Frontend (site + widget):**
- `npm install` (exit 0) · `npm run build` (exit 0; emits `dist/`).
- `npm run dev` (or `npm run preview`) serves the site; a Playwright/Node smoke check asserts:
  - the original content is present (course title, 5 module names, 3 prices $29/$89/$19),
  - the Bake Coach launcher opens the chat panel,
  - sending a message renders an assistant reply **as formatted markdown** — assert the reply bubble
    contains rendered HTML (e.g. a `<strong>` or `<ul>`/`<li>` element) and does **not** show a literal
    `**` or a leading `-` in its visible text (mock the agent endpoint in the test if the live agent
    isn't running, but the authoritative round-trip check hits the running agent).
  - the widget's request goes to a **same-origin `/api/...`** path (proxied to the agent), **not** a
    hardcoded `http://localhost:<port>` — assert the built bundle / network call uses `/api`, so it
    works behind a sub-path proxy.

Prefer a small `e2e` check (Playwright, or a Node script hitting both the agent and the served site)
as the authoritative VERIFY seam over unit tests alone.

## Notes for running inside a browser IDE
- A hosted IDE may serve the dev/preview server under a **sub-path** proxy, not the domain root. Keep
  the frontend's Vite config environment-agnostic: take `base` from an env var (`VITE_BASE`, default
  `/`) rather than hardcoding a host path, and bind the server (`host`, `allowedHosts`) so a proxied
  host is accepted. Title-but-blank-body means `base` and the serving path disagree.
