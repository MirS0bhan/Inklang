# InkLang

## *this project has been wrote by LLMs*

**A declarative YAML language for generating SVG designs, powered by Inkscape.**

Write one YAML file that describes a design, fill it from CSV/JSON data, and get
clean, hand-editable SVG out — optionally exported to PNG or PDF through
Inkscape. InkLang is built to generate many variations of the same design (think
business cards, certificates, labels, social posts) without touching a GUI.

The pipeline is:

```
read YAML  →  fill {{variables}}  →  parse  →  validate  →  build SVG  →  write .svg
                                                                          ↘ export PNG/PDF
```

- **YAML** describes the design (PyYAML).
- **Jinja2** fills `{{variables}}` from data.
- **Pydantic** validates the schema with plain-English errors.
- **inkex** (Inkscape's own SVG library) builds the SVG elements — no string
  concatenation.
- **Inkscape** rasterizes / converts to PNG and PDF.

This is the MVP: four element types — `text`, `rect`, `circle`, `image`. No
gradients, groups, transforms, filters, or clipping yet.

---

## Requirements

- **Python ≥ 3.13**
- **Inkscape ≥ 1.x** — only needed for PNG/PDF export. Rendering to SVG works
  without it.

## Installation

This project uses [`uv`](https://docs.astral.sh/uv/) for dependency management.

```bash
git clone https://github.com/MirS0bhan/Inklang && cd inklang
uv sync         
```

That installs the `inklang` console script inside the project's virtualenv.
Run it through `uv run`:

```bash
uv run inklang --help
```

## Verifying Inkscape is available

Exporting to PNG or PDF shells out to the `inkscape` executable. Check that it is
on your `PATH`:

```bash
inkscape --version        # expect something like "Inkscape 1.4 ..."
which inkscape            # /usr/bin/inkscape
```

If it's missing, install it from your package manager (`apt install inkscape`,
`brew install --cask inkscape`, or from [inkscape.org](https://inkscape.org)).
Rendering to SVG does **not** require Inkscape — only `inklang export` and
`batch --format png|pdf` do. When Inkscape can't be found, InkLang fails with a
clear message rather than a traceback.

---

## Quick start

The repo ships an example: a 3.5"×2" business card. The design lives in
`examples/business_card.yaml`, and `examples/clients.csv` holds four people to
print cards for.

### `render` — one design, one record → one SVG

```bash
uv run inklang render examples/business_card.yaml \
  --data examples/clients.csv \
  --out card.svg
```

`--data` accepts a JSON object, a single-element JSON list, or a CSV file (the
**first** row is used). If your YAML has no `{{variables}}`, you can omit
`--data` entirely.

### `batch` — one design, many records → one file per row

```bash
uv run inklang batch examples/business_card.yaml \
  --data examples/clients.csv \
  --out-dir out/cards
```

This writes `out/cards/Ada_Lovelace.svg`, `Grace_Hopper.svg`, etc. — one file
per CSV row. By default each file is named after the `name` column (override with
`--name-field`); values are sanitized to be filesystem-safe.

Add `--format png` (or `pdf`) to also export each design via Inkscape:

```bash
uv run inklang batch examples/business_card.yaml \
  --data examples/clients.csv \
  --out-dir out/cards --format png --dpi 150
```

### `export` — turn an existing SVG into PNG or PDF

```bash
uv run inklang export card.svg --format png --out card.png
uv run inklang export card.svg --format pdf --out card.pdf
```

If you omit `--format`, it's inferred from the `--out` extension (`.png`/`.pdf`).

---

## Designing in YAML

A design file has a header and a list of `elements`, drawn top-to-bottom (later
elements render on top of earlier ones):

```yaml
design: Business Card        # a human label; shown in errors/logs
size: "350x200"              # WIDTHxHEIGHT, in pixels
background: "#ffffff"        # optional full-canvas background colour

elements:
  - type: rect
    position: [0, 0]
    size: [350, 200]
    fill: "#ffffff"
```

Any string value in the file can contain `{{variables}}`, including colours and
positions — they're filled from your data before validation. So `fill: "{{accent}}"`
pulls each person's accent colour out of the CSV.

### Element types

**`text`**

```yaml
- type: text
  content: "Hello, {{name}}!"
  position: [24, 72]          # [x, y] of the text baseline, in px
  color: "#1a1a1a"            # default "#000000"
  font:
    family: Helvetica         # default "Arial"
    size: 26                  # px, default 16
    weight: bold              # optional: "normal" | "bold" | a number
    style: italic             # optional: "normal" | "italic"
```

**`rect`**

```yaml
- type: rect
  position: [0, 0]            # top-left corner [x, y]
  size: [350, 8]              # [width, height]
  fill: "#7b2ff7"
  corner_radius: 8            # optional, rounded corners (px)
  stroke:                     # optional outline
    color: "#333333"
    width: 2                  # px, default 1
    dash: [4, 2]              # optional dash/gap pattern
```

**`circle`**

```yaml
- type: circle
  center: [312, 40]           # [cx, cy]
  radius: 14
  fill: "#7b2ff7"
  stroke: { color: "#000000", width: 1 }   # optional
```

**`image`**

```yaml
- type: image
  src: logo.png               # path or URL (Inkscape resolves it on export)
  position: [10, 10]
  size: [40, 40]
  opacity: 0.8                # optional, 0.0–1.0, default 1.0
```

### Data files

`--data` accepts:

- **`.csv`** — one record per row, header row supplies the keys.
- **`.json`** — a single object (one record), or a list of objects (one record
  each).
- **omitted** — useful for designs with no variables; treated as a single empty
  record.

```csv
name,title,company,phone,email,accent
Ada Lovelace,Founder & CEO,Analytical Engines Ltd,+1 555 0100,ada@example.com,#7b2ff7
```

---

## Errors

InkLang aims to fail with a sentence, not a stack trace. A few examples:

```
Error: Missing variable: 'accent' is used in the design but was not provided
in the data (used in line: # Coloured top band — its colour comes from the
data ({{accent}}).).

Error: The design file is not valid InkLang:
  • elements[0].circle.radius: Field required

Error: Inkscape was not found on your PATH. Install it to export PNG or PDF.
```

Validation errors point at the offending element and field (`elements[0]` is the
first element, `elements[1]` the second, and so on). App errors exit `1`; usage
errors (bad flags, missing `--out`) exit `2`.

---

## Testing

```bash
uv run pytest -q          # 41 tests; the Inkscape call is mocked
```

The exporter tests patch the Inkscape invocation, so the full suite passes
without Inkscape installed.

---

## Setup quirks (inkex outside Inkscape)

`inkex` is Inkscape's Python SVG library, designed to run *inside* Inkscape
extensions. Using it standalone to build SVGs works, but has a few rough edges
worth recording:

1. **It installs and runs fine outside Inkscape.** A plain `uv add inkex` (or
   `pip install inkex`) pulls a working package. Importing `inkex`,
   `inkex.elements`, and `inkex.command` works with no Inkscape on the `PATH` —
   only the `inkscape.command.inkscape(...)` *call* needs the binary. So building
   and writing SVG needs nothing extra; only PNG/PDF export needs Inkscape.

2. **Pretty-printing needs an explicit indent.** lxml's `pretty_print=True` only
   preserves whitespace that was already in a *parsed* tree; for a tree built
   programmatically it does nothing, leaving the SVG on one long line. We call
   `lxml.etree.indent(tree, space="  ")` before writing so the output is
   human-readable and friendly to edit in Inkscape.

3. **Jinja substitution happens *before* YAML parsing.** This is the sharpest
   trap. The pipeline fills `{{variables}}` on the raw text and *then* parses the
   YAML, which means a `{{...}}` in a **comment** is treated as a variable too.
   Keep placeholder braces out of YAML comments (or write them as `{{ '{' '{' }}}`
   if you must). The example design file documents this at its top.

4. **Style keys use dashes, attributes use underscores.** Through inkex, style
   properties go in an element's `.style` dict with CSS names
   (`stroke-width`, `font-family`), while plain SVG attributes use `elem.set(...)`
   with names like `stroke_width`. Mixing them silently no-ops the property, so
   the renderer is careful to route each value to the right place.

---

## Roadmap

The MVP deliberately covers only `text`, `rect`, `circle`, and `image`. Likely
next steps: gradients, groups, transforms, and clipping paths; a richer font API;
and a watcher mode for live preview.
