#PDF -> clean text
import pymupdf
import re
import os

DOCUMENTS = [
    {
        "input": "Act265_EmploymentAct1955.pdf",
        "output": "Act265_EmploymentAct1955_clean.txt",
        "start_page": 11,
        "end_page": 108,
        "top_margin": 87,
        "bottom_margin": 736,
        "footer_pattern": r"WJW23",
    },
    {
        "input": "Act599_ConsumerProtectionAct1999.pdf",
        "output": "Act599_ConsumerProtectionAct1999_clean.txt",
        "start_page": 13,
        "end_page": 134,
        "top_margin": 127,
        "bottom_margin": 775,
        "footer_pattern": r"WJW\d+|\.indd|\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*(AM|PM)",
    },
    {
        "input": "Act709_PersonalDataProtectionAct2010.pdf",
        "output": "Act709_PersonalDataProtectionAct2010_clean.txt",
        "start_page": 11,
        "end_page": 98,
        "top_margin": 67,
        "bottom_margin": 695,
        "footer_pattern": None,
    },
]

INPUT_DIR = "dataset/acts"
OUTPUT_DIR = "dataset/extracted_text"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_pdf(config):
    input_path = os.path.join(INPUT_DIR, config["input"])
    output_path = os.path.join(OUTPUT_DIR, config["output"])

    doc = pymupdf.open(input_path)
    full_text = []

    start = config["start_page"] - 1
    end = min(config["end_page"], len(doc))

    for page_num in range(start, end):
        page = doc[page_num]
        rect = page.rect

        crop_rect = pymupdf.Rect(rect.x0, config["top_margin"], rect.x1, config["bottom_margin"])
        page.set_cropbox(crop_rect)

        text = page.get_text()

        # Remove stray standalone page-number lines
        text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

        # Remove footer/printer stamp lines if a pattern is defined
        if config["footer_pattern"]:
            text = re.sub(rf"^.*{config['footer_pattern']}.*$", "", text, flags=re.MULTILINE)

        # Collapse excess blank lines
        text = re.sub(r"\n\s*\n+", "\n\n", text)

        full_text.append(text.strip())

    doc.close()

    result = "\n\n".join(full_text)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)


    print(f"[{config['input']}] -> {output_path}")
    print(f"  Pages processed: {start+1}-{end} ({end-start} pages)")
    print(f"  Length: {len(result)} chars")
    print()


for config in DOCUMENTS:
    clean_pdf(config)