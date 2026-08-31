# Vision — add a "Bake Coach" AI agent to the Bake Like a Pro site

Take the **Bake Like a Pro** landing page you already built (the `bake-like-a-pro` example) and make
it interactive: add a **"Bake Coach" chat agent** — a **Strands agent** running on **Amazon Bedrock
AgentCore Runtime** (backend) plus a **chat widget** wired into the existing React site (frontend).

A visitor should be able to open the chat, ask a baking question ("how do I stop my sponge sinking?",
"what's 15% of 240g of flour?"), and get a helpful, streamed answer from the Bake Coach — all
runnable and testable **locally** (no cloud deploy required to demonstrate it).

This is the flagship showcase for **autonomous full-stack development**: the SD Loop plans the
architecture, builds the agent backend, adds the chat UI to the existing frontend, wires them
together, and proves the whole thing works end to end.

## Starting point

This run **builds on the output of the `bake-like-a-pro` example** — a React + Vite + Tailwind
landing page. Bring that site in as the frontend starting point (copy it into this workspace, or
point the run at a workspace that already contains it). You are **adding to** it, not rebuilding it:
keep the existing design and sections intact, and add the chat feature on top.

## What to build

**Backend — a "Bake Coach" Strands agent on AgentCore Runtime**
- A Python agent using the **Strands** framework, served through **AgentCore Runtime**, with **Amazon
  Bedrock** (Claude) as the model and a friendly, expert baking-coach persona.
- Give it **at least one useful tool** — e.g. a recipe-scaling / bakers'-percentage calculator — so it
  demonstrably *uses tools*, not just chats.
- Runnable and invokable **locally**. Confirm the exact runtime SDK, HTTP contract, and local-run
  command from the authoritative docs (see `tech-env.md`) — don't assume the API from memory.

**Frontend — a chat widget on the existing site**
- Add a **"Bake Coach" chat widget** to the existing landing page (launcher → chat panel with message
  list, input, send, and a "coach is thinking" state) that calls the agent and **renders the reply as
  formatted markdown** — bold, lists, and headings display as rich text, never as literal `**asterisks**`
  or `-` bullets (the agent streams markdown). Prefer a streaming-aware renderer such as
  [`streamdown`](https://www.npmjs.com/package/streamdown) (a drop-in `react-markdown` replacement built
  for AI streaming that handles incomplete blocks gracefully).
- Make the agent endpoint URL **configurable** (env var / config) so it works locally now and against
  a deployed runtime later.
- Match the site's existing design system so the widget feels native, not bolted on.

## Must include
- The Bake Coach answers a normal baking question **and** correctly answers one needing its tool
  (e.g. "scale this recipe from 4 to 10 servings" or "what's 15% of 240g?").
- The chat widget opens on the site, sends a message, and displays the coach's response.
- The original landing-page content (course name, 5 modules, 3 prices, enroll flow) still works.
- A short `README.md` explaining how to run backend + frontend locally.

## Done =
- Backend: the agent runs locally and a scripted check confirms a well-formed response including a
  correct **tool-assisted** answer.
- Frontend: the build succeeds and the served site shows the working chat widget; a scripted/Playwright
  check confirms opening the chat, sending a message, rendering a reply **as formatted markdown** (the
  reply bubble contains rendered HTML like `<strong>`/`<ul>`, not a literal `**` or leading `-`), and
  that the original site content still works.
- The run's integration report is green: both new seams (agent invocation + widget→agent round trip)
  are exercised and pass, alongside the existing site checks.

Cloud deployment is an **optional stretch**, not required for "done" — the verified local run is the
deliverable. How you plan and build it is yours.
