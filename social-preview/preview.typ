#import "common.typ": *
#set document(title: "llm-openrouter-decisions", author: "Andrea Borruso")
#set text(lang: "en", font: SANS)
#set page(width: W, height: H, margin: 0in, fill: BG)

#rail
#block(width: 100%, height: 100%, inset: (left: 0.6in, right: 0.5in, top: 0.42in, bottom: 0.38in))[
  #title
  #v(0.3in)
  #grid(columns: (1fr, 1.15fr), column-gutter: 0.35in,
    header,
    command,
  )
  #v(1fr)
  #footer
]
