// Palette, fonts and helpers shared with the social preview
#import "../social-preview/theme.typ": *

// — light card, used once to break the rhythm —
#let PAPER   = rgb("#f6f3ee")
#let INK     = rgb("#1c2128")
#let INK-DIM = rgb("#5b636d")
#let ORANGE-D = rgb("#b85f12")   // orange readable on paper

#let URL = "github.com/aborruso/llm-openrouter-decisions"

// — one call = one card, 4:5, full-bleed —
#let slide(light: false, url: true, body) = page(fill: if light { PAPER } else { BG }, {
  let dim = if light { INK-DIM } else { MUTED }
  set text(fill: if light { INK } else { FG })
  place(left + top, rect(width: 0.16in, height: 100%, fill: ORANGE))
  place(top + right, dx: -0.6in, dy: 0.55in, context text(
    font: MONO, size: 10pt, fill: dim,
    [#counter(page).display() / #counter(page).final().first()],
  ))
  if url { place(bottom + left, dx: 0.85in, dy: -0.5in, text(font: MONO, size: 10pt, fill: dim, URL)) }
  block(
    width: 100%, height: 100%,
    // without the URL, the body can use the space it would take
    inset: (left: 0.85in, right: 0.6in, top: 0.55in, bottom: if url { 0.95in } else { 0.55in }),
    body,
  )
})

#let kicker(body, color: ORANGE) = text(
  font: MONO, size: 11pt, weight: "bold", tracking: 2pt, fill: color, upper(body),
)

#let headline(body) = block(text(size: 34pt, weight: "bold", body))

// — big terminal for 4:5 cards —
#let term(body) = block(
  fill: PANEL, stroke: 0.6pt + BORDER, radius: 6pt,
  inset: (x: 16pt, y: 14pt), width: 100%,
)[
  #set text(font: MONO, size: 12.5pt, fill: FG)
  #set par(leading: 0.6em)
  #set smartquote(enabled: false)
  #body
]

#let prompt = text(fill: MUTED)[\$ ]
