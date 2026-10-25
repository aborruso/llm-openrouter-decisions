#import "theme.typ": *

#set document(title: "llm-openrouter-decisions", author: "Andrea Borruso")
#set text(lang: "en", font: SANS, size: 16pt)
#set par(leading: 0.65em)
// 4:5 → 1080×1350 at 144 ppi
#set page(width: 7.5in, height: 9.375in, margin: 0in)

#let sh(body) = term(raw(block: true, body))
#let out(body) = text(fill: TEAL, raw(block: true, body))

// — 1 · cover —
#slide({
  v(1fr)
  kicker[LLM plugin · first alpha]
  v(0.15in)
  text(font: MONO, size: 25pt, weight: "bold")[llm-openrouter-\ decisions]
  v(0.45in)
  text(size: 40pt, weight: "bold")[Ask a closed question.\ Get a #text(fill: ORANGE)[number] back.]
  v(0.35in)
  text(size: 17pt, fill: MUTED)[30 decision models from OpenRouter, in your terminal, through Simon Willison's LLM.]
  v(0.4in)
  chip("yes/no", TEAL); h(6pt); chip("choice", TEAL); h(6pt); chip("score", TEAL); h(6pt); chip("box", ORANGE)
  v(1fr)
})

// — 2 · thanks (the one light card) —
#slide(light: true, {
  v(1fr)
  kicker(color: ORANGE-D)[First, a thank you]
  v(0.2in)
  text(size: 40pt, weight: "bold")[Thank you,\ Simon Willison.]
  v(0.35in)
  text(size: 18pt)[For the work he has been doing for years to explain AI to everyone, in the open, and for LLM, a tool that lets anyone use AI models in a smart, convenient and elegant way.]
  v(0.3in)
  text(size: 18pt, weight: "bold", fill: ORANGE-D)[This plugin only exists because LLM does.]
  v(0.4in)
  text(size: 13pt, fill: INK-DIM)[Request validation, response handling and tests derived from #box[llm-typesafe] by Simon Willison (Apache-2.0). Skeleton from his #box[llm-plugin] cookiecutter template.]
  v(1fr)
})

// — 3 · what decision models are —
#let kind(name, color, what, json) = grid(
  columns: (1.15in, 1fr), column-gutter: 0.2in,
  text(font: MONO, size: 15pt, weight: "bold", fill: color, name),
  [
    #text(size: 15pt, what)
    #v(-0.08in)
    #text(font: MONO, size: 11pt, fill: MUTED, json)
  ],
)

#slide({
  kicker[What they are]
  v(0.2in)
  headline[They don't write text.\ They answer with numbers.]
  v(0.12in)
  text(size: 15pt, fill: MUTED)[You send some content, the _state_, plus a closed question.]
  v(0.35in)
  kind("noul", TEAL, [Probability that a statement is true], "{\"noul\": 0.99}")
  v(0.16in)
  kind("choice", TEAL, [A category, with a probability for each option], "{\"choice\": \"billing\", ...}")
  v(0.16in)
  kind("score", TEAL, [A position on an ordered scale], "{\"score\": 0.94, \"legend\": ...}")
  v(0.16in)
  kind("box", ORANGE, [Where something is in an image], "{\"box\": {\"top\": 0.06, ...}}")
  v(1fr)
  text(size: 17pt)[Fast and very cheap: made for classifying, filtering and triaging #text(fill: ORANGE, weight: "bold")[many items] from the command line.]
})

// — 4 · the catalog —
#slide({
  kicker[Not just one model]
  v(0.2in)
  headline[30 models.\ 13 makers.\ One key.]
  v(0.35in)
  set text(size: 15pt)
  grid(columns: (1fr, 1fr), row-gutter: 0.16in, column-gutter: 0.2in,
    [TypeSafe Jev], [OpenAI GPT-6 Luna Decisions],
    [Perplexity Decider], [Cloudflare Clef],
    [Liquid d1], [Inception Mercury Decide],
    [Upstage Solar Decide], [Microsoft Decision-1],
    [Kev (open weight)], text(fill: MUTED)[and more],
  )
  v(0.4in)
  sh("llm models | grep openrouter-decisions")
  v(1fr)
  text(size: 17pt)[Compare them on your own data changing nothing but #text(font: MONO, fill: ORANGE)[-m]. Accuracy, speed, price and probabilities differ: test more than one before picking.]
})

