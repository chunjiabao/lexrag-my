## 3 Sept 2026

### Environment
- Project root: `C:\Users\chunj\Documents\lexrag-my`
- Python venv: `lexrag-my/venv` (activate with `.\venv\Scripts\Activate`)
- PyMuPDF installed inside venv (v1.28.2)

### A1 — Environment Setup: Done
- venv, .gitignore, requirements set up

### A2 — Statutory Downloading and Versioning: Done
- Scope expanded from 2 Acts to 5 Acts
- Source: lom.agc.gov.my
- PDFs stored in: `lexrag-my/Acts/`
- Files:
  - Act599_ConsumerProtectionAct1999.pdf
  - Act265_EmploymentAct1955.pdf
  - Act212_HirePurchaseAct1967.pdf
  - Act514_OccupationalSafetyHealthAct1994.pdf
  - Act709_PersonalDataProtectionAct2010.pdf
- MD5 checksums recorded (see checksum table — not yet saved to a file, only in chat history)

### A3 — PDF Text Extraction: Done
- Script: `lexrag-my/scripts/extract_text.py` (uses PyMuPDF)
- Output: `lexrag-my/extracted_text/` (one .txt per Act)
- Spot-checked Act514 — section numbering (incl. 7A/7B/7C) and structure extracted cleanly
- NOT yet spot-checked: other 4 Acts, especially Schedules/tables (highest risk per R1)

### Next step
- A4 — Section-level chunking (not started)

---

## 3 Sept 2026 (continued)

### A3 — Revised: raw extraction was too messy, moved to per-Act cleaning

**Problem found:** initial extraction (via `extract_text.py`) still contained page numbers, repeating headers ("Employment" / "Laws of Malaysia" / "Act 265"), footer print stamps (`WJW23/0686 Act 265.indd N`, date/time), plus Table of Contents and "List of Amendments" back matter — all noise that would pollute A4 chunking.

**Approach decided:** clean each Act individually with its own script, since header/footer format, footer stamp, and front/back matter boundaries differ per Act (different typesetting software: this one was Adobe InDesign, Act514 was Word).

**Method used:** page-cropping (not regex-stripping). Measured exact y-coordinates of header/footer text via PyMuPDF word positions, then set each page's cropbox to exclude those bands *before* text extraction — physically removes header/footer rather than pattern-matching after the fact. More reliable than regex since it can't miss a wording variant.

**Act 265 — Employment Act 1955: Cleaned ✅**
- Script: `lexrag-my/scripts/clean_act265.py`
- Content range: pages 11–110 (Section 1 → end of Second Schedule)
  - Excluded: pages 1–10 (cover + Table of Contents)
  - Excluded: pages 111–121 (List of Amendments / List of Sections Amended — historical reference, not needed for RAG)
- Crop margins: top=87pt, bottom=736pt (page height 750.7pt) — specific to this Act's layout
- Output: `lexrag-my/extracted_text/Act265_EmploymentAct1955_clean.txt` (164,381 characters)
- Verified: no footer stamp, no header text, confirmed clean on page 40 (the page originally flagged as still messy)

**Decision needed for A4:** how to handle `(Deleted by Act A1651)` / `(Omitted)` markers and `*NOTE—...` footnotes — these are legitimate legal content (not extraction noise), so decide whether to keep as placeholder chunks (preserves section numbering/structure) or skip during chunking.

**Not yet done:** same crop-cleaning process for the other 4 Acts (Act212, Act514, Act599, Act709) — each needs its own page-range and margin measurement, since formatting varies by Act.

### Next step
- Repeat crop-cleaning process for remaining 4 Acts (Act212, Act514, Act599, Act709)
- Then proceed to A4 — Section-level chunking