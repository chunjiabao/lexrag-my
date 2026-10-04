from rapidfuzz import fuzz

# Unify curly quotation marks and dashes so they match their plain forms
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
    # Return the match score and the start and end of the matched passage in the original section text
    q = normalise(quote)[0].strip()
    text, positions = normalise(section_text)

    start = text.find(q)
    if start != -1:
        score, end = 100.0, start + len(q)
    else:
        # Not an exact match: find the most similar passage, tolerating PDF extraction differences
        alignment = fuzz.partial_ratio_alignment(q, text)
        score, start, end = alignment.score, alignment.dest_start, alignment.dest_end
    return score, positions[start], positions[end - 1] + 1


def check_quote(quote, section_text, min_quote_words, fuzzy_threshold):
    # Quotes that are too short cannot pass as evidence
    if len(quote.split()) < min_quote_words:
        return "fail"
    score, start, end = locate_quote(quote, section_text)
    if score >= fuzzy_threshold:
        return "pass"
    return "fail"
