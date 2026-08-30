# Breadcrumbs — Figma system spec

Not the project brief. This is the system itself: what to set up as Figma **variables**, **components/variants**, and **prototype interactions**, so the file behaves like the mockup when you click through it — and translates 1:1 to React state when it's built.

---

## 1. File structure (pages)

```
📄 00 – Tokens          (variable collections, text styles, effect styles)
📄 01 – Components       (every component + its variants, no layout)
📄 02 – Screens          (the assembled scrolling page, using instances only)
📄 03 – Prototype        (copy of 02, wired with interactions — keep separate so wiring never blocks layout edits)
```

Never wire interactions on the same page you're actively laying out — `03` is a duplicate of `02` you re-sync manually when layout settles. This is the single biggest cause of broken Figma prototypes: editing a frame that has 40 interactions pointing at it.

---

## 2. Variable collections

Figma variables, not just styles — because two of the widgets (the decision toggle, the gate simulator) need real state that prototype interactions can read and write.

### Collection: `color` (single mode — this system doesn't need light/dark)
| Variable | Value | Bound to |
|---|---|---|
| `color/ink` | `#141A22` | text |
| `color/indigo-900` | `#1E2A44` | hero/gate surfaces |
| `color/indigo-600` | `#33456B` | buttons, links |
| `color/loom-100` | `#EDEAE0` | page bg |
| `color/loom-50` | `#F7F5EF` | card bg |
| `color/brass` | `#B08A3E` | accent, active states |
| `color/verified` | `#2E6B5E` | promote / measured |
| `color/rust` | `#9C4A34` | reject / specified |
| `color/thread` | `#9B9384` | dividers, inactive |

### Collection: `spacing` (number)
`space/xs=4, sm=8, md=16, lg=24, xl=40, 2xl=64` — bind to auto-layout gap/padding, never type a raw number into a frame.

### Collection: `state` (the one that makes the prototype real)
| Variable | Type | Default | Driven by |
|---|---|---|---|
| `state/switch-writers` | boolean | true | Decision Toggle |
| `state/switch-custodian` | boolean | true | Decision Toggle |
| `state/switch-shared` | boolean | true | Decision Toggle |
| `state/verdict` | string | `"blockchain"` | computed from the three switches |
| `state/merkle-step` | number | 0 | Merkle Stepper |
| `state/gate-outcome` | string | `"idle"` | Gate Simulator (`idle` / `running` / `promote` / `reject`) |
| `state/gate-progress` | number | 0 | Gate Simulator (drives which flow-steps are lit) |

Figma prototyping (2024+) supports conditional expressions and variable math on interactions — every behavior below is built from these two features plus **Smart Animate**, no code.

---

## 3. Text styles
| Style | Font | Size/weight | Use |
|---|---|---|---|
| `display/h1` | Fraunces | 44/600 | hero headline |
| `display/h2` | Fraunces | 26/600 | section headline |
| `body/lead` | Inter | 17/400, 1.65 line | intro paragraphs |
| `body/base` | Inter | 15/400 | general copy |
| `mono/label` | IBM Plex Mono | 12/500, +6% tracking, uppercase | eyebrows, stamps, step pills |
| `mono/data` | IBM Plex Mono | 13/400 | hashes, chaincode names |

---

## 4. Components (variants + properties)

Build these on page `01`, each as one component set. Variant axes are listed as they'd appear in the Figma properties panel.

### `StatusStamp`
- Variant axis `state`: `measured | simulated | specified | assumption`
- Each variant is a fixed combo of border color + text color + label (bound to `color/*` variables, not hard-coded hex) — swapping the variant is the only way to change it, so it can never drift from the token set.

### `LedgerRow`
- Property `label` (text), `body` (text), `stamp` (instance-swap → `StatusStamp`, optional)
- Auto-layout: 200px fixed left column, flexible right column, matching the CSS grid in the mockup.

