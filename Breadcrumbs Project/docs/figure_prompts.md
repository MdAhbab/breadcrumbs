# Figure prompts for a high-resolution image generator

Three prompts, one per figure. Each is written to be executed without asking a follow-up
question: every element has a position, a size, a colour, a stroke weight and a reason for
being there. Where a number is given as a percentage it is a percentage of the canvas width
or height, measured from the top-left corner.

## Read this before generating anything

**Image models garble text.** They handle one to three words in large type well, and they
handle sentences, small captions, or more than about twenty separate strings badly. Every
prompt below therefore ends with a closed list of the only words allowed in that image. If a
word is not on the list, it must not appear. Generate at the largest size the tool offers,
then check every label letter by letter. A figure containing "Continiuty Gate" is worse than
no figure at all, because a judge who spots it stops trusting the rest of the page.

**If a label comes out wrong twice, stop and say so.** The paper already draws figures 1 to 4
in TikZ with exact typography. Any of these three can be produced the same way, or the
generated image can be used as a background with a clean TikZ label layer placed on top.
That fallback is cheap and it always works.

**Shared palette.** Used across all three so the set reads as one system.

| Role | Hex | Used for |
|---|---|---|
| Ledger blue | `#2563EB` | Anything that is on-chain: blocks, seals, the accumulator |
| Learning orange | `#E8710A` | The learning plane: clients, updates, the model |
| Proof green | `#059669` | A check that succeeded, a proof that verified |
| Warning ochre | `#B45309` | A bound that holds but does not prevent |
| Secondary grey | `#6B7280` | Documents, arrows, anything off-chain |
| Text near-black | `#111827` | All type |
| Rule light grey | `#E5E7EB` | Borders, separators, grid lines |
| Background off-white | `#F7F8FA` | Canvas |

The palette is colour-blind safe and survives greyscale printing, because green and blue are
separated in lightness as well as hue. **No gradients, no drop shadows, no glow, no bevels,
no 3-D, no photorealism, no isometric projection.** Flat vector only, as though drawn in
Illustrator for a journal.

**Typography.** One geometric sans-serif throughout, in the spirit of Inter, Aktiv Grotesk or
Helvetica Now. Headings in uppercase with wide letter spacing, roughly 0.08em. Labels in
uppercase, medium weight. No serif faces anywhere. No script or handwriting. Monospace only
where a prompt explicitly asks for a hexadecimal string.

---

## 1 · Graphical abstract: "Proving nothing is missing"

**Purpose.** This is the single image a judge sees before reading anything. It has to carry
one idea: that this system proves the absence of a record, not merely the presence of one.
Almost every ledger project can show you that a record exists. Very few can show you that
nothing has been quietly left out. That asymmetry is the whole pitch and the figure has to
land it in about four seconds.

**Canvas.** 16:9 landscape, minimum 3840 by 2160. Background `#F7F8FA` flat, edge to edge.
Outer margin of 6% on all four sides, kept completely empty. Nothing bleeds off the canvas.

**Overall structure.** A title band across the top, a four-column main register in the upper
two thirds, and a full-width horizontal band across the lower third. A single long arrow runs
beneath the four columns and ties them together. The composition reads strictly left to right.

**Title band, top 12% of canvas.** One line of text, centred horizontally, set in the
geometric sans at roughly 5% of canvas height in cap height, bold, uppercase, letter spacing
0.1em, colour `#111827`:

`PROVING NOTHING IS MISSING`

Nothing else in this band. Below it, a full-width hairline rule in `#E5E7EB`, 2px at 4K,
spanning from the left margin to the right margin.

**Main register, from 16% to 62% of canvas height.** Four columns of equal width, separated by
three thin vertical rules in `#E5E7EB`, each rule running the full height of the register.
Column centres sit at 18%, 39%, 61% and 82% of canvas width. Each column has a single-word
heading at its top, set at 1.6% cap height, uppercase, medium weight, letter spacing 0.08em,
colour `#6B7280`, and a graphic centred beneath it.

