"""
PDF text extraction — pulls raw text from uploaded resume PDFs.
Gemini then structures the extracted text into clean resume content.
"""
import logging
import os

logger = logging.getLogger(__name__)


def _fix_char_spacing(text: str) -> str:
    """Fix PDFs where every character has a space between them (char-level glyph storage)."""
    import re
    lines = text.split('\n')
    fixed = []
    for line in lines:
        words = line.split(' ')
        if not words:
            fixed.append(line)
            continue
        single_char_ratio = sum(1 for w in words if len(w) <= 1) / max(len(words), 1)
        if single_char_ratio > 0.55:
            # Split on double spaces (word boundaries), collapse single spaces (char spaces)
            segments = line.split('  ')
            collapsed = ' '.join(''.join(s.split(' ')) for s in segments)
            fixed.append(collapsed)
        else:
            fixed.append(line)
    return '\n'.join(fixed)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract plain text from a PDF file. Returns empty string on failure."""
    if not os.path.exists(pdf_path):
        logger.error(f"PDF not found: {pdf_path}")
        return ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
        raw = "\n\n".join(pages)
        return _fix_char_spacing(raw)
    except Exception as e:
        logger.error(f"PDF extraction failed for {pdf_path}: {e}")
        return ""


def extract_and_structure(pdf_path: str) -> str:
    """
    Extract text from PDF, then ask Gemini to clean and structure it.
    Returns structured plain-text resume ready to store in DB.
    """
    raw = extract_text_from_pdf(pdf_path)
    if not raw:
        return ""
    if len(raw) < 50:
        logger.warning(f"PDF extracted very little text ({len(raw)} chars) — may be image-based")
        return raw

    from gemini import _run
    prompt = f"""Clean and structure this raw PDF-extracted resume text.
Fix any OCR/extraction artifacts, normalize formatting, keep ALL information.
Output in clear sections: Contact, Summary, Skills, Experience, Education, Projects.
Keep it as plain text (no markdown syntax).

RAW EXTRACTED TEXT:
{raw[:4000]}

Return ONLY the cleaned, structured resume text. No commentary."""
    structured = _run(prompt, timeout=60)
    return structured if structured and len(structured) > 100 else raw
