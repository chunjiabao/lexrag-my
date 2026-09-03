"""
Cleaning script for Act 265 - Employment Act 1955
Method: crops each page's visible area BEFORE extracting text, physically
removing the header and footer bands rather than regex-stripping them after.

Run from the root of the lexrag-my project folder.
"""

import fitz  # PyMuPDF
import re
import os

INPUT_PATH = "Acts/Act265_EmploymentAct1955.pdf"
OUTPUT_PATH = "extracted_text/Act265_EmploymentAct1955_clean.txt"

# Page range for actual Act content (1-indexed, as seen in a PDF viewer)
START_PAGE = 11   # Section 1 begins here
END_PAGE = 110    # End of Second Schedule; "List of Amendments" starts on 111

# Crop band (in points) — measured from actual text positions on this PDF.
# Header text ends at y=86, footer text starts at y=738, page height=750.7
TOP_MARGIN = 87
BOTTOM_MARGIN = 736

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

doc = fitz.open(INPUT_PATH)
full_text = []

for page_num in range(START_PAGE - 1, min(END_PAGE, len(doc))):
    page = doc[page_num]
    rect = page.rect

    # Crop the page: keep only the band between header and footer
    crop_rect = fitz.Rect(rect.x0, TOP_MARGIN, rect.x1, BOTTOM_MARGIN)
    page.set_cropbox(crop_rect)

    text = page.get_text()

    # Remove any stray standalone page-number lines that might survive
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    # Collapse excess blank lines
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    full_text.append(text.strip())

doc.close()

result = "\n\n".join(full_text)

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(result)

print(f"Cleaned text saved to: {OUTPUT_PATH}")
print(f"Length: {len(result)} characters")
print("\n--- First 500 chars (sanity check) ---")
print(result[:500])
print("\n--- Check for leftover footer stamp ---")
if "WJW23" in result:
    print("WARNING: footer text still present, adjust BOTTOM_MARGIN")
else:
    print("Clean: no footer stamp found")