*Column 1, heading `RECORDS`.* Three flat document pictograms in `#6B7280`, drawn as rounded
rectangles with a 2% corner radius, in portrait proportion roughly 3 wide by 4 tall,
overlapping by about a third, fanned so the leftmost is lowest and the rightmost highest.
Stroke weight 3px at 4K, no fill, or a very light `#E5E7EB` fill. Inside the front document,
four short horizontal lines suggesting ruled text, plus one small circle in the lower right
suggesting a stamp. Inside the middle document, a single short wavy line suggesting a
signature. The rearmost document is plain. These represent a payroll register, a safety
inspection and a chemical inventory, but they must not be labelled as such.

*Column 2, heading `COMMIT`.* A regular hexagon in `#2563EB`, flat-topped, stroke 4px at 4K,
no fill, sized so its width is about 70% of the column width. Inside it, a binary Merkle tree
drawn as seven small filled circles in `#2563EB`: four along the bottom row, two in the
middle row, one at the apex. Join them with thin straight lines, 2px, in `#2563EB` at 50%
opacity. From the apex circle, a short line exits vertically through the top edge of the
hexagon and ends in a small solid arrowhead. The hexagon is the standard shape for a block in
this deck, so keep it geometrically exact, not hand-drawn.

*Column 3, heading `ACCUMULATOR`.* The visual centre and the largest single element on the
canvas. A rounded square in `#2563EB`, corner radius about 4% of its own width, stroke 6px at
4K, filled with `#2563EB` at 6% opacity. Its side length is about 90% of the column width,
noticeably larger than the hexagon in column 2. Inside it, a hexadecimal string set in
monospace, `#111827`, wrapped over exactly three lines, centred, ending in a three-dot
ellipsis, for example `3f8a2c91d4e6` on the first line and similar strings below. The string
must read as one very large number that has been truncated. Do not draw a lock, a shield, a
padlock or a keyhole anywhere near it.

*Column 4, heading `THREE ANSWERS`.* Three stacked rounded pill shapes, full column width,
each about 12% of canvas height, separated by gaps of about 4% of canvas height. Corner radius
equal to half the pill height, so the ends are fully round. Each pill has a 3px stroke and a
6% opacity fill. Top pill in `#059669` with a check mark icon at its left end. Middle pill in
`#059669` with a crossed-out circle icon at its left end. Bottom pill in `#059669` with a
bracket enclosing three dots at its left end. To the right of each icon, one label in
`#111827`, uppercase, 1.4% cap height:

`IS PRESENT`, `NEVER EXISTED`, `NOTHING MISSING`

The middle pill is the unusual claim. If the composition allows one element to be emphasised
without adding text, give the middle pill a slightly heavier stroke, 4px rather than 3px.

**Connecting arrow, at about 66% of canvas height.** A single horizontal line in `#6B7280`,
3px at 4K, running from the left edge of column 1 to the right edge of column 4, with a solid
arrowhead at the right end only. It passes beneath all four columns. Three small vertical
ticks rise from it, one at each column boundary, 1% of canvas height, in `#E5E7EB`.

**Lower band, from 72% to 94% of canvas height.** A full-width rounded rectangle, corner
radius 1% of canvas width, stroke 3px in `#E8710A`, filled `#E8710A` at 5% opacity. Inside it,
on the left two thirds, six small circles in `#E8710A` arranged in a loose ring, each joined
by a thin 2px line to a single larger circle at the ring's centre. This is six factories and a
shared model. On the right third, a turnstile pictogram: two vertical posts with three
horizontal bars between them, in `#E8710A`, stroke 3px. Centred in the band's left portion,
one label in `#111827`, uppercase, 1.6% cap height:

`SHARED MODEL`

From the turnstile, one short arrow in `#059669`, 3px with a solid arrowhead, rises vertically
and ends just below the accumulator square in column 3. This is the only element that crosses
between the two registers, and it should be visually obvious.

