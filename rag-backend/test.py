# pyrefly: ignore [missing-import]
from markitdown import MarkItDown

md = MarkItDown()

result = md.convert("trigno 11th.pdf")

markdown_text = result.text_content
with open("outputFile.md", "w", encoding="utf-8") as f:
    f.write(markdown_text)
