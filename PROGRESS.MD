## 3 Sept 2026

### Environment
- Project root: `C:\Users\chunj\Documents\lexrag-my`
- Python venv: `lexrag-my/venv` (activate with `.\venv\Scripts\Activate`)
- PyMuPDF installed inside venv (v1.28.2)

### A1 — Environment Setup: Done
- venv, .gitignore, requirements set up

### A2 — Statutory Downloading and Versioning: Done
- Source: lom.agc.gov.my
- PDFs stored in: `lexrag-my/Acts/`
- MD5 checksums recorded (see checksum table — not yet saved to a file, only in chat history)

### A3 — PDF Text Extraction (raw, pre-cleaning): Done
- Script: `lexrag-my/scripts/extract_text.py` (uses PyMuPDF)
- Output: `lexrag-my/extracted_text/` (one raw .txt per Act)
- Result: raw extraction contained page numbers, repeating headers/footers, ToC, and back matter — needed further cleaning (see below)

### Next step
- A4 — Section-level chunking (not started)

---

## 3 Sept 2026 (continued)

### A3 — Revised: raw extraction too messy, moved to per-Act cleaning

**Problem found:** initial extraction still contained page numbers, repeating headers ("Employment" / "Laws of Malaysia" / "Act 265"), footer print stamps (`WJW23/0686 Act 265.indd N`, date/time), plus Table of Contents and "List of Amendments" back matter — all noise that would pollute A4 chunking.

**Approach decided:** clean each Act individually with its own config, since header/footer format, footer stamp, and front/back matter boundaries differ per Act.

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

### Scope: 3 Acts

**Final scope:** Employment Act 1955 (Act 265), Consumer Protection Act 1999 (Act 599), Personal Data Protection Act 2010 (Act 709).

**Why:**
- Thematic coherence — all 3 are "individual rights against an entity" (workplace rights, consumer rights, data rights), giving the project a clear framing.
- PDPA 2010 is current and highly relevant (2024 amendments, active enforcement).
- Keeps A4/A5 (chunking/validation) workload manageable given the 13-week timeline, while still going beyond the original proposal's 2-Act scope.

### A3 — Crop-cleaning: Consumer Protection Act 1999 and PDPA 2010 — Done ✅

Repeated the same page-cropping approach for the remaining 2 Acts in scope.

**Script:** `lexrag-my/scripts/clean_all_acts.py` — consolidated all 3 Acts into one script (list of per-Act configs + shared `clean_pdf()` function) rather than separate scripts per Act, since the extraction logic is identical and only the parameters (page range, crop margins, footer pattern) differ.

**Per-Act config used:**

| Act | Content pages | Top margin | Bottom margin | Footer stamp |
|---|---|---|---|---|
| 265 – Employment Act 1955 | 11–108 | 87 | 736 | `WJW23` — stripped via regex |
| 599 – Consumer Protection Act 1999 | 13–134 | 127 | 775 | `WJW.../.indd` + timestamp on every page — stripped via regex |
| 709 – Personal Data Protection Act 2010 | 11–98 | 67 | 695 | none found in extracted range |

