"""PDF reader tool — extract text from PDF files."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any


class PdfReaderTool:
    name = "pdf_reader"
    description = "Extract text from a PDF file. Optionally specify page range. Requires pdftotext (poppler-utils) or pymupdf."
    input_schema = '{"path": "/path/to/file.pdf", "pages": "1-5 or all"}'

    async def execute(self, **kwargs: Any) -> str:
        path = kwargs.get("path") or kwargs.get("input", "")
        pages = kwargs.get("pages", "all")

        if not path:
            return "Error: No PDF path provided."

        filepath = Path(path).expanduser()
        if not filepath.exists():
            return f"Error: File not found: {path}"
        if not filepath.suffix.lower() == ".pdf":
            return f"Error: Not a PDF file: {path}"

        # Try pdftotext first (poppler-utils, lighter)
        result = await self._try_pdftotext(filepath, pages)
        if result is not None:
            return result

        # Fallback: try pymupdf
        result = self._try_pymupdf(filepath, pages)
        if result is not None:
            return result

        return (
            "Error: No PDF reader available.\n"
            "Install one of:\n"
            "  pacman -S poppler  (provides pdftotext)\n"
            "  pip install pymupdf"
        )

    async def _try_pdftotext(self, filepath: Path, pages: str) -> str | None:
        """Try using pdftotext from poppler-utils."""
        page_args = ""
        if pages != "all":
            parts = pages.split("-")
            if len(parts) == 2:
                page_args = f"-f {parts[0]} -l {parts[1]}"
            elif len(parts) == 1:
                page_args = f"-f {parts[0]} -l {parts[0]}"

        cmd = f"pdftotext {page_args} '{filepath}' -"

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

            if proc.returncode == 0:
                text = stdout.decode(errors="replace")
                if len(text) > 10000:
                    text = text[:10000] + "\n...[truncated at 10000 chars]"
                return text or "(no text extracted — PDF may be image-based)"
            return None
        except (asyncio.TimeoutError, FileNotFoundError):
            return None

    def _try_pymupdf(self, filepath: Path, pages: str) -> str | None:
        """Try using pymupdf (fitz)."""
        try:
            import fitz  # pymupdf
        except ImportError:
            return None

        try:
            doc = fitz.open(str(filepath))
            text_parts: list[str] = []

            if pages == "all":
                page_range = range(len(doc))
            else:
                parts = pages.split("-")
                if len(parts) == 2:
                    start = max(0, int(parts[0]) - 1)
                    end = min(len(doc), int(parts[1]))
                    page_range = range(start, end)
                else:
                    pg = max(0, int(parts[0]) - 1)
                    page_range = range(pg, pg + 1)

            for i in page_range:
                page = doc[i]
                text_parts.append(f"--- Page {i + 1} ---\n{page.get_text()}")

            doc.close()
            result = "\n".join(text_parts)
            if len(result) > 10000:
                result = result[:10000] + "\n...[truncated at 10000 chars]"
            return result or "(no text extracted)"
        except Exception as e:
            return f"Error reading PDF with pymupdf: {e}"
