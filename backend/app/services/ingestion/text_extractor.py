"""
Text Extraction Service for OVA Ingestion Pipeline.
Provides a modular TextExtractor interface with concrete extractors:
- TxtExtractor (.txt)
- JsonExtractor (.json with flattened key-value representation for stable offsets)
- PdfTextExtractor (.pdf via pypdf with scanned / needs_ocr detection)
- MockTextExtractor (testing / mocks)
Config-driven selection allows future OCR / Document AI extractors to drop in seamlessly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import io
import json
import os
import re
from typing import List, Dict, Any, Optional, Union

from app.core.config import settings


@dataclass
class ExtractedText:
    text: str
    pages: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    needs_ocr: bool = False


class TextExtractor(ABC):
    """Abstract base class for document text extractors."""

    @abstractmethod
    def extract(self, file_content: Union[str, bytes], filename: str = "") -> ExtractedText:
        """Extract text from file bytes or string content."""
        pass


class TxtExtractor(TextExtractor):
    """Extracts raw text from plain text files."""

    def extract(self, file_content: Union[str, bytes], filename: str = "") -> ExtractedText:
        warnings: List[str] = []
        if isinstance(file_content, bytes):
            try:
                text = file_content.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    text = file_content.decode("latin-1")
                    warnings.append("Decoded using latin-1 encoding fallback.")
                except Exception as exc:
                    warnings.append(f"Failed to decode text: {exc}")
                    text = file_content.decode("utf-8", errors="replace")
        else:
            text = str(file_content)

        # Normalize newlines
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not text.strip():
            warnings.append("Document text is empty.")

        pages = [{"page_number": 1, "text": text}]
        return ExtractedText(text=text, pages=pages, warnings=warnings, needs_ocr=False)


class JsonExtractor(TextExtractor):
    """
    Parses JSON clinical payloads and flattens them into structured, readable text
    with stable line and key-value offsets.
    """

    def extract(self, file_content: Union[str, bytes], filename: str = "") -> ExtractedText:
        warnings: List[str] = []
        if isinstance(file_content, bytes):
            raw_str = file_content.decode("utf-8", errors="replace")
        else:
            raw_str = str(file_content)

        try:
            data = json.loads(raw_str)
        except Exception as exc:
            warnings.append(f"Invalid JSON document: {exc}")
            return ExtractedText(text=raw_str, pages=[{"page_number": 1, "text": raw_str}], warnings=warnings)

        # Flatten into stable, readable lines
        lines: List[str] = []

        def _flatten(obj: Any, prefix: str = ""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    key_path = f"{prefix}.{k}" if prefix else str(k)
                    if isinstance(v, (dict, list)):
                        _flatten(v, key_path)
                    else:
                        lines.append(f"{key_path}: {v}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    idx_path = f"{prefix}[{i}]"
                    if isinstance(item, (dict, list)):
                        _flatten(item, idx_path)
                    else:
                        lines.append(f"{idx_path}: {item}")
            else:
                lines.append(f"{prefix}: {obj}" if prefix else str(obj))

        _flatten(data)
        flattened_text = "\n".join(lines)
        pages = [{"page_number": 1, "text": flattened_text}]
        return ExtractedText(text=flattened_text, pages=pages, warnings=warnings, needs_ocr=False)


class PdfTextExtractor(TextExtractor):
    """
    Extracts text from PDF documents using pypdf.
    If fewer than 20 alphanumeric characters are detected across all pages,
    flags the document as scanned / image-only (needs_ocr=True).
    """

    def extract(self, file_content: Union[str, bytes], filename: str = "") -> ExtractedText:
        warnings: List[str] = []
        pages: List[Dict[str, Any]] = []

        if isinstance(file_content, str):
            if os.path.exists(file_content):
                with open(file_content, "rb") as f:
                    content_bytes = f.read()
            else:
                content_bytes = file_content.encode("utf-8")
        else:
            content_bytes = file_content

        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content_bytes))
            full_text_blocks: List[str] = []
            total_alphanumeric = 0

            for idx, page in enumerate(reader.pages):
                try:
                    p_text = page.extract_text() or ""
                except Exception as p_exc:
                    warnings.append(f"Page {idx + 1} extraction warning: {p_exc}")
                    p_text = ""

                pages.append({"page_number": idx + 1, "text": p_text})
                full_text_blocks.append(f"--- Page {idx + 1} ---\n{p_text}")
                total_alphanumeric += len(re.findall(r"[a-zA-Z0-9]", p_text))

            combined_text = "\n\n".join(full_text_blocks)

            # Detect scanned image PDF without embedded text layer
            if total_alphanumeric < 20:
                warnings.append("Scanned or image-only PDF detected; text layer missing. OCR required.")
                return ExtractedText(
                    text="[NEEDS OCR: Scanned document requires OCR processing. No embedded text found.]",
                    pages=pages,
                    warnings=warnings,
                    needs_ocr=True,
                )

            return ExtractedText(
                text=combined_text,
                pages=pages,
                warnings=warnings,
                needs_ocr=False,
            )

        except Exception as exc:
            warnings.append(f"Failed to parse PDF document: {exc}")
            return ExtractedText(
                text="[NEEDS OCR: Scanned or unreadable PDF document. OCR processing required.]",
                pages=[],
                warnings=warnings,
                needs_ocr=True,
            )


class MockTextExtractor(TextExtractor):
    """Mock extractor returning predictable text for testing."""

    def __init__(self, override_text: Optional[str] = None, force_ocr: bool = False):
        self.override_text = override_text
        self.force_ocr = force_ocr

    def extract(self, file_content: Union[str, bytes], filename: str = "") -> ExtractedText:
        if self.force_ocr:
            return ExtractedText(
                text="[NEEDS OCR: Mock scanned document]",
                pages=[],
                warnings=["Mock OCR required flag"],
                needs_ocr=True,
            )
        text = self.override_text or "MOCK CLINICAL RECORD: AMH: 2.1 ng/mL, Oocytes retrieved: 8."
        return ExtractedText(
            text=text,
            pages=[{"page_number": 1, "text": text}],
            warnings=[],
            needs_ocr=False,
        )


def get_text_extractor(filename: str = "", mime_type: Optional[str] = None) -> TextExtractor:
    """Factory selecting the appropriate extractor based on settings and file type."""
    if settings.TEXT_EXTRACTOR.lower() == "mock":
        return MockTextExtractor()

    lower_fn = filename.lower()
    if lower_fn.endswith(".pdf") or mime_type == "application/pdf":
        return PdfTextExtractor()
    elif lower_fn.endswith(".json") or mime_type == "application/json":
        return JsonExtractor()
    elif lower_fn.endswith(".txt") or mime_type == "text/plain":
        return TxtExtractor()

    # Default fallback
    return TxtExtractor()
