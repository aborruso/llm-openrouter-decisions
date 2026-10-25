#import "theme.typ": *

// 1280x640 at 144 ppi
#let W = 1280in / 144
#let H = 640in / 144

#let title = [
  #text(font: MONO, size: 10pt, weight: "bold", tracking: 2pt, fill: ORANGE)[LLM PLUGIN]
  #v(0.06in)
  #box(text(font: MONO, size: 30pt, weight: "bold", fill: FG)[llm-openrouter-decisions])
]

#let header = [
  #text(size: 15pt, fill: FG)[Decision models in your terminal.]
  #v(0.04in)
  #text(size: 12pt, fill: MUTED)[Typed answers from 30 models, \ one OpenRouter key.]
  #v(0.2in)
  #chip("yes/no", TEAL) #h(4pt) #chip("choice", TEAL) #h(4pt) #chip("score", TEAL) #h(4pt) #chip("box", ORANGE)
]

#let command = terminal[
  #text(fill: MUTED)[\$] llm -m jev14 \
  #h(1.2em)'Please refund my last payment.' \
  #h(1.2em)-s 'Does it ask for a refund?' \
  #v(0.04in)
  #text(fill: TEAL)[{"type": "noul", "noul": 0.99}]
]

#let footer = text(font: MONO, size: 9pt, fill: MUTED)[github.com/aborruso/llm-openrouter-decisions]

#let rail = place(left + top, rect(width: 0.12in, height: 100%, fill: ORANGE))
