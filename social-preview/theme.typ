// — palette: dark technical background, accents from the README chart —
#let BG      = rgb("#0d1117")
#let PANEL   = rgb("#161b22")
#let BORDER  = rgb("#30363d")
#let FG      = rgb("#e6edf3")
#let MUTED   = rgb("#8b949e")
#let ORANGE  = rgb("#E8862A")
#let TEAL    = rgb("#2BB3B5")   // lighter than the chart teal, readable on dark

// — fonts —
#let SANS = ("DejaVu Sans", "Liberation Sans", "Arial")
#let MONO = ("DejaVu Sans Mono", "Liberation Mono", "Courier New")

// — terminal panel with a command and its JSON answer —
#let terminal(body) = block(
  fill: PANEL, stroke: 0.6pt + BORDER, radius: 5pt,
  inset: (x: 14pt, y: 12pt), width: 100%,
)[
  #set text(font: MONO, size: 10.5pt, fill: FG)
  #set par(leading: 0.55em)
  #set smartquote(enabled: false)
  #body
]

// — the four answer types as small chips —
#let chip(label, color) = box(
  stroke: 0.8pt + color, radius: 3pt, inset: (x: 7pt, y: 4pt),
  text(font: MONO, size: 9.5pt, fill: color, label),
)
