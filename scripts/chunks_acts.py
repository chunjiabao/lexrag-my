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
OUTPUT_DIR = "dataset/chunks"

os.makedirs(OUTPUT_DIR, exist_ok=True)

SECTION_PATTERN = re.compile(r"^(\d+[a-zA-Z]{0,2})\.\s+(.*)$")

# Part headers (e.g. "Part I") and the all-caps Part title line that follows
# them (e.g. "PRELIMINARY") aren't part of Table 3.1's schema, but they are
# structural noise that must be discarded, not swept into section_heading
# or full_text.
PART_HEADER_PATTERN = re.compile(r"^Part\s+[IVXLCDM]+[A-Z]?\s*$", re.IGNORECASE)


def is_part_title_line(line):
    """All-caps line (e.g. 'PRELIMINARY') immediately following a Part
    header — treated as part of the discarded Part marker, not a heading."""
    s = line.strip()
    return bool(s) and s.isupper() and not re.search(r"\d", s)


def looks_like_title(line):
    """Heuristic for a real section heading line: short, no digits, no
    trailing sentence punctuation, not a quoted defined term or a
    subsection marker like '(1)'."""
    s = line.strip()
    if not s or len(s) > 70:
        return False
    if re.search(r"\d", s):
        return False
    if s.endswith((".", ";", ",", ":")):
        return False
    if s.startswith(("\u201c", '"', "(")):
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
            full_text = "\n".join(current_lines).strip()
            chunks.append({
                "act_name": act_name,
                "section_number": current_section_num,
                "section_heading": current_section_heading,
                "full_text": full_text,
                # Not in Table 3.1, but kept as it's needed by your own
                # project logic to decide how to handle repealed sections
                # during chunking/indexing (see DECISIONS.md).
                "is_deleted": bool(re.match(
                    r"^\(Deleted|^\(Omitted", full_text, re.IGNORECASE
                )),
            })

    i = 0
    while i < len(lines):
        line = lines[i]

        # Discard Part header lines and their following all-caps title
        # line entirely — not part of Table 3.1's schema.
        if PART_HEADER_PATTERN.match(line.strip()):
            i += 1
            if i < len(lines) and lines[i].strip() == "":
                i += 1
            if i < len(lines) and is_part_title_line(lines[i]):
                i += 1
            continue

        sec_match = SECTION_PATTERN.match(line)
        if sec_match:
            # Walk backward through consecutive heading-looking lines
            # (headings can wrap across 2+ lines) and pop them off the
            # PREVIOUS section's body instead of leaving them stuck there.
            heading_lines = []
            while current_lines and looks_like_title(current_lines[-1]):
                heading_lines.insert(0, current_lines[-1].strip())
                current_lines = current_lines[:-1]
            next_heading = " ".join(heading_lines) if heading_lines else None

            flush()

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

        if not os.path.exists(input_path):
            print(f"[SKIP] {input_path} not found")
            continue

        with open(input_path, encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_act(text, doc["act_name"])

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

        deleted = sum(1 for c in chunks if c["is_deleted"])
        no_heading = sum(1 for c in chunks if not c["section_heading"])

        print(f"[{doc['input']}] -> {output_path}")
        print(f"  Total chunks: {len(chunks)}")
        print(f"  Deleted/Omitted sections: {deleted}")
        print(f"  Chunks with no heading found: {no_heading}  (spot-check these)")
        print()


if __name__ == "__main__":
    main()