// — 5 · how it works —
#slide({
  kicker[How it works]
  v(0.2in)
  headline[Content in.\ Question with -s.]
  v(0.3in)
  sh("llm install llm-openrouter-decisions\nllm keys set openrouter\nllm aliases set jev14 \\\n  openrouter-decisions/typesafe/jev-1.14")
  v(0.3in)
  term[
    #raw(block: true, "llm -m jev14 'Please refund my last payment.' \\\n  -s 'Does this message ask for a refund?'")
    #v(0.06in)
    #out("{\"type\": \"noul\", \"noul\": 0.99}")
  ]
  v(0.3in)
  text(size: 15pt, fill: MUTED)[Categories with #text(font: MONO, fill: FG)[-o answer_type choice], several named questions in one request with #text(font: MONO, fill: FG)[-o questions], JSON input, images with #text(font: MONO, fill: FG)[-a].]
  v(1fr)
})

// — 6 · a CSV file —
#let row(t, d, c, u, hl: false) = (
  text(size: 12.5pt, fill: if hl { ORANGE } else { FG }, t),
  text(font: MONO, size: 11.5pt, d),
  align(right, text(font: MONO, size: 11.5pt, fill: if hl { ORANGE } else { FG }, c)),
  align(right, text(font: MONO, size: 11.5pt, u)),
)

#slide({
  kicker[A real batch]
  v(0.2in)
  headline[48 decisions,\ #text(fill: ORANGE)[\$0.00033.]]
  v(0.25in)
  text(size: 15pt, fill: MUTED)[16 residents' reports to a city, 3 questions each, one CSV row at a time: which department, is it urgent, does it hold personal data.]
  v(0.3in)
  grid(columns: (1fr, auto, auto, auto), column-gutter: 0.18in, row-gutter: 0.14in,
    ..(text(size: 10pt, fill: MUTED)[REPORT], text(size: 10pt, fill: MUTED)[DEPT],
       align(right, text(size: 10pt, fill: MUTED)[CONF]), align(right, text(size: 10pt, fill: MUTED)[URGENT])),
    ..row[Huge pothole outside number 12][public works][1.00][0.95],
    ..row[A tree is about to fall][public works][1.00][0.94],
    ..row[Traffic light outside the hospital][public works][1.00][0.89],
    ..row(hl: true)[Strong smell of gas in the street][public works][0.47][0.88],
    ..row[Recycling bins full for days][environment][0.99][0.56],
  )
  v(0.3in)
  text(size: 15pt)[The report with a social security number: personal data #text(font: MONO, fill: TEAL)[0.99], every other row 0.04 or less.]
  v(1fr)
  text(size: 17pt)[The gas leak is urgent, but no category fits a utility: confidence #text(fill: ORANGE, weight: "bold")[0.47]. Sorting by confidence finds the rows a person should look at.]
})

// — 7 · images —
#slide({
  kicker[Images too]
  v(0.2in)
  headline[Where is the legend?]
  v(0.25in)
  box(clip: true, radius: 6pt, image("../examples/chart-box.png", width: 80%))
  v(0.25in)
  term[
    #raw(block: true, "llm -m jev14 -a chart.png \\\n  -s 'the legend of the chart' \\\n  -o answer_type box ''")
    #v(0.06in)
    #out("{\"box\": {\"top\": 0.06, \"bottom\": 0.15,\n  \"left\": 0.86, \"right\": 0.93}, \"confidence\": 0.69}")
  ]
  v(1fr)
  text(size: 15pt)[The box finds the legend but covers only its left half. Boxes are approximate: pair them with a yes/no question.]
})

// — 8 · read more, get it —
#let reading(title, who, what) = block[
  #text(size: 15pt, weight: "bold", title) #text(size: 13pt, fill: MUTED)[· #who]\
  #text(size: 13.5pt, what)
]

#slide(url: false, {
  kicker[Read more]
  v(0.25in)
  reading[Jev introduces a new shape of LLM][Simon Willison][What decision models are, and why evals and bias checks matter even more than with chat models.]
  v(0.22in)
  reading[Can Jev Parse CSV?][Remy Wang][Repairing broken CSV files with one yes/no question per comma: 12,044 decisions for 8 cents.]
  v(0.22in)
  reading[Can You Trust Jev's Confidence?][Ryan Porter][Confidence ranks right and wrong answers well but overstates them by 7 to 15 points.]
  v(0.3in)
  v(1fr)
  line(length: 100%, stroke: 0.6pt + BORDER)
  v(0.3in)
  kicker[Try it]
  v(0.15in)
  headline[One install,\ one OpenRouter key.]
  v(0.25in)
  sh("llm install llm-openrouter-decisions")
  v(0.2in)
  text(font: MONO, size: 14pt, fill: TEAL)[#URL]
  v(0.05in)
  text(font: MONO, size: 14pt, fill: MUTED)[pypi.org/project/llm-openrouter-decisions]
  v(0.1in)
})