**Note on Act599:** printer stamp appears on every page (unlike Act265's isolated case), so crop alone wasn't enough — footer regex added per-config to strip any matching line before saving. Confirms the decision to keep per-Act config flexible rather than hardcoding one cleaning method.

**Output:** all 3 `_clean.txt` files in `lexrag-my/extracted_text/`.

### Environment note
- Hit a path bug when moving scripts from Claude's sandbox to local: hardcoded sandbox paths (`/mnt/user-data/uploads`, `/mnt/user-data/outputs`) don't exist on Windows. Fixed by switching to relative paths (`INPUT_DIR = "Acts"`, `OUTPUT_DIR = "extracted_text"`), run from project root. Lesson: keep scripts environment-agnostic from the start.

### Not yet done
- Full spot-check of Act599 and Act709 internal pages (Schedules/tables especially) — only start/end boundaries and footer-stamp checks confirmed so far, per script's automated sanity check output. Mid-document manual spot-check still outstanding.
- MD5 checksum table not yet saved to a file (still only in chat history) — worth saving as `data_provenance.md`.

### A3 — Status: Done ✅

### Next step
- Full spot-check of Act599 / Act709 internal pages (Schedules/tables) before proceeding
- A4 — Section-level chunking (not started)
  - Still need the earlier decision on `(Deleted by Act A1651)` / `(Omitted)` markers and `*NOTE—...` footnotes: placeholder chunks vs. skip

---

## 4 Sept 2026 (continued)

### A4 — Section-level chunking: built, corrected, then rescoped to match proposal — Done ✅ (generation)

**Decision made:** repealed/omitted sections (`(Deleted by Act A1651)`, `(Omitted)`) kept as placeholder chunks rather than skipped, to preserve section numbering continuity. Added `is_deleted` boolean flag to each chunk to support this — a user querying a repealed section gets "this section was repealed," not silence or a gap in numbering.

**Script (v1):** `lexrag-my/scripts/chunk_acts.py` — rule-based parser detecting section boundaries via `N.\t` line pattern (handles sub-lettered sections like `7a`, `33a`) and Part headers via `Part I` pattern.

**Bugs found and fixed during testing on Act265:**
1. Section titles were bleeding into the *previous* section's body text (e.g. "Interpretation" appearing at the end of Section 1's text instead of as Section 2's title) — fixed by popping title-like lines off the previous section before flushing.
2. Multi-line titles (titles wrapping across 2 lines, e.g. "Contracts to be in writing and to include provision for / termination") only had their last line detected — fixed by walking backward through *all* consecutive title-looking lines, not just one.
3. Footnote text was initially misidentified as a section title (heuristic false-positive) — refined `looks_like_title()` to reject lines containing digits or ending in sentence punctuation.

**Scope correction — metadata schema:** built an "upgraded" version with additional extracted fields (`defined_terms`, `referenced_acts`, `referenced_sections`, `referenced_parts`, `referenced_schedules`, `notes`, `part`, `part_title`), based on a working critique of Section 2's large, undifferentiated definitions chunk. On review against **Table 3.1 of the proposal**, confirmed the approved schema only requires: `act_name`, `section_number`, `section_heading`, `full_text`. None of the extra fields are consumed by any pipeline component described in Section 3.4 (BM25 indexes and embeds `full_text` only; citation verification matches on `section_number` and `full_text`) — reverted to the simplified schema to avoid scope creep against the 13-week timeline.

**Final script (v2):** `lexrag-my/scripts/chunk_acts.py` — outputs exactly:
```json
{
  "act_name": "...",
  "section_number": "...",
  "section_heading": "...",
  "full_text": "...",
  "is_deleted": false
}
```
(`is_deleted` kept as the one deliberate addition beyond Table 3.1, since it directly supports the repealed-section handling decision above.)

**Bug fix during rescoping:** Part header lines ("Part I") and their all-caps title line ("PRELIMINARY") were leaking into `section_heading` after removing the dedicated Part-tracking fields — fixed by explicitly discarding those lines during parsing rather than letting them fall through to the heading-detection logic.

**Output generated:** all 3 Acts chunked — `Act265_chunks.json`, `Act599_chunks.json`, `Act709_chunks.json` in `lexrag-my/chunks/`.
- Act265: 89 chunks, 5 deleted/omitted, 6 chunks with no heading detected (flagged for manual check)
- Act599 / Act709: chunk counts not yet reviewed — generated but not inspected

### Not yet done
- **Manual review of all 3 chunk files** — about to start (see next step)
- MD5 checksum table still not saved to a file
- Full internal spot-check of Act599/Act709 cleaned text (pre-chunking) still outstanding from A3

### Next step
- **Manually check the 3 generated chunk files** (`Act265_chunks.json`, `Act599_chunks.json`, `Act709_chunks.json`) against the actual Acts — this is the A5 chunk validation activity, confirming section boundaries, headings, and `is_deleted` flags are accurate before this becomes the "Validated statutory chunks" milestone (M1)

---

## 5 Sept 2026

### A4 — Chunking bug found and fixed: regex only matched tab-delimited section lines

**Bug found:** `SECTION_PATTERN` in `chunks_acts.py` required a literal tab character between the section number and its heading (`^(\d+[a-zA-Z]{0,2})\.\t(.*)$`). Any section line where the cleaned text used a space instead of a tab after `N.` was silently missed by the parser, so that section never started a new chunk — its text got absorbed into the *previous* section's chunk instead.

**Fix:** loosened the pattern to match any whitespace: `^(\d+[a-zA-Z]{0,2})\.\s+(.*)$`.

**Impact — Act265 regenerated with the fix:**

| | Before fix | After fix |
|---|---|---|
| Total chunks | 89 | 137 |
| Deleted/omitted | 5 | 10 |
| No heading detected | 6 | 11 |

More real sections are now correctly split out (good), but "no heading detected" also rose from 6 to 11 — need to confirm during manual review whether these are genuine edge cases the heading heuristic still can't catch, or false positives introduced by the looser whitespace match.

**Generated for the first time — Act599:** `chunks/Act599_chunks.json` — 194 chunks, 4 deleted/omitted, 4 no-heading (not yet manually reviewed).

**Act709 chunked, but output landed in a different folder:** `chunks_acts.py`'s `OUTPUT_DIR` is currently set to `extracted_chunk_code_output/` (changed from `chunks/`), so the latest run wrote `extracted_chunk_code_output/Act709_chunks.json` (146 chunks, 0 deleted, 3 no-heading) there instead of alongside the other two Acts. Act265's and Act599's chunk files are still sitting in `chunks/` from earlier runs with the old `OUTPUT_DIR` — the three Acts' chunk files are now split across two folders.

### Not yet done
- **Reconcile output location:** pick one canonical folder (`chunks/`) for all `_chunks.json` files and move/regenerate Act709's into it; `extracted_chunk_code_output/` is currently untracked and inconsistent with where Act265/Act599 live.
- Manual review of all 3 chunk files (Act265, Act599, Act709) against the source Acts — still the outstanding A5 validation task, now against the corrected/regenerated chunk counts above.
- MD5 checksum table still not saved to a file.
- Full internal spot-check of Act599/Act709 cleaned text (pre-chunking) still outstanding from A3.

### Next step
- Decide on the chunk output folder and consolidate all 3 `_chunks.json` files into it
- Begin manual chunk validation (A5) on the corrected chunk files

---

## 6 Sept 2026

### Output location reconciled — Done ✅
- `chunks/` confirmed as the single canonical folder for all `_chunks.json` files
- Act709's output moved/regenerated into `chunks/`; `extracted_chunk_code_output/` no longer used
- All 3 Acts' chunk files (Act265, Act599, Act709) now live in one place

### A5 — Manual chunk validation: started ✅
- Began checking section boundaries, headings, and `is_deleted` flags in the corrected chunk files against the source Acts

### MD5 checksum table — saved ✅

| File | MD5 Checksum |
|---|---|
| Act265_EmploymentAct1955.pdf | `98443eaca7356d20c21f47e6070c0466` |
| Act599_ConsumerProtectionAct1999.pdf | `d518d00abed68ef9ab8212eba4e2a357` |
| Act709_PersonalDataProtectionAct2010.pdf | `165e8830a2b2cdffe30352b26ab82429` |

(previously only recorded in chat history — now needs saving to `data_provenance.md` in the project repo)

### Not yet done
- Full internal spot-check of Act599/Act709 cleaned text (pre-chunking) — still outstanding from A3
- A5 manual chunk validation — in progress, not yet complete for any of the 3 Acts

### Next step
- Continue A5 manual chunk validation across all 3 Acts
- Save the MD5 checksum table above into `data_provenance.md`
- Complete the outstanding Act599/Act709 mid-document spot-check

---

## 5 Sept 2026 (continued)

### MD5 checksum table — moved to `data_provenance.md` ✅
- Created `data_provenance.md` at project root with the checksum table, source (lom.agc.gov.my), and file locations
- Re-verified all 3 PDFs' MD5s against `Acts/` — match the values originally recorded in chat/PROGRESS.MD

### Not yet done
- A5 manual chunk validation — in progress, not yet complete for any of the 3 Acts
- Full internal spot-check of Act599/Act709 cleaned text (pre-chunking) — still outstanding from A3

### Next step
- Continue A5 manual chunk validation across all 3 Acts
- Complete the outstanding Act599/Act709 mid-document spot-check

---

## 5 Sept 2026 (continued)

### Repo reorganization: all dataset files grouped under `dataset/`

**Change made:** moved the three data folders under one parent directory instead of leaving them scattered at project root:
- `Acts/` → `dataset/acts/`
- `extracted_text/` → `dataset/extracted_text/`
- `chunks/` → `dataset/chunks/`

**Why:** keeps generated/source data separate from `scripts/` and project docs at root, and gives A5's validated output a clear home alongside the rest of the pipeline's data rather than mixed in with code.

**New folder:** `dataset/chunks_validated/` added to hold the post-A5-validation chunk files, separate from the raw generator output in `dataset/chunks/`. Currently seeded with the same content as `dataset/chunks/` (Act265, Act599, Act709) — no corrections have been written into it yet; it's the destination for edits as manual validation proceeds, keeping the unvalidated generator output in `dataset/chunks/` untouched as a reference.

**Scripts updated to match new paths:**
- `scripts/clean_act265.py`: `INPUT_DIR`/`OUTPUT_DIR` now point to `dataset/acts` / `dataset/extracted_text`; also switched the PyMuPDF import from `import fitz` to `import pymupdf` (the maintained import name) and dropped the old footer-stamp-leftover sanity check print (no longer wired to a variable after edits).
- `scripts/chunks_acts.py`: `INPUT_DIR`/`OUTPUT_DIR` now point to `dataset/extracted_text` / `dataset/chunks` (previously `extracted_chunk_code_output/`, the split-folder issue noted on 5 Sept — now consolidated under `dataset/`).
- `data_provenance.md`: updated the "Stored in" path and the `md5sum` re-verification command to `dataset/acts/*.pdf`.

### Not yet done
- Populate `dataset/chunks_validated/` with actual corrections from A5 review — currently just a copy of the unvalidated chunks
- A5 manual chunk validation — still in progress, not yet complete for any of the 3 Acts
- Full internal spot-check of Act599/Act709 cleaned text (pre-chunking) — still outstanding from A3
- Reorganization changes above are uncommitted — not yet staged/committed to git

### Next step
- Continue A5 manual chunk validation, writing corrected chunks into `dataset/chunks_validated/`
- Commit the reorganization (folder moves + path updates in scripts and `data_provenance.md`)
- Complete the outstanding Act599/Act709 mid-document spot-check

---

## 5 Sept 2026 (continued)

### A5 — Manual chunk validation: complete for all 3 Acts ✅

**Status:** all corrections written into `dataset/chunks_validated/`, confirmed against `dataset/chunks/` (raw generator output) — the two folders now genuinely diverge, not just a copy.

**Act265 (Employment Act 1955):** 141 → 137 chunks
- Removed 3 duplicate `section_number` entries (raw parser had emitted the same section twice for 3 sections)
- 40 sections corrected: 29 `section_heading` fixes, 23 `full_text` fixes (some sections had both)
- 10 chunks flagged `is_deleted` with blank heading (repealed/omitted sections — expected, matches the placeholder-chunk design decision from A4)

**Act599 (Consumer Protection Act 1999):** 204 → 194 chunks
- Removed 10 duplicate `section_number` entries
- 42 sections corrected: 33 `section_heading` fixes, 19 `full_text` fixes
- 4 chunks flagged `is_deleted` with blank heading

**Act709 (PDPA 2010):** 146 → 146 chunks (no duplicates to begin with)
- 12 sections corrected: 9 `section_heading` fixes, 3 `full_text` fixes
- Fixed the same Part-header-leaking-into-heading bug noted for Act265 in the A4 entry above (`"Part I PRELIMINARY 1"` → cleaned to `"1"` with heading corrected) — confirms this was a recurring parser edge case across Acts, not isolated to Act265
- 0 deleted/omitted sections (expected — PDPA 2010 is a newer Act with no repealed provisions in scope)

**Milestone M1 ("Validated statutory chunks," proposal Week 4) — reached ✅**
All three Acts now have zero duplicate section numbers, corrected headings/text, and `dataset/chunks_validated/` is the confirmed canonical dataset going into Phase B (retrieval pipeline).

### Not yet done
- Full internal spot-check of Act599/Act709 cleaned text (pre-chunking, schedules/tables especially) — still outstanding from A3, though A5's section-level corrections above did not surface issues traceable back to this
- MD5 checksum re-verification against `dataset/acts/*.pdf` post-reorg — confirm `data_provenance.md` command still resolves correctly
- Reorganization + A5 validation work is uncommitted — not yet staged/committed to git

### Next step
- Commit the reorganization and A5 validation corrections
- Begin Phase B (retrieval pipeline): B1 BM25 sparse index construction, using `dataset/chunks_validated/` as the source of truth

---

## 6 Sept 2026 (continued)

### B1 — BM25 sparse index: Done ✅
- Script: `scripts/b1_bm25_index.py`
- Tokenizer: lowercases, matches `[a-z0-9]+`, strips English stopwords via `sklearn`'s `ENGLISH_STOP_WORDS`
- `build_index()` fits `BM25Okapi` over all validated chunks' `full_text` and pickles `(retriever, corpus)` to `dataset/indexes/bm25/bm25_index.pkl`; reused on later runs unless `force=True`
- `search_bm25(query, k)` and `get_chunk(doc_id)` expose the retrieval interface for downstream use (B5)

### B2 — Dense retrieval index: Done ✅
- Script: `scripts/b2_dense_index.py`
- Model: `BAAI/bge-small-en-v1.5` (local SentenceTransformers, ~130MB) — same BGE family as the B4 cross-encoder reranker, for a consistent embedding/reranking story
- Embeddings stored in a persistent ChromaDB collection (`dataset/indexes/chroma`, cosine similarity space), added in batches of 256
- BGE's asymmetric-retrieval convention applied: queries are prefixed with `"Represent this sentence for searching relevant passages: "` before embedding; passages never are
- `search_dense(query, k)` converts Chroma's cosine distance back to similarity (`1 - distance`)

### B5 — Retrieval configuration controller: built (later removed — see 12 Sept entry)
- Script: `scripts/b5_retrieval_controller.py` — single `retrieve(query, k, method)` entry point switching between the 4 proposal configs (Table 3.5): `bm25_only`, `dense_only`, `hybrid_no_rerank`, `full`
- Wired: `bm25_only` (B1), `dense_only` (B2). `hybrid_no_rerank` / `full` raised `NotImplementedError`, pending B3 (RRF fusion) and B4 (cross-encoder reranker)

### Not yet done
- B3 — hybrid fusion (RRF), B4 — cross-encoder reranker (not started)
- Commit the Phase B work above

### Next step
- Build B3 (RRF fusion of B1 + B2), then B4 (cross-encoder reranker)

---

## 11 Sept 2026

### Code style decision: drop type hints/docstrings/argparse in favour of terse inline comments
- `scripts/b1_bm25_index.py`: removed all type hints and function docstrings, the `--rebuild` CLI flag, and the Windows stdout UTF-8 `reconfigure` workaround — replaced with short inline `#` comments; `__main__` demo block simplified to a plain `print(score, doc_id, heading)` loop
- House style going forward: no type hints, no argparse, no prose docstrings — short `#` comments only where the *why* isn't obvious
- `scripts/chunks_acts.py`: fixed `OUTPUT_DIR` (`dataset/chunks_test` → `dataset/chunks`), a leftover from an earlier test run

---

## 12 Sept 2026

### B2 restyled to match B1 — Done ✅
- Applied the same style pass to `scripts/b2_dense_index.py`: dropped the module/function docstrings, removed the `--rebuild` argparse flag and the Windows stdout-encoding workaround, simplified `__main__` to match B1's plain print loop
- Dense retrieval logic itself unchanged — same BGE model, query prefix, Chroma cosine index, batched insert

### BGE 512-token limit audit — Done ✅
- One-off terminal check (not saved as a script): tokenized all 477 validated chunks with the real `BAAI/bge-small-en-v1.5` tokenizer (`transformers.AutoTokenizer`)
- Result: min 6 / max 2,583 / mean 199.1 / median 122 tokens
- **36 chunks (7.5%) exceed BGE's 512-token window** — `sentence-transformers` truncates these silently (no error), so the tail of long sections is never embedded
- 0 chunks exceed the absolute 8,192-token hard limit
- Longest chunks are mostly definitions/interpretation sections: `Act265#2` (2583 tokens — Employment Act's definitions clause), `Act599#3` (1914), `Act265#60a` (1465), `Act709#4` (1367), `Act265#82` (1019)
- **Flagged as a known limitation for the report** — no sub-chunking implemented; still need to decide whether to sub-chunk sections over 512 tokens or accept the truncation as-is

### Scripts renamed to the activity-numbered convention — Done ✅
- To match the `b1_bm25_index.py` / `b2_dense_index.py` naming pattern, renamed via `git mv` (history preserved):
  - `scripts/clean_act265.py` → `scripts/a3_clean_acts.py` (A3 — PDF cleaning; despite the old filename it already cleaned all 3 Acts, not just 265)
  - `scripts/chunks_acts.py` → `scripts/a4_chunk_acts.py` (A4 — section-level chunking)
  - `scripts/load_chunks.py` → `scripts/a5_load_chunks.py` (A5 — loads the validated corpus for Phase B)
- Updated `from load_chunks import load_all_chunks` to `from a5_load_chunks import load_all_chunks` in both `b1_bm25_index.py` and `b2_dense_index.py`
- Verified `a5_load_chunks.load_all_chunks()` and `b1_bm25_index.py` still run correctly post-rename

### `scripts/b5_retrieval_controller.py` — removed (intentional)
- Deleted from the working tree at the user's request; not yet committed

### Not yet done
- Commit the accumulated Phase B work: B1/B2 builds, the B1/B2 style pass, the script renames, and the B5 removal — all currently uncommitted
- Decide on sub-chunking for the 36 chunks exceeding BGE's 512-token limit
- B3 — hybrid fusion (RRF), B4 — cross-encoder reranker (not started)
- If a retrieval controller (B5) is rebuilt later, it will need to import from the renamed `a5_load_chunks` module

### Next step
- Commit the current uncommitted changes
- Decide B3/B4 approach and begin implementation

---

## 27 Sept 2026

### Catch-up: B3, B4, B5 built since 12 Sept (not logged at the time)

**B3 — Hybrid fusion (RRF): Done ✅**
- Script: `scripts/b3_hybrid_no_rerank.py`
- `fuse(ranked_lists, k)` combines ranked lists by rank position only (ignores each retriever's own score scale), accumulating `1 / (RRF_K + rank)` per doc across lists, `RRF_K = 60`
- `search_hybrid(query, k, retriever_k)` runs B1 + B2 at `retriever_k` depth each, fuses via RRF, returns top `k`

**B4 — Cross-encoder reranker: Done ✅**
- Script: `scripts/b4_full.py`
- Model: `BAAI/bge-reranker-base` (same BGE family as B2's embedder)
- `rerank(query, candidate_ids, k)` scores each candidate with the cross-encoder and re-sorts
- `search_full(query, k, retriever_k, candidate_k)` gets `candidate_k` fused candidates from B3, reranks, returns top `k`

**B5 — Retrieval controller: rebuilt Done ✅**
- Script: `scripts/b5_retrieval_controller.py` — single `retrieve(query, k, method, retriever_k, candidate_k)` entry point switching between all four proposal configs (Table 3.5): `bm25_only`, `dense_only`, `hybrid_no_rerank`, `full`
- All four methods wired end-to-end now that B3/B4 exist (previous version only had `bm25_only`/`dense_only` wired, per the 6 Sept entry)
- Style pass applied to match B1/B2 (house style: no default args on `retrieve()`/`fuse()`/`search_hybrid()`/`rerank()`/`search_full()` — every caller passes args explicitly; no type hints/docstrings/argparse)
- Removed the earlier "return marker string instead of raising" fallback for an unknown `method` value, in favour of consistent explicit-argument style
- `Output` file regenerated with all four methods' results against the demo query ("Can I get any refund for receiving a defective item?"), each block now labelled with its method name and wall-clock time taken (bm25_only 0.001s, dense_only 0.150s, hybrid_no_rerank 0.057s, full 7.931s)

**Known issue caught during this catch-up review:** `b5_retrieval_controller.py`'s `METHOD` constant briefly held a typo (`"fulls"` instead of `"full"`) in the working tree; already corrected before this entry — flagged here since dropping the default-args made it fail loudly (crash) instead of silently returning a marker string, which is the intended tradeoff of the style change but worth remembering if `METHOD` is hand-edited again.

**M2 status (Retrieval pipeline completion, Week 7):** all four retrieval methods now exist, callable through one `retrieve()` interface, individually confirmed to run and return top-k ranked chunks. Not formally marked complete yet — pending a decision on what additional confirmation this milestone requires before signing off.

### Not yet done
- Commit the reorganization: B3/B4 additions, B5 rebuild/restyle, `Output` regeneration, `.gitignore` cleanup — all currently uncommitted
- Formal M2 sign-off decision
- Sub-chunking decision for the 36 chunks exceeding BGE's 512-token limit (open since 12 Sept)
- Test-set construction (Phase D) — proposal's R4 risk mitigation calls for this to run in parallel with Phase B, not after; not yet started as of this entry

### Next step
- Commit current uncommitted changes
- Decide M2 sign-off and scope M3 (generation + citation verification integration, Phase C)

---

## 27 Sept 2026 (continued)

### M3 started — C1/C2 (generation) built and tested end-to-end ✅

**Decisions locked in before implementation:** structured output forced via Anthropic tool-use (`tool_choice` mandating a single tool call) rather than prompted free-text JSON; model is `claude-haiku-4-5-20251001` for both generation and (later) the C4 judge, chosen over Sonnet for the R3 cost constraint; API key set up via a gitignored `.env` (`ANTHROPIC_API_KEY`), loaded with `python-dotenv`.

**C1 — Prompt and constraint design: Done ✅**
- Script: `scripts/c1_prompt_design.py`
- RACE-framework system prompts (Role, Action, Context, Expectation) — `SYSTEM_PROMPT` for initial generation, `SYSTEM_PROMPT_STRICT` for regeneration after a failed citation check (Table 3.3), differing only in how strictly the Action clause restricts the model to explicit section text
- `build_user_message(query, chunks)` assembles the Context block from retrieved chunk dicts (`doc_id`, `act_name`, `section_number`, `section_heading`, `full_text`) plus the question — pure string-building, no API calls, so it's independently testable

**C2 — Structured output and citation generation: Done ✅**
- Script: `scripts/c2_generate.py`
- `record_answer` tool schema forces `answer` (string), `claims` (list of `{claim_text, cited_doc_id}`), `insufficient_info` (bool) — `tool_choice` set to force this specific tool, so the model cannot reply with plain text
- `_valid()` is the schema checker required by Section 3.5.2 on top of the API-level schema enforcement — catches wrong types even though structural conformance is already guaranteed by tool-use
- On schema failure: one retry with a stricter follow-up instruction, then the proposal's exact fallback string ("Unable to generate a verified response.") rather than passing a malformed result downstream
- `generate(query, chunks, strict=False)` is the public entry point; `strict=True` swaps in `SYSTEM_PROMPT_STRICT` for use by C5's retry logic (not yet built)
- **Tested end-to-end:** ran the demo query ("Can I get any refund for receiving a defective item?") through B5's `full` retrieval method into `generate()` — got back a grounded, multi-claim answer citing `Act599#42`, `Act599#46`, `Act599#64`; no schema-retry path triggered, first tool call was already valid

**API key troubleshooting:** first key pasted into `.env` was an organization-level key not scoped to a workspace — Anthropic's API rejected requests with `anthropic-workspace-id` missing. Fixed by generating a workspace-scoped key instead; no code changes needed.

### Not yet done
- C3 — Existence check (rule-based), C4 — Support check (LLM-as-judge), C5 — Failure handling / single-retry wiring (not started)
- Test set (D1/D2) still not started — needed before C3–C5 can be evaluated against anything beyond ad hoc manual queries
- All of the above, plus `.env`/`requirements.txt`/`c1_prompt_design.py`/`c2_generate.py`, are uncommitted

### Next step
- Build C3 (existence check) and C4 (support check) against real generated claims like the ones C2 just produced
- Then C5 (single retry + status assignment: verified / verified_after_retry / insufficient_info)
- Test set construction (D1/D2) still pending — separate track, not yet started