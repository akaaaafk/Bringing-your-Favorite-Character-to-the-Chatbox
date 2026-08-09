# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Movie Persona Chat
**Updated:** 2026-08-05 · Impeccable colorize + animate pass
**Style:** Projection-room cinema (warm dark) · Pattern: Persona landing + Operate chat
**Design Dials:** Variance 5/10 | Motion 6/10 | Density 4/10

---

## Global Rules

### Color Palette (Projection booth)

Warm charcoal canvas + tungsten accent. Refuse indigo nightlife / AI purple.

| Role | Value | CSS Variable |
|------|-------|--------------|
| Primary | `oklch(0.28 0.04 45)` | `--color-primary` |
| Secondary | `oklch(0.32 0.035 40)` | `--color-secondary` |
| Accent / CTA | `oklch(0.78 0.14 75)` | `--color-accent` |
| On Accent | `oklch(0.18 0.03 50)` | `--color-on-accent` |
| Background | `oklch(0.145 0.02 55)` | `--color-background` |
| Foreground | `oklch(0.94 0.02 85)` | `--color-foreground` |
| Card | `oklch(0.2 0.025 50)` | `--color-card` |
| Muted | `oklch(0.24 0.025 48)` | `--color-muted` |
| Muted Foreground | `oklch(0.72 0.03 70)` | `--color-muted-fg` |
| Border | `oklch(0.42 0.04 55)` | `--color-border` |
| Destructive | `oklch(0.62 0.18 25)` | `--color-destructive` |
| Ring | `oklch(0.78 0.14 75)` | `--color-ring` |

Per-character accent stripes stay on the cast / rail; brand tungsten owns CTAs only.

### Typography

- **Heading:** Bodoni Moda (title-card)
- **Body:** Source Sans 3
- **Mood:** warm cinema, editorial, precise
- **Google Fonts:** Bodoni Moda + Source Sans 3

### Spacing

| Token | Value |
|-------|-------|
| `--space-xs` | `4px` |
| `--space-sm` | `8px` |
| `--space-md` | `16px` |
| `--space-lg` | `24px` |
| `--space-xl` | `32px` |
| `--space-2xl` | `48px` |
| `--space-3xl` | `64px` |

### Motion thesis

- **Focal:** React Bits `BlurText` focus-pull on hero (Motion)
- **Atmosphere:** React Bits `LightRays` tungsten projector beam on landing (ogl WebGL)
- **Feedback:** React Bits `ClickSpark` on CTA / cast / send; message `msg-in`
- **Continuity:** view fade landing↔chat; character glow crossfade
- **Cast:** IntersectionObserver reveal
- Easing: `cubic-bezier(0.16, 1, 0.3, 1)` · respect `prefers-reduced-motion` (disables LightRays / BlurText anim)

### Anti-patterns

- Indigo / purple SaaS dark theme
- Inter / Playfair default pairing
- Emoji as icons (use Lucide / SVG)
- Cards in the hero
- Eyebrow / kicker above the H1
- Bounce / elastic easing

### Pre-Delivery Checklist

- [ ] SVG icons only
- [ ] `cursor-pointer` on clickables
- [ ] Hover 150–300ms
- [ ] Focus rings visible
- [ ] `prefers-reduced-motion`
- [ ] Responsive 375 / 768 / 1024 / 1440

---

## Page Map

1. **Landing** — Brand + one headline + short line + CTA; character strip below fold
2. **Chat** — Character context rail + conversation + Best-of-N controls
