#clean text -> JSON chunks
import re
import json
import os

DOCUMENTS = [
    {
        "input": "Act265_EmploymentAct1955_clean.txt",
        "output": "Act265_chunks.json",
        "act_id": "Act265",
        "act_name": "Employment Act 1955",
    },
    {
        "input": "Act599_ConsumerProtectionAct1999_clean.txt",
        "output": "Act599_chunks.json",
        "act_id": "Act599",
        "act_name": "Consumer Protection Act 1999",
    },
    {
        "input": "Act709_PersonalDataProtectionAct2010_clean.txt",
        "output": "Act709_chunks.json",
        "act_id": "Act709",
        "act_name": "Personal Data Protection Act 2010",
    },
]

INPUT_DIR = os.path.join("dataset", "extracted_text")
OUTPUT_DIR = os.path.join("dataset", "chunks")

os.makedirs(OUTPUT_DIR, exist_ok=True)

SECTION_PATTERN = re.compile(r"^(\d+[a-zA-Z]{0,2})\.\s+(.*)$")
PART_HEADER_PATTERN = re.compile(r"^Part\s+[IVXLCDM]+[A-Z]?\s*$", re.IGNORECASE)

# Match "section 18", "subsection 81d(4)", "sections 6, 7 and 12", "sections 10 to 16"
SEC_NUM = r"\d+[a-zA-Z]{0,2}(?:\([^)]*\))*"
REFERENCE_PATTERN = re.compile(
    rf"\b(?:sub)?sections?\s+({SEC_NUM}(?:\s*(?:,|and|or|to)\s*{SEC_NUM})*)",
    re.IGNORECASE,
)
# Match references to sections of other Acts, e.g. "section 18 of the Employment Act 1955"
OTHER_ACT_PATTERN = re.compile(r"^\s+of\s+(?!this\s+Act)", re.IGNORECASE)

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

# Extract the sections of the same Act that a section refers to
def extract_references(full_text, own_section, act_id, section_numbers):
    references = []
    for match in REFERENCE_PATTERN.finditer(full_text):
        # Skip references to sections of other Acts, e.g. "section 18 of the Employment Act 1955 (other Acts)"
        if OTHER_ACT_PATTERN.match(full_text[match.end():]):
            continue

        group = match.group(1)
        nums = [re.sub(r"\(.*", "", n).lower() for n in re.findall(SEC_NUM, group)]

        # Expand ranges such as "sections 10 to 16"
        targets = []
        parts = re.split(r"\s*(,|and|or|to)\s*", group)
        seps = parts[1::2]
        for idx, num in enumerate(nums):
            if idx > 0 and seps[idx - 1] == "to" and num.isdigit() and nums[idx - 1].isdigit():
                targets.extend(str(n) for n in range(int(nums[idx - 1]) + 1, int(num)))
            targets.append(num)

        for num in targets:
            doc_id = f"{act_id}#{num}"
            if num in section_numbers and num != own_section and doc_id not in references:
                references.append(doc_id)
    return references

def chunk_act(text, act_name, act_id):
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
                "doc_id": f"{act_id}#{current_section_num}",
                "act_name": act_name,
                "section_number": current_section_num,
                "section_heading": current_section_heading,
                "full_text": full_text,
                "references": [],
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

    # After all chunks are created, extract references for each chunk 
    section_numbers = {c["section_number"] for c in chunks}
    for c in chunks:
        c["references"] = extract_references(
            c["full_text"], c["section_number"], act_id, section_numbers
        )
    return chunks


for doc in DOCUMENTS:
    input_path = os.path.join(INPUT_DIR, doc["input"])
    output_path = os.path.join(OUTPUT_DIR, doc["output"])

    with open(input_path, encoding="utf-8") as f:
        text = f.read()

    # Chunk the act text into sections and headings
    chunks = chunk_act(text, doc["act_name"], doc["act_id"])

    # Save the chunks to a JSON file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"[{doc['input']}]")
    print(f"  Total chunks: {len(chunks)}")
    print()