**The only text allowed anywhere in this image:** `PROVING NOTHING IS MISSING`, `RECORDS`,
`COMMIT`, `ACCUMULATOR`, `THREE ANSWERS`, `IS PRESENT`, `NEVER EXISTED`, `NOTHING MISSING`,
`SHARED MODEL`, and the truncated hexadecimal string. No other words. No captions. No page
numbers. No watermark. No logo. No signature. No axis labels. No legend.

**Negative prompt.** No photorealism, no 3-D, no isometric view, no perspective, no drop
shadows, no gradients, no glow, no neon, no dark background, no blockchain clichés such as
chain links, padlocks, coins, Bitcoin symbols, glowing cubes, circuit-board traces, hooded
figures or globes. No stock-illustration people. No hands. No screens or devices. No arrows
other than those specified. No decorative dots or particles.

**Check before accepting.** Every word from the closed list is spelled correctly. The
accumulator square is visibly the largest element. The middle pill reads `NEVER EXISTED`. The
green arrow rises from the turnstile into column 3 and nowhere else. There are exactly three
pills, exactly seven Merkle circles and exactly six factory circles.

---

## 2 · System architecture: three planes

**Purpose.** To show that the ledger sits between the documents and the model, and mediates
both. The common misreading of this project is that it is an AI system with a blockchain
bolted on. The figure has to make the opposite obvious: the ledger is the load-bearing part,
and the learning plane is something it governs.

**Canvas.** 4:3 or 5:4 portrait-ish landscape, minimum 3200 by 2400. Background `#F7F8FA`.
Outer margin 6%, empty.

**Overall structure.** Three horizontal bands stacked vertically, each a rounded rectangle
with a 1% corner radius. They are separated by gaps of 5% of canvas height. The middle band is
the widest and has the heaviest stroke, because it is the one that matters. Short vertical
connectors run through the gaps between bands.

The vertical order is deliberate and must not be rearranged. Documents are at the top because
that is where the process starts, in a factory office. The learning plane is at the bottom
because it is the last thing added and the least essential: remove it and the ledger still
works, whereas remove the ledger and the learning plane has nothing holding it honest. The
permissioned ledger sits in the middle because it physically mediates between the two, and a
reader should be able to see that neither outer band touches the other directly. Every path
between the top band and the bottom band passes through the middle one. Do not draw any arrow
that connects band A to band B directly, however tempting it looks compositionally, because
that single line would contradict the paper's central claim.

Width is the second signal. Band C is wider than the two bands it separates, so its rounded
rectangle visibly overhangs them on both the left and the right by about 4% of canvas width on
each side. This overhang should be obvious at a glance and is the fastest way for a reader to
see which plane is load-bearing. Do not centre all three bands at equal width.

**Band A, top, from 10% to 33% of canvas height. Heading `RECORD CUSTODY`.**
Rounded rectangle, stroke 3px `#6B7280`, fill `#6B7280` at 4% opacity, spanning 84% of canvas
width, centred. The heading sits at the band's top-left inside corner, uppercase, 1.5% cap
height, `#6B7280`, letter spacing 0.08em.

Inside, four elements evenly spaced left to right, joined by three short horizontal arrows in
`#6B7280`, 2px with small solid arrowheads:

1. A document pictogram in `#6B7280`, as described in figure 1, with ruled lines inside.
2. A small binary Merkle tree: seven circles in `#2563EB`, four across the base, two, then
   one, joined by 2px lines.
3. A padlock-free "vault" glyph: a plain rounded square in `#6B7280`, stroke 3px, containing
   a single centred dot. This is off-chain encrypted storage. Do not draw a padlock.
4. A single small document with one line highlighted in `#059669` and a green check mark
   beside it. This is a selective disclosure.

Beneath these four, one label each, uppercase, 1.2% cap height, `#111827`:
`CAPTURE`, `HASH`, `STORE OFF-CHAIN`, `DISCLOSE ONE ITEM`

**Band C, middle, from 38% to 62% of canvas height. Heading `PERMISSIONED LEDGER`.**
This is the widest band, spanning 92% of canvas width, and the visually dominant one. Stroke
5px `#2563EB`, fill `#2563EB` at 7% opacity, corner radius 1%.

