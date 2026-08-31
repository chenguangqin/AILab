# Technical Environment — "Bake Like a Pro" Landing Page

## Summary
| Attribute | Value |
|---|---|
| Project type | Greenfield frontend prototype |
| Language / runtime | TypeScript on Node.js 20+ |
| Package manager | npm (pnpm acceptable) |
| Deploy target | **none (local only)** — served via `npm run preview` on localhost |

## Frameworks & services
| Layer | Choice |
|---|---|
| Framework | **React 19** |
| Build tool | **Vite** (React + TypeScript template) — see the dev-server note below |
| Styling | **Tailwind CSS** |
| Fonts | Fraunces + Hanken Grotesk (Google Fonts) |
| Content | static (from `vision.md`; CSVs provided for reference) — no backend, no fetch |
| State | local component state only (e.g. the mock enroll modal) |

This mirrors the real Hotmart "moon-builder-ui" stack (React + Vite + Tailwind), minus all
cloud/runtime pieces.

## Dev server (viewing the app from a browser IDE)

A hosted IDE may serve the dev/preview server under a **sub-path** proxy, not the domain root. Keep
the config environment-agnostic: take Vite's `base` from an env var (`VITE_BASE`, default `/`) rather
than hardcoding a host's path, and bind the server so a proxied host is accepted. Set **both** the
`server` and `preview` blocks to `host: true` and **`allowedHosts: true`** (the boolean `true`, which
allows any host). Do NOT use the string `'all'` — Vite 6 treats it as a single literal hostname and
rejects the real proxy host with a 403 ("This host is not allowed. Add it to preview.allowedHosts").
If a page shows its title but a blank body, `base` and the serving path disagree; a 403 through the
proxy means `allowedHosts` is wrong (use `true`).

## Prohibitions
- **No AWS, no CDK, no Cognito/S3/CloudFront, no deployment of any kind.** Local only.
- No backend, no API, no database, no real payment integration (the enroll flow is a mock).
- No leftover stubs, TODOs, or lorem-ipsum in the shipped sections.

## Validation commands (these prove milestones and the VERIFY seam)
- `npm install` — install dependencies (exit 0).
- `npm run build` — Vite production build (exit 0; emits `dist/`).
- `npm run preview -- --port 4173` — serve the built site locally; then a scripted check
  (curl the served HTML/JS, or a Playwright/vitest smoke test) asserts:
  - the string "Bake Like a Pro" is present,
  - all 5 module names appear,
  - all 3 plan prices ($29, $89, $19) appear,
  - the enroll button triggers the mock confirmation.
- Prefer a small `e2e` check (Playwright or a Node script hitting the preview server) as the
  authoritative VERIFY seam over unit tests alone.

Text presence alone is not a sufficient VERIFY seam: a page can contain every required string and
still be visually broken (a headline that collapses to one word per line, images that never render,
an off-subject photo, a dropped footer). The "looks genuinely designed" and "reads well on mobile,
tablet, and desktop" requirements in `vision.md` are part of *done*, and they can only be judged by
*seeing* the page. So in the VERIFY seam, after the site is serving, **capture screenshots of the
rendered page (desktop, tablet, and mobile widths) into `loop-docs/`** — the Pilot reviews these to
judge the page visually, catching breakage that a text/DOM assertion cannot. You already have the
browser open for the E2E check; take the shots there. (A screenshot proves how the page *looks*,
including whether each image actually depicts its subject per `images.md`.)

While the browser is open, also assert **every declared image actually renders**: no broken or `404`
sources (an `<img>` with `naturalWidth === 0` after load, or a CSS `background-image` that never
paints, is a defect). The images come from the curated `images.md` set; if any URL has since been
retired, fall back to a placeholder (`images.md`) rather than shipping a broken image slot.
