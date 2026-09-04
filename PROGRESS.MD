## 3 Sept 2026

### Environment
- Project root: `C:\Users\chunj\Documents\lexrag-my`
- Python venv: `lexrag-my/venv` (activate with `.\venv\Scripts\Activate`)
- PyMuPDF installed inside venv (v1.28.2)

### A1 — Environment Setup: Done
- venv, .gitignore, requirements set up

### A2 — Statutory Downloading and Versioning: Done
- Initially downloaded 5 Acts to explore scope expansion (see scope decision below)
- Source: lom.agc.gov.my
- PDFs stored in: `lexrag-my/Acts/`
- MD5 checksums recorded for all 5 downloaded (see checksum table — not yet saved to a file, only in chat history)

### A3 — PDF Text Extraction (raw, pre-cleaning): Done
- Script: `lexrag-my/scripts/extract_text.py` (uses PyMuPDF)
- Output: `lexrag-my/extracted_text/` (one raw .txt per Act)
- Spot-checked Act514 — section numbering (incl. 7A/7B/7C) and structure extracted cleanly
- Result: raw extraction contained page numbers, repeating headers/footers, ToC, and back matter — needed further cleaning (see below)

### Next step
- A4 — Section-level chunking (not started)

---

## 3 Sept 2026 (continued)

### A3 — Revised: raw extraction too messy, moved to per-Act cleaning

**Problem found:** initial extraction still contained page numbers, repeating headers ("Employment" / "Laws of Malaysia" / "Act 265"), footer print stamps (`WJW23/0686 Act 265.indd N`, date/time), plus Table of Contents and "List of Amendments" back matter — all noise that would pollute A4 chunking.

**Approach decided:** clean each Act individually with its own config, since header/footer format, footer stamp, and front/back matter boundaries differ per Act (different typesetting software — e.g. Act265 was Adobe InDesign, Act514 was Word).

**Method used:** page-cropping (not regex-stripping). Measured exact y-coordinates of header/footer text via PyMuPDF word positions, then set each page's cropbox to exclude those bands *before* text extraction — physically removes header/footer rather than pattern-matching after the fact. More reliable than regex alone since it can't miss a wording variant.

**Act 265 — Employment Act 1955: Cleaned ✅**
- Script: `lexrag-my/scripts/clean_act265.py`
- Content range: pages 11–110 (Section 1 → end of Second Schedule)
  - Excluded: pages 1–10 (cover + Table of Contents)
  - Excluded: pages 111–121 (List of Amendments — historical reference, not needed for RAG)
- Crop margins: top=87pt, bottom=736pt (page height 750.7pt) — specific to this Act's layout
- Output: `lexrag-my/extracted_text/Act265_EmploymentAct1955_clean.txt` (164,381 characters)
- Verified: no footer stamp, no header text, confirmed clean on page 40

**Decision needed for A4:** how to handle `(Deleted by Act A1651)` / `(Omitted)` markers and `*NOTE—...` footnotes — these are legitimate legal content (not extraction noise), so decide whether to keep as placeholder chunks (preserves section numbering/structure) or skip during chunking.

### Next step
- Repeat crop-cleaning process for remaining Acts
- Then proceed to A4 — Section-level chunking

---

## 4 Sept 2026

### Scope decision: narrowed from 5 Acts down to 3

**Considered:** keeping all 5 downloaded Acts (Employment, Consumer Protection, Hire-Purchase, OSHA, PDPA) vs. narrowing to a smaller, more thematically coherent set.

**Decided:** final scope is **3 Acts** — Employment Act 1955 (Act 265), Consumer Protection Act 1999 (Act 599), Personal Data Protection Act 2010 (Act 709).

**Why:**
- Thematic coherence — all 3 are "individual rights against an entity" (workplace rights, consumer rights, data rights), giving the project a clear framing rather than 5 loosely related Acts.
- PDPA 2010 chosen over Hire-Purchase Act 1967 and OSHA 1994 as the third Act — PDPA is current and highly relevant (2024 amendments, active enforcement), while Hire-Purchase is older and more procedurally dense with heavier amendment history, and OSHA would have made the set workplace-heavy (2 of 3 Acts) rather than balanced across domains.
- Keeps A4/A5 (chunking/validation) workload manageable given the 13-week timeline, while still going beyond the original proposal's 2-Act scope.

**Impact:** Act212 (Hire-Purchase) and Act514 (OSHA) — already downloaded and checksum-recorded — are set aside, not part of final dataset. Raw extraction (`extract_text.py`) had already run on all 5; only Act265, Act599, and Act709 proceed to crop-cleaning and beyond.

### A3 — Crop-cleaning: Consumer Protection Act 1999 and PDPA 2010 — Done ✅

Repeated the same page-cropping approach for the remaining 2 Acts in final scope.

**Script:** `lexrag-my/scripts/clean_all_acts.py` — consolidated all 3 Acts into one script (list of per-Act configs + shared `clean_pdf()` function) rather than separate scripts per Act, since the extraction logic is identical and only the parameters (page range, crop margins, footer pattern) differ.

**Per-Act config used:**

| Act | Content pages | Top margin | Bottom margin | Footer stamp |
|---|---|---|---|---|
| 265 – Employment Act 1955 | 11–108 | 87 | 736 | `WJW23` — stripped via regex |
| 599 – Consumer Protection Act 1999 | 13–134 | 127 | 775 | `WJW.../.indd` + timestamp on every page — stripped via regex |
| 709 – Personal Data Protection Act 2010 | 11–98 | 67 | 695 | none found in extracted range |

**Note on Act599:** printer stamp appears on every page (unlike Act265's isolated case), so crop alone wasn't enough — footer regex added per-config to strip any matching line before saving. Confirms the decision to keep per-Act config flexible rather than hardcoding one cleaning method.

**Output:** all 3 `_clean.txt` files in `lexrag-my/extracted_text/`.

**Status:** Act212 and Act514 configs removed from script entirely (out of scope per decision above) — script now only processes the final 3 Acts.

### Environment note
- Hit a path bug when moving scripts from Claude's sandbox to local: hardcoded sandbox paths (`/mnt/user-data/uploads`, `/mnt/user-data/outputs`) don't exist on Windows. Fixed by switching to relative paths (`INPUT_DIR = "Acts"`, `OUTPUT_DIR = "extracted_text"`), run from project root. Lesson: keep scripts environment-agnostic from the start.

### Not yet done
- Full spot-check of Act599 and Act709 internal pages (Schedules/tables especially) — only start/end boundaries and footer-stamp checks confirmed so far, per script's automated sanity check output. Mid-document manual spot-check still outstanding.
- MD5 checksum table not yet saved to a file (still only in chat history) — worth saving as `data_provenance.md` before final scope is locked in.

### A3 — Status: Done ✅ (for final 3-Act scope)

### Next step
- Full spot-check of Act599 / Act709 internal pages (Schedules/tables) before proceeding
- A4 — Section-level chunking (not started)
  - Still need the earlier decision on `(Deleted by Act A1651)` / `(Omitted)` markers and `*NOTE—...` footnotes: placeholder chunks vs. skip