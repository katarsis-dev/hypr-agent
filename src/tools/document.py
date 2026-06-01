"""Document converter tool — convert between PDF, DOCX, Markdown, TXT, HTML."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any


SUPPORTED_FORMATS = {"pdf", "docx", "md", "txt", "html", "odt", "rst"}


class DocumentConverterTool:
    name = "document_convert"
    description = "Convert documents between formats: PDF, DOCX, Markdown, TXT, HTML, ODT. Uses pandoc or libreoffice as backends."
    input_schema = '{"input_path": "/path/to/file.md", "output_format": "pdf|docx|html|txt|md|odt", "output_path": "optional output path"}'

    async def execute(self, **kwargs: Any) -> str:
        input_path = kwargs.get("input_path") or kwargs.get("path", "")
        output_format = kwargs.get("output_format") or kwargs.get("format", "")
        output_path = kwargs.get("output_path", "")

        if not input_path:
            return "Error: No input_path provided."
        if not output_format:
            return f"Error: No output_format specified. Supported: {', '.join(SUPPORTED_FORMATS)}"

        output_format = output_format.lower().lstrip(".")
        if output_format not in SUPPORTED_FORMATS:
            return f"Error: Unsupported format '{output_format}'. Supported: {', '.join(SUPPORTED_FORMATS)}"

        filepath = Path(input_path).expanduser()
        if not filepath.exists():
            return f"Error: File not found: {input_path}"

        # Determine output path
        if not output_path:
            output_path = str(filepath.with_suffix(f".{output_format}"))

        # Try pandoc first (best for md/html/docx/pdf/rst)
        result = await self._try_pandoc(filepath, output_path, output_format)
        if result is not None:
            return result

        # Fallback: libreoffice (good for docx/odt/pdf)
        result = await self._try_libreoffice(filepath, output_path, output_format)
        if result is not None:
            return result

        return (
            "Error: No converter available.\n"
            "Install one of:\n"
            "  pacman -S pandoc          (best for md/html/docx/pdf)\n"
            "  pacman -S libreoffice-fresh (for docx/odt/pdf)"
        )

    async def _try_pandoc(self, input_path: Path, output_path: str, fmt: str) -> str | None:
        """Try converting with pandoc."""
        cmd = f"pandoc '{input_path}' -o '{output_path}'"
        if fmt == "pdf":
            # pandoc needs a PDF engine
            cmd += " --pdf-engine=xelatex 2>/dev/null || pandoc '{}' -o '{}' --pdf-engine=wkhtmltopdf 2>/dev/null || pandoc '{}' -o '{}'".format(
                input_path, output_path, input_path, output_path
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)

            if proc.returncode == 0:
                size = Path(output_path).stat().st_size
                return f"Converted successfully!\nOutput: {output_path} ({size} bytes)"
            return None
        except (asyncio.TimeoutError, FileNotFoundError):
            return None

    async def _try_libreoffice(self, input_path: Path, output_path: str, fmt: str) -> str | None:
        """Try converting with LibreOffice."""
        lo_format = {
            "pdf": "pdf",
            "docx": "docx",
            "odt": "odt",
            "html": "html",
            "txt": "txt",
        }.get(fmt)

        if not lo_format:
            return None

        output_dir = str(Path(output_path).parent)
        cmd = f"libreoffice --headless --convert-to {lo_format} --outdir '{output_dir}' '{input_path}'"

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)

            if proc.returncode == 0:
                # LibreOffice outputs to the same name with new extension
                expected = Path(output_dir) / f"{input_path.stem}.{lo_format}"
                if expected.exists():
                    size = expected.stat().st_size
                    return f"Converted successfully!\nOutput: {expected} ({size} bytes)"
                return f"Conversion may have succeeded. Check {output_dir} for output."
            return None
        except (asyncio.TimeoutError, FileNotFoundError):
            return None
