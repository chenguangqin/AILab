<!--
TEMPLATE — loop-docs/design.md (the design-system anchor for UI / frontend builds).
The SD Loop writes this in PLAN (using an attached design skill like frontend-design)
and BUILD conforms EVERY section to it — so the last section is as polished and on-brand
as the first. A design system that lives only in the agent's context drifts across turns;
a written token doc it re-reads each turn does not. Non-UI builds (CLI, API, pipeline)
don't have a design.md.

Inspired by the DESIGN.md format (github.com/google-labs-code/design.md, Apache-2.0):
structured tokens + human-readable rationale. Kept kit-native (no external linter).

Pick ONE bold art direction and commit to it — see the menu at the bottom for flavors.
Fill in real values; delete the guidance comments.
-->

# Design System — <Project Name>

## Art direction
<One or two sentences: the ONE aesthetic this build commits to, and the feeling it should evoke.
e.g. "Warm, editorial, artisanal — serif display type, cream + a single berry accent, generous whitespace.">

## Tokens

### Palette
- **background** — <hex> · **surface** — <hex> · **ink / text** — <hex>
- **primary** — <hex> · **accent** — <hex> · **muted** — <hex>
- (state colors if needed: success / warning / danger)

### Typography
- **Display font** — <family> (weights) · **Body font** — <family> (weights)
- **Type scale** — <e.g. 12 / 14 / 16 / 20 / 28 / 40 / 64px> · **line-height** — <body / headings>
- **Letter-spacing / features** — <if any>

### Spacing & layout
- **Spacing scale** — <e.g. 4 / 8 / 12 / 16 / 24 / 40 / 64px> · **max content width** — <e.g. 46rem / 1200px>
- **Grid / rhythm** — <columns, gutters, vertical rhythm>

### Radius & elevation
- **Radius** — <e.g. 4 / 8 / 16px / pill> · **Shadows** — <e.g. subtle card / raised / overlay>

### Motion
- **Easing** — <e.g. ease-out cubic> · **Durations** — <e.g. 150 / 250 / 400ms>
- **Signature moment** — <one orchestrated entrance/reveal, not scattered micro-animations>

### Component patterns
- **Buttons** — <shape, fill/outline, states> · **Cards** — <…> · **Inputs / nav / etc.** — <…>

## Do's & Don'ts
- ✅ <a concrete rule that keeps sections on-brand — e.g. "berry accent only on CTAs and active states">
- ✅ <e.g. "every section uses the spacing scale — no ad-hoc margins">
- ❌ <a concrete anti-pattern — e.g. "no second accent color; no drop shadows on flat surfaces">
- ❌ <e.g. "no system-font fallback in shipped UI — load the display + body fonts">

<!--
ART-DIRECTION MENU — pick ONE (or write your own) for the line at the top. These are
*directions*, not locked looks: the design skill fills in the specific tokens per run,
so two "editorial" runs still look different. Variety without homogenizing output.

- editorial / artisanal   — serif display, warm neutrals + one accent, generous whitespace, magazine rhythm
- brutalist / raw         — mono or grotesk type, hard edges, high-contrast mono palette, exposed grid, no shadows
- glassmorphism / atmospheric — translucent frosted surfaces, soft gradient mesh backdrop, blur + light borders
- playful / toy-like       — rounded everything, saturated primaries, springy motion, chunky friendly type
- luxury / refined         — restrained palette, fine serif + tracking, lots of negative space, subtle gold/ink accents
- retro-futuristic         — neon-on-dark, scanline/grid textures, monospace accents, glow effects
- soft / pastel            — low-contrast pastels, airy spacing, gentle rounded shapes, calm
- industrial / utilitarian — dense data-forward layout, muted palette, tight grid, functional over decorative
-->
