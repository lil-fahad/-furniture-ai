"""Bounded, isolated PDF rasterization. No file paths or URLs are accepted."""

import io
import sys


def main():
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    import pypdfium2 as pdfium

    raw = sys.stdin.buffer.read(26 * 1024 * 1024)
    page_number = int(sys.argv[1])
    with pdfium.PdfDocument(raw) as doc:
        if not 1 <= len(doc) <= 20 or not 0 <= page_number < len(doc):
            raise ValueError("PDF page limit")
        page = doc[page_number]
        width, height = page.get_size()
        if min(width, height) <= 0:
            raise ValueError("Invalid page size")
        bitmap = page.render(scale=min(2.0, 1536 / max(width, height)))
        image = bitmap.to_pil().convert("RGB")
        buf = io.BytesIO()
        image.save(buf, "PNG")
        sys.stdout.buffer.write(buf.getvalue())
        bitmap.close()
        page.close()


if __name__ == "__main__":
    main()
