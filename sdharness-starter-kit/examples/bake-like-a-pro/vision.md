# Vision — "Bake Like a Pro" Landing Page

Build a **beautiful, delightful, eye-catching** landing page for an online baking course,
**Bake Like a Pro** by Chef Amara Silva. This is a frontend-design showcase — the bar is
visual craft. A visitor should want to enroll on feel alone.

**Use the `frontend-design` skill** (attached to this run) to design and build the UI.

**Keep the design consistent:** in PLAN, use the skill to settle the aesthetic, then capture it as a
**structured `loop-docs/design.md`** — named design tokens (palette, typography + type scale, spacing,
radius, elevation, motion, component patterns) plus a short **Do's & Don'ts** — and build **every**
section to that file. It's the run's cross-turn consistency anchor: reading a written token doc each
turn keeps the last section as polished and on-brand as the first (a design system that lives only in
the agent's head drifts across turns).

**Art direction:** *warm, editorial, artisanal — serif display type, cream + a single berry accent, generous whitespace.*

**Design for adoption — responsive and easy to browse.** Visual craft alone isn't the bar; the page
must make a visitor want to enroll *fast*, on any device. Concretely:
- **Multi-device by default.** Flawless on mobile, tablet, and desktop — design mobile-first, then tune
  up. Collapse the top nav on small screens (a menu/hamburger, not crowded links), keep tap targets
  finger-sized, and use the extra room on wide screens rather than a lonely center column. Assume it'll
  be judged at ~375px (phone), ~768px (tablet), and ~1440px (desktop).
- **Scannable, not an endless scroll.** A visitor should grasp the whole offer with minimal scrolling.
  Favor compact, scannable layouts — e.g. the 5 modules as a tight grid or list a reader takes in at a
  glance, **not** five full-screen alternating image/text billboards. Reserve large hero-style blocks
  for the hero; keep supporting sections dense and quick to skim.
- **Easy to browse.** Clear visual hierarchy, obvious next action, and a persistent/quick path to
  enroll as the visitor scrolls — so the route from "interested" to "enroll" is always one glance away.

## Must include
- A compelling hero with the course name and a clear call to action.
- The 5 course modules: Foundations · The Perfect Sponge · Frosting & Fillings · Decorating · Going Pro.
- The 3 pricing plans: Starter **$29** one-time · Pro **$89** one-time (recommended) · Membership **$19/month**.
- A mock "enroll" interaction (no real payment) that confirms the chosen plan.

## Resources (provided in this folder)
- `images.md` — the curated, verified image set to wire in (URL + description per section).
- `bake-like-a-pro-curriculum.csv` / `bake-like-a-pro-offers.csv` — full course + pricing detail.
- `tech-env.md` — the stack and constraints (local only, no cloud).

## Done =
`npm run build` succeeds, the site runs locally, and a scripted check confirms the course
title, the 5 module names, the 3 prices ($29 / $89 / $19), and the enroll confirmation are
present — **and it looks genuinely designed, with the curated `images.md` photos wired into their
sections** **and reads well on mobile, tablet, and desktop with minimal scrolling** (responsive,
scannable, easy to browse — see the adoption notes above). How you get there is yours to plan.