Inside, a horizontal row of five flat-topped hexagons in `#2563EB`, stroke 4px, no fill, each
about 9% of canvas width across, joined edge to edge by short 3px horizontal segments so they
read as a chain of blocks without any chain-link imagery. Above the row, centred, the heading.

Below the hexagon row, inside the same band, four small rounded rectangles in a row, stroke
2px `#2563EB`, fill white, each labelled in monospace, 1.1% cap height, `#111827`:
`doccustody`, `anchor`, `fedmodel`, `reputation`

These are the four smart contracts and their names must be lowercase monospace exactly as
written, because they are code identifiers.

At the band's right end, outside the hexagon row but inside the band, a small circular badge
in `#2563EB`, stroke 3px, containing a stylised certificate glyph: a rounded rectangle with a
ribbon at its lower edge, drawn as two short angled tails descending from the rectangle's
bottom corners. One label beneath it, uppercase, 1.1% cap height: `MSP IDENTITY`

The hexagon chain needs care, because it is the element most likely to be rendered as a
blockchain cliché. The five hexagons are identical in size and orientation, flat-topped, sitting
on a shared horizontal centre line, with equal gaps between them bridged by a short straight
segment. There are no links, no interlocking rings, no glowing edges and no numbers inside the
hexagons. They are empty outlines. The impression to aim for is a row of cells in a technical
drawing, not a graphic about cryptocurrency. If the generator insists on adding chain links
between them, drop the connecting segments entirely and let the hexagons sit as five separate
outlines with even spacing, which reads correctly and cannot be misinterpreted.

The four contract names sit in a single evenly spaced row beneath the hexagons, aligned to the
same baseline, each in its own small rounded rectangle of identical size. Their boxes are
noticeably smaller than the hexagons, roughly half the height, because they are components
inside the ledger rather than peers of it. Keep the four names in the order given: it runs from
the contract that handles documents, through the one that anchors them, to the one that governs
the model, to the one that tracks behaviour, which is the order the report introduces them.

**Band B, bottom, from 67% to 90% of canvas height. Heading `LEARNING PLANE`.**
Rounded rectangle, stroke 3px `#E8710A`, fill `#E8710A` at 4% opacity, spanning 84% of canvas
width, centred.

Inside, on the left, six small circles in `#E8710A`, stroke 3px, arranged in two rows of
three. Each has a short arrow pointing right, in `#E8710A`, 2px. In the middle, a single
larger circle in `#E8710A`, stroke 4px, fill `#E8710A` at 8% opacity. On the right, a
turnstile glyph: two vertical posts with three horizontal bars, `#E8710A`, stroke 3px.

Beneath these, three labels, uppercase, 1.2% cap height, `#111827`:
`SIX FACTORIES`, `AGGREGATE`, `CONTINUITY GATE`

**Cross-plane connectors, in the gaps.** Two pairs of short vertical arrows, 3px, with solid
arrowheads, running through the 5% gaps:

- Between band A and band C: one arrow pointing down in `#2563EB`, one pointing up in
  `#6B7280`. Beside them, two short labels stacked, 1% cap height, `#6B7280`:
  `COMMIT ROOT` and `PROOF`
- Between band C and band B: one arrow pointing up in `#E8710A`, one pointing down in
  `#059669`. Beside them: `CANDIDATE` and `DECISION`

The arrows should be short, no more than the height of the gap, and must not cross each other.

**The only text allowed anywhere in this image:** `RECORD CUSTODY`, `CAPTURE`, `HASH`,
`STORE OFF-CHAIN`, `DISCLOSE ONE ITEM`, `PERMISSIONED LEDGER`, `doccustody`, `anchor`,
`fedmodel`, `reputation`, `MSP IDENTITY`, `LEARNING PLANE`, `SIX FACTORIES`, `AGGREGATE`,
`CONTINUITY GATE`, `COMMIT ROOT`, `PROOF`, `CANDIDATE`, `DECISION`. That is nineteen strings,
which is at the upper limit of what an image model handles. If the tool struggles, drop
`MSP IDENTITY` first, then `COMMIT ROOT` and `PROOF`.

