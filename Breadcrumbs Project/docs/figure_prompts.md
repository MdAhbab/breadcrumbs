# Three figure prompts for a high-resolution image generator

**Read this first — it will save you a wasted generation.** Image models still garble text.
They do well with 1–3 word labels in large type and badly with sentences, small captions, or
more than about twenty distinct strings on a canvas. Every prompt below therefore gives an
explicit, short, closed list of the words allowed in the image, and asks for generous space
around each one. Generate at the largest size available, then check every label letter by
letter; a figure with "Continiuty Gate" in it is worse than no figure.

If a label comes out wrong twice, tell me — the paper already draws its figures in TikZ, and
I can produce any of these three with exact typography instead, or produce a clean TikZ label
layer to sit over a generated background.

Shared palette, used in all three so the set reads as one system:
blue `#2563EB` (the ledger), orange `#E8710A` (the learning plane), green `#059669` (proof
succeeded / verified), grey `#6B7280` (secondary), near-black `#111827` (text), light grey
`#E5E7EB` (rules and borders), off-white `#F7F8FA` (background). It is colour-blind safe and
survives greyscale printing. No gradients, no drop shadows, no glow, no 3-D, no photorealism.

---

## 1 · Graphical abstract

> A clean academic graphical abstract for a computer-science paper, flat vector illustration
> style, wide 16:9 landscape, off-white `#F7F8FA` background, generous white space, thin
> `#E5E7EB` rules, no shadows, no 3-D, no photorealism.
>
> The composition reads left to right in four columns separated by thin vertical rules, with
> a single horizontal arrow spanning the full width beneath them in `#6B7280`.
>
> **Column 1 — "Records".** A small stack of three flat document pictograms in `#6B7280`,
> lightly overlapping, one with a tiny table of ruled lines, one with a stamp circle, one with
> a signature squiggle. Above them the word `RECORDS`.
>
> **Column 2 — "Commit".** A hexagonal outline in `#2563EB` containing a small binary Merkle
> tree drawn as seven dots joined by thin lines, three at the base, two above, one at the top.
> A short arrow from the top dot exits the hexagon. Above it the word `COMMIT`.
>
> **Column 3 — "One number".** The visual centre and the largest element: a single large
> rounded square in `#2563EB` with a thick border, containing a long string of monospace
> hexadecimal characters wrapped over three lines, deliberately truncated with an ellipsis, so
> it reads as one very large number. Above it the word `ACCUMULATOR`.
>
> **Column 4 — "Three answers".** Three stacked rounded pill shapes, each with a small icon on
> the left: a green `#059669` check mark, a green `#059669` crossed-out circle, and a green
> `#059669` bracket enclosing three dots. Beside them, one short label each:
> `IS PRESENT`, `NEVER EXISTED`, `NOTHING MISSING`.
>
> Below the four columns, separated by a horizontal rule, a narrow full-width band in `#E8710A`
> containing three small circles joined by thin lines to a fourth circle, with a small gate or
> turnstile pictogram at the right end. One label inside the band: `SHARED MODEL`. A short
> upward arrow from the gate into the accumulator column, in `#059669`.
>
> Across the very top, one line of large bold sans-serif text, centred:
> `PROVING NOTHING IS MISSING`.
>
> The ONLY text anywhere in the image is: `PROVING NOTHING IS MISSING`, `RECORDS`, `COMMIT`,
> `ACCUMULATOR`, `IS PRESENT`, `NEVER EXISTED`, `NOTHING MISSING`, `SHARED MODEL`, and the
> truncated hexadecimal string. No other words, no captions, no numbers, no watermark, no
> logo. Set every label in a clean geometric sans-serif, large, with wide letter spacing.

---

## 2 · System architecture, blockchain and AI

