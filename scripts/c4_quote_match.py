from rapidfuzz import fuzz

CHAR_MAP = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
})


def normalise(text):
    # Lowercase, unify quotes and dashes, and collapse whitespace.
    # Also keep each normalised character's position in the original text, so a match can be located there.
    chars = []
    positions = []
    for i, ch in enumerate(text.translate(CHAR_MAP).lower()):
        if ch.isspace():
            # Drop leading whitespace and repeated whitespace
            if not chars or chars[-1] == " ":
                continue
            ch = " "
        chars.append(ch)
        positions.append(i)
    return "".join(chars), positions


def locate_quote(quote, section_text):
    # [0] is the normalised quote, [1] is the position list 
    q = normalise(quote)[0].strip()
    text, positions = normalise(section_text)
    
    # find() method returns -1 (default) if the value is not found
    start = text.find(q)
    if start != -1:
        score, end = 100.0, start + len(q)
    else:
        alignment = fuzz.partial_ratio_alignment(q, text)
        score, start, end = alignment.score, alignment.dest_start, alignment.dest_end
    # -1 + 1 to avoids an index error when the quote is at the end of the section text
    return score, positions[start], positions[end - 1] + 1
