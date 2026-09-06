#clean text -> JSON chunks 
import re
import json
import os

DOCUMENTS = [
    {
        "input": "Act265_EmploymentAct1955_clean.txt",
        "output": "Act265_chunks.json",
        "act_name": "Employment Act 1955",
    },
    {
        "input": "Act599_ConsumerProtectionAct1999_clean.txt",
        "output": "Act599_chunks.json",
        "act_name": "Consumer Protection Act 1999",
    },
    {
        "input": "Act709_PersonalDataProtectionAct2010_clean.txt",
        "output": "Act709_chunks.json",
        "act_name": "Personal Data Protection Act 2010",
    },
]

INPUT_DIR = "dataset/extracted_text"
OUTPUT_DIR = "dataset/chunks_test"

os.makedirs(OUTPUT_DIR, exist_ok=True)

SECTION_PATTERN = re.compile(r"^(\d+[a-zA-Z]{0,2})\.\s+(.*)$")
PART_HEADER_PATTERN = re.compile(r"^Part\s+[IVXLCDM]+[A-Z]?\s*$", re.IGNORECASE)

# Identify uppercase Part titles such as "PRELIMINARY"
def is_part_title_line(line):
    s = line.strip()
    return bool(s) and s.isupper() and not re.search(r"\d", s)

# Identify lines that look like section headings 
def looks_like_title(line):
    s = line.strip()
    if not s or len(s) > 70:
        return False
    if re.search(r"\d", s):
        return False
    if s.endswith(( ";", ",", ":")):
        return False
    if s.startswith(('"', "(")):
        return False
    return True

def chunk_act(text, act_name):
    lines = text.split("\n")

    chunks = []
    current_section_num = None
    current_section_heading = None
    current_lines = []

    def flush():
        if current_section_num is not None:
            # Join the lines of the current section into a single string 
            full_text = "\n".join(current_lines).strip()

            chunks.append({
                "act_name": act_name,
                "section_number": current_section_num,
                "section_heading": current_section_heading,
                "full_text": full_text,
                "is_deleted": bool(re.match(
                    r"^\(Deleted|^\(Omitted", full_text, re.IGNORECASE
                )),
            })

    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip Part headers and titles
        if PART_HEADER_PATTERN.match(line.strip()):
            i += 1
            if i < len(lines) and lines[i].strip() == "":
                i += 1
            if i < len(lines) and is_part_title_line(lines[i]):
                i += 1
            continue

        sec_match = SECTION_PATTERN.match(line)
        if sec_match:
            # Move heading lines to the new section
            heading_lines = []
            while current_lines and looks_like_title(current_lines[-1]):
                heading_lines.insert(0, current_lines[-1].strip())
                current_lines = current_lines[:-1]
            next_heading = " ".join(heading_lines) if heading_lines else None

            flush()
            # Save the new section details
            current_section_num = sec_match.group(1)
            current_section_heading = next_heading
            current_lines = [sec_match.group(2)]
            i += 1
            continue

        current_lines.append(line)
        i += 1

    flush()
    return chunks


def main():
    for doc in DOCUMENTS:
        input_path = os.path.join(INPUT_DIR, doc["input"])
        output_path = os.path.join(OUTPUT_DIR, doc["output"])

        with open(input_path, encoding="utf-8") as f:
            text = f.read()

        # Chunk the act text into sections and headings
        chunks = chunk_act(text, doc["act_name"])

        # Save the chunks to a JSON file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

        print(f"[{doc['input']}] -> {output_path}")
        print(f"  Total chunks: {len(chunks)}")
        print()
        
if __name__ == "__main__":
    main()