> A detailed technical architecture diagram for an academic paper, flat vector, 4:3 landscape,
> off-white `#F7F8FA` background, thin `#E5E7EB` borders, no shadows, no 3-D, no photorealism.
> Three horizontal bands stacked with clear vertical gaps between them, each band a rounded
> rectangle with a 2px coloured border and a white fill.
>
> **Top band, blue `#2563EB` border.** Five equal boxes in a row, joined left to right by thin
> grey arrows. Each box has a small pictogram above its label: a document, a binary tree of
> dots, a padlock, a stamp with two overlapping signature marks, a hexagon around a large dot.
> Labels, one per box: `CAPTURE`, `MERKLE`, `ENCRYPT`, `WITNESS`, `SEAL`. At the band's left
> edge, rotated vertically, the word `RECORDS`.
>
> **Middle band, blue `#2563EB` border, drawn taller and heavier than the others to read as the
> centre of the system.** Inside it, on the left, a column of three small boxes labelled
> `IDENTITY`, `ENDORSE`, `ORDER`. In the middle, one large rounded square in solid `#2563EB`
> with white text inside reading `RSA GROUP`, with four thin arrows radiating from it to four
> small boxes arranged around it, labelled `WITNESS`, `ABSENCE`, `BATCH`, `DELAY`. On the
> right, two stacked boxes labelled `SEALS` and `GATE`. Along the bottom edge of the band, a
> horizontal row of six small linked squares representing a block chain, each joined to the
> next by a short link, the leftmost darker. At the band's left edge, rotated vertically, the
> word `LEDGER`.
>
> **Bottom band, orange `#E8710A` border.** Six small circles in a row representing factories,
> each with a thin arrow rising to a single box labelled `AGGREGATE`, which connects rightward
> to a box labelled `CANDIDATE`. Below the circles, a small cylinder pictogram labelled
> `MEMORY`. At the band's left edge, rotated vertically, the word `LEARNING`.
>
> **Between the bands:** from the top band down into the middle band, one thick blue arrow. From
> the bottom band up into the middle band, one thick orange arrow. From the middle band down
> into the bottom band, one thick green `#059669` arrow, drawn beside the orange one and
> pointing the opposite way, so the pair reads as a request and a decision.
>
> The ONLY text in the image is: `RECORDS`, `LEDGER`, `LEARNING`, `CAPTURE`, `MERKLE`,
> `ENCRYPT`, `WITNESS`, `SEAL`, `IDENTITY`, `ENDORSE`, `ORDER`, `RSA GROUP`,
> `ABSENCE`, `BATCH`, `DELAY`, `SEALS`, `GATE`, `AGGREGATE`, `CANDIDATE`, `MEMORY`. Every label
> is one or two words in clean geometric sans-serif, generously spaced, no sentences, no
> captions, no numbers, no legend, no watermark.

---

## 3 · Swimlane flow

> A swimlane process diagram in the style of a systems paper, flat vector, wide 16:9 landscape,
> off-white `#F7F8FA` background, no shadows, no 3-D, no photorealism.
>
> Five horizontal lanes of equal height, stacked, separated by thin `#E5E7EB` rules, each lane
> labelled at the far left in a narrow grey `#6B7280` header column with the label rotated
> vertically. Lane labels top to bottom: `FACTORY`, `WITNESS`, `LEDGER`, `AUDITOR`, `BUYER`.
> The `LEDGER` lane has a very light blue `#2563EB` tint at about 8 percent opacity so it reads
> as the shared medium; all other lanes are white.
>
> Time runs left to right across five evenly spaced columns. Draw the process as rounded boxes
> placed in the appropriate lane and column, joined by arrows that cross lanes vertically where
> a handoff happens. Use `#2563EB` for boxes in the ledger lane and `#6B7280` outlines with
> white fill everywhere else.
>
> Column 1: a box in `FACTORY` labelled `HASH`. Column 2: a box in `WITNESS` labelled
> `COUNTERSIGN`, with an arrow reaching it from the `FACTORY` box, and a small dashed arrow
> coming down into it from the `LEDGER` lane to show the witness was assigned rather than
> chosen. Column 3: a box in `LEDGER` labelled `COMMIT`, receiving an arrow up from `WITNESS`.
> Column 4: a box in `FACTORY` labelled `SEAL`, with an arrow down into a box in `LEDGER`
> labelled `EPOCH`. Column 5: a box in `BUYER` labelled `REQUEST` with an arrow up into a box
> in `LEDGER` labelled `PROOF`, and from that box two arrows: one green `#059669` arrow down to
> a box in `BUYER` labelled `COMPLETE`, and one red-orange `#E8710A` arrow down to a smaller box
> in `AUDITOR` labelled `MISSING`.
>
> Draw the `MISSING` box with a thicker `#E8710A` border than everything else, so the failure
> path is the most visually prominent element on the canvas.
>
> Along the very bottom, spanning the full width beneath all lanes, a thin horizontal arrow in
> `#6B7280` pointing right, with three evenly spaced small tick marks on it and one label at its
> right end: `TIME`.
>
> The ONLY text in the image is: `FACTORY`, `WITNESS`, `LEDGER`, `AUDITOR`, `BUYER`, `HASH`,
> `COUNTERSIGN`, `COMMIT`, `SEAL`, `EPOCH`, `REQUEST`, `PROOF`, `COMPLETE`, `MISSING`, `TIME`.
> One or two words per box, clean geometric sans-serif, large and generously spaced. No
> sentences, no captions, no numbers, no legend, no watermark, no extra decoration.
