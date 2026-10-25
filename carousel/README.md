# LinkedIn carousel

Source of the LinkedIn carousel that announces the plugin: 8 cards, 4:5 (1080x1350), built with [Typst](https://typst.app/). It reuses the palette of `../social-preview/theme.typ` and the chart in `../examples/chart-box.png`, so it compiles with the repository as root:

```bash
cd carousel
typst compile --root .. slides.typ "output/slide-{p}.png" --ppi 144
typst compile --root .. slides.typ output/deck.pdf
```

`output/deck.pdf` is the file to upload as a LinkedIn document post. `linkedin-post.txt` is the text of the post: CRLF line endings, and the empty lines hold a U+2800 character, because LinkedIn drops truly empty lines on paste. Copy it to the clipboard from the file, not from a terminal.
