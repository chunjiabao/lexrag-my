import fitz  # PyMuPDF
import os

INPUT_DIR = "Acts"
OUTPUT_DIR = "extracted_text"

os.makedirs(OUTPUT_DIR, exist_ok=True)

for filename in os.listdir(INPUT_DIR):
    if filename.lower().endswith(".pdf"):
        filepath = os.path.join(INPUT_DIR, filename)
        doc = fitz.open(filepath)

        full_text = ""
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            full_text += f"\n\n--- Page {page_num} ---\n\n{text}"

        doc.close()

        output_filename = filename.replace(".pdf", ".txt")
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        print(f"Extracted: {filename} -> {output_filename} ({len(full_text)} characters)")

print("\nDone. Check the extracted_text folder.")