### `ToggleSwitch`
- Variant axis `on`: `true | false`
- Boolean component property `bound-variable` — set each instance's `on` variant to *read from* one of the three `state/switch-*` variables (Figma lets a variant be driven by a variable, not just set manually).
- Interaction on the switch layer itself: **On click → Set variable** `state/switch-writers` (or whichever) **to** `not(state/switch-writers)`. No navigation, no Smart Animate needed — the bound variant does the visual flip automatically.

### `VerdictBanner`
- Variant axis `result`: `blockchain | database`
- Its instance on the canvas has no click interaction — instead, drive its `result` variant with a **conditional expression** bound to the three switch variables: `if (switch-writers and switch-custodian and switch-shared) then "blockchain" else "database"`. This is the one place you need Figma's expression editor rather than a simple boolean.

### `PlaneAccordion`
- Variant axis `open`: `true | false`; property `steps` (text, one per line, or a nested `Pill` list component)
- Interaction: **On click (header) → Change to** the other variant, transition **Smart Animate, 200ms, ease-out**, scoped to "this layer" so the other two plane instances don't also toggle.

### `MerkleStepper`
- A single component with 7 child `Step` instances (variant axis `state`: `pending | active | done`)
- Each `Step`'s variant is bound to an expression comparing its own index against `state/merkle-step`.
- The button below it: **On click → Set variable** `state/merkle-step` **to** `state/merkle-step + 1`, condition-gated so the button becomes non-interactive (or swaps to a "done" variant) once `state/merkle-step = 7`.
- The punchline text block: visibility bound to `state/merkle-step >= 7`.

### `ContinuityGate`
This is the one component that genuinely needs a short interaction *chain* rather than a single click:
- Two trigger buttons (`Submit good candidate` / `Submit forgetful candidate`), each: **On click → Set variable** `state/gate-outcome` **to** `"running"`, **and** set a second variable `state/gate-target` to `"promote"` or `"reject"`.
- A row of 7 `FlowStep` instances, each bound (via expression) to `state/gate-progress >= its own index`.
- Chain of **After delay 260ms → Set variable `state/gate-progress` to `state/gate-progress + 1`** interactions, one per step, each firing off the previous — this is Figma's native way to fake a JS `setInterval` with no code. On the last delay, instead set `state/gate-outcome` to the value of `state/gate-target`.
- The `Outcome` panel's variant (`idle | running | promote | reject`) is bound directly to `state/gate-outcome`.

### `LimitationRow`
- Property `index` (text), `body` (text), `stamp` (instance-swap → `StatusStamp`). No interaction — static list, matches the mockup exactly.

---

## 5. Interaction map (quick reference)

| Component | Trigger | Action | Notes |
|---|---|---|---|
| ToggleSwitch ×3 | On click | Set variable → boolean flip | drives `VerdictBanner` via expression, no direct link between them |
| PlaneAccordion ×3 | On click | Change to (open/closed) | Smart Animate, scoped per-instance |
| MerkleStepper button | On click | Set variable → increment | button disables / punchline reveals via bound visibility |
| GateSimulator buttons | On click | Set two variables, then a delay-chain of increments | last delay sets the outcome variable |
| Nav links | On click | Scroll to | Figma's native "Scroll to" action, target = section frame on page `02`/`03` |

---

## 6. the React build

Every row above maps directly onto React state with no translation gap:

| Figma variable | React equivalent |
|---|---|
| `state/switch-*` (boolean) | `useState<boolean>` ×3 |
| `state/verdict` (computed) | derived value, not its own `useState` — `const verdict = a && b && c ? 'blockchain' : 'database'` |
| `state/merkle-step` (number) | `useState<number>(0)`, button does `setStep(s => s+1)` |
| `state/gate-outcome`, `gate-progress` | `useState`, delay-chain becomes a `setInterval`/`setTimeout` sequence exactly as in the HTML mockup's `runGate()` function |

Because the Figma variables are named to mirror the eventual state variables, whoever codes this can read the prototype interactions as a state-transition table rather than reverse-engineering intent from static frames — that's the entire point of specifying it this way instead of as plain screens.