**Negative prompt.** As figure 1, plus: no chain-link imagery between the hexagons, no
padlocks, no cloud shapes, no server racks, no database cylinders, no brain or neural-network
imagery in the learning plane, no robot, no humanoid figures, no world map, no dashboard
screenshots, no code editor windows.

**Check before accepting.** The middle band is visibly the widest and heaviest. There are
exactly five hexagons and exactly four contract names in lowercase monospace. There are
exactly six small circles in the learning plane. No arrow crosses another. `CONTINUITY GATE`
is spelled correctly, which is the label this figure most often gets wrong.

---

## 3 · Swimlane flow: the life of one record

**Purpose.** To answer "what actually happens, step by step" for a reader who does not trust
architecture diagrams. This is the figure that shows the system as a sequence of
responsibilities held by different organisations, none of whom has to trust the others.

**Canvas.** 16:9 landscape, minimum 3840 by 2160. Background `#F7F8FA`. Outer margin 5%.

**Overall structure.** Four horizontal swimlanes stacked vertically, each spanning the full
usable width, separated by hairline rules in `#E5E7EB`, 2px. A lane-title column occupies the
leftmost 16% of the usable width, separated from the flow area by a slightly heavier vertical
rule, 3px `#E5E7EB`, running the full height of all four lanes. Time runs left to right across
the flow area. Each lane is about 20% of canvas height.

**Lane titles**, in the left column, right-aligned, uppercase, 1.3% cap height, letter
spacing 0.08em, vertically centred in each lane:

`FACTORY` in `#6B7280`, `LEDGER` in `#2563EB`, `WITNESS` in `#B45309`, `BUYER` in `#059669`

**Why four lanes.** Each lane is an organisation with its own private key and its own reason
to be suspicious of the others. That is the point of the figure: no lane trusts any other lane,
and the sequence still works. A reader who takes only one thing from this image should take
that the witness lane and the buyer lane are separate from the factory lane, because a system
where the factory could occupy all four lanes would prove nothing at all.

**Nodes.** Every step is a rounded rectangle, corner radius 0.8% of canvas width, stroke 3px,
white fill, about 11% of canvas width by 7% of canvas height. Each node carries one label in
`#111827`, uppercase, 1.1% cap height, centred, at most two words. Node stroke colour matches
its lane. All nodes share the same size, with the single exception noted for `COMMIT`, so that
no step looks more important than another purely because it is larger. Vertical centring within
a lane must be exact: a node that floats high or low in its lane reads as an error.

Nodes must not overlap the lane rules, and no node may sit in the left title column. Horizontal
positions are given as the centre of each node, so a node at 20% has its left edge at about
14.5% and its right edge at about 25.5%.

**Lane 1, FACTORY.** Two nodes. The first at about 20% of canvas width, labelled `SUBMIT`.
The second at about 62%, labelled `SEAL PERIOD`.

**Lane 2, LEDGER.** Three nodes. At about 34%, labelled `ENDORSE`. At about 48%, labelled
`COMMIT`. At about 76%, labelled `ANCHOR EPOCH`. The `COMMIT` node should be drawn as a
flat-topped hexagon rather than a rounded rectangle, to match the block shape used in the
other two figures, and should have a 4px stroke rather than 3px.

**Lane 3, WITNESS.** One node only, at about 41%, labelled `COUNTER-SIGN`, stroke `#B45309`.
Beside it, a small dice or coin glyph in `#B45309`, stroke 2px, no more than 3% of canvas
width, indicating that the witness was assigned by chance rather than chosen. Do not label the
glyph.

**Lane 4, BUYER.** Two nodes. At about 88%, labelled `VERIFY`. Below and slightly right of it,
a smaller rounded rectangle, about 8% by 5%, stroke 2px `#059669`, containing three short
horizontal lines stacked, each with a small green check mark at its left end. This is the
three-check verification panel and it must show exactly three lines, because collapsing them
into one is the specific mistake the paper argues against.

The three lines are not decoration and their count carries an argument. A record is accepted
only when three independent checks agree, and one of those three could in principle be forged
by whoever holds the factorisation of the accumulator modulus. Showing a single combined tick
would throw away exactly the defence that makes that trapdoor survivable. So three lines, never
two, never four, and never one large tick. If space is tight, shrink the panel rather than
reducing the number of lines. Do not add a percentage, a score, or the word `VERIFIED` inside
the panel.

**Why the witness lane holds only one node.** The witness does one thing and does it once: it
counter-signs a record it was assigned rather than chose. Giving that lane more nodes would
suggest an ongoing relationship between the factory and its counter-signatory, which is the
arrangement this design exists to prevent. The single node, with a lane otherwise empty, is
itself the message. Leave the rest of that lane genuinely blank.

**Arrows.** All arrows 3px with small solid arrowheads. Within a lane, horizontal, in the
lane's colour. Between lanes, vertical or gently stepped, never diagonal across more than one
lane, in `#6B7280`. The required connections, in order:

`SUBMIT` right to `ENDORSE`, `ENDORSE` down to `COUNTER-SIGN`, `COUNTER-SIGN` up to `COMMIT`,
`COMMIT` right to `SEAL PERIOD`, `SEAL PERIOD` right to `ANCHOR EPOCH`, `ANCHOR EPOCH` down to
`VERIFY`.

That is six arrows and no others. No arrow may pass through a node.

**Time axis.** Along the very bottom, below the last lane, a horizontal line in `#E5E7EB`,
2px, with three small ticks and three labels beneath, uppercase, 1% cap height, `#6B7280`:
`DAY 1`, `MONTH END`, `QUARTER`

The axis is there to make one point that the node sequence alone cannot: these steps happen on
very different timescales. Submission and endorsement are seconds apart. Sealing a period waits
for the month to close. Anchoring an epoch and a buyer's verification may be a quarter later.
A reader who assumes the whole flow happens in one sitting will misjudge what the system costs
to run, so the spacing between ticks should be visibly uneven, matching the node positions
rather than being evenly divided.

Position the ticks at roughly 20%, 62% and 88% of the flow area, so they align with `SUBMIT`,
`SEAL PERIOD` and `VERIFY` respectively.

**The only text allowed anywhere in this image:** `FACTORY`, `LEDGER`, `WITNESS`, `BUYER`,
`SUBMIT`, `ENDORSE`, `COUNTER-SIGN`, `COMMIT`, `SEAL PERIOD`, `ANCHOR EPOCH`, `VERIFY`,
`DAY 1`, `MONTH END`, `QUARTER`. Fourteen strings. No other words, no captions, no numbers
other than the `1` in `DAY 1`.

**Negative prompt.** As figure 1, plus: no calendar icons, no clock faces, no stopwatch, no
progress bars, no percentage figures, no human avatars in the lanes, no factory building
illustrations, no shipping or garment imagery, no flags, no currency symbols.

**What this figure deliberately leaves out.** There is no error path, no rejection branch and
no retry loop. Those exist in the system and are tested, but drawing them here would double the
line count and bury the happy path that a first-time reader needs. There is also no
representation of the learning plane, which belongs to figure 2. Resist adding either.

**Check before accepting.** There are exactly four lanes and exactly eight nodes: two in
`FACTORY`, three in `LEDGER`, one in `WITNESS`, and one node plus one small panel in `BUYER`.
`COMMIT` is a hexagon and everything else in that lane is a rounded rectangle. The verification
panel under `VERIFY` has exactly three lines. There are exactly six arrows and none crosses a
node. `COUNTER-SIGN` is hyphenated correctly, which is the label this figure most often gets
wrong. The lane titles are right-aligned against the vertical rule. Print the result in
greyscale and confirm the four lane colours are still distinguishable by position and label,
since hue alone will not survive.

---

## After generation

Put the accepted images in `figures/` as `abstract.png`, `architecture.png` and `flow.png` at
full resolution, and keep the prompt that produced each one in a sibling `.txt` file. If a
figure has to be regenerated later, the prompt is the only way to get a consistent result, and
a set of three figures that do not match visually is worse than one good figure alone.
