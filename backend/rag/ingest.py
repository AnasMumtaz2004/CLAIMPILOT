import re
import sys
from datetime import datetime

import pymupdf
from sqlalchemy import delete

from database.connection import SessionLocal
from database.models import Policy
from rag.config import APPROVAL_POLICY_DIR
from rag.config import CLAIMS_GUIDELINES_DIR
from rag.config import CUSTOMER_POLICIES_DIR
from rag.config import DOC_APPROVAL_POLICY
from rag.config import DOC_CLAIMS_GUIDELINES
from rag.config import DOC_CUSTOMER_POLICY
from rag.config import DOMAIN_ALL
from rag.config import HARD_CHUNK_CHARS
from rag.config import INSURANCE_LINES
from rag.config import MAX_CHUNK_CHARS
from rag.config import MIN_BODY_CHARS
from rag.config import SOURCES_DIR
from rag.models import DocumentChunk
from rag.search import embed_texts

# Lines that are page furniture, not content
HEADER_TEXT = "FOR AI SYSTEM DEVELOPMENT"
FOOTER_ID_RE = re.compile(r"\|\s*(Policy No|Document ID):")
PAGE_NUMBER_RE = re.compile(r"Page \d+( of \d+)?\s*\|?\s*$")
TOC_HEADER_RE = re.compile(r"^Section\s+Description\b.*Page Number")

# Facts that are read from the document text
POLICY_NUMBER_RE = re.compile(r"Policy No: (POL-[A-Z0-9-]+)")
DOCUMENT_ID_RE = re.compile(r"Document ID: (DOC-[A-Z0-9-]+)")
FORM_VERSION_RE = re.compile(r"\bAST-[A-Z]{2,4}-(V\d+)")
INCEPTION_RE = re.compile(r"Policy Inception Date[ |]+(\d{1,2} [A-Za-z]+ \d{4})")

# Heading shapes in the customer policies
SECTION_RE = re.compile(r"^SECTION (\d+): (.+)$")
CLAUSE_RE = re.compile(r"^(\d+\.\d+) (CLAUSE|ENDORSEMENT) ([A-Z]+[.-]\d+): (.+)$")
PLAIN_CLAUSE_RE = re.compile(r"^(\d+\.\d+) ([A-Z][A-Z0-9 ,&/()'’—–:.\-]+)$")
SCHEDULE_RE = re.compile(r"^(\d+)\. ([A-Z][A-Z0-9 ,&/()'’—–:.\-]+)$")
SUBCLAUSE_RE = re.compile(r"^(\d+\.\d+\.\d+) ")

# Heading shapes in the internal documents
INTERNAL_SECTION_RE = re.compile(r"^(\d+)\. ([A-Z][A-Z0-9 ,&/()'’—–:.\-]{7,})$")
INTERNAL_CLAUSE_RE = re.compile(r"^(\d+\.\d+) ([A-Z].+)$")

# Words in a heading that tell us which insurance line a rule belongs to
DOMAIN_WORDS = [
    ("private vehicle", "private_vehicle"),
    ("health", "health"),
    ("commercial", "commercial"),
    ("home", "home"),
]


# ---------------------------------------------------------------------------
# Reading the PDF
# ---------------------------------------------------------------------------


def clean_cell(text):
    """Collapse the whitespace inside one table cell."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def table_to_text(page, table):
    """Write one table as rows of cells separated by pipes."""
    rows = []
    for row in table.rows:
        cells = []
        for cell_rect in row.cells:
            if cell_rect is None:
                cells.append("")
            else:
                cell_text = page.get_text("text", clip=pymupdf.Rect(cell_rect))
                cells.append(clean_cell(cell_text))

        # Skip rows that have no text at all
        if any(cells):
            rows.append("| " + " | ".join(cells) + " |")

    return "\n".join(rows)


def page_to_text(page):
    """Return the text of one page in reading order, with tables as pipe rows."""
    tables = page.find_tables().tables
    table_rects = []
    for table in tables:
        table_rects.append(pymupdf.Rect(table.bbox))

    # Collect the normal text blocks that are not inside a table
    items = []
    for block in page.get_text("blocks", sort=True):
        x0, y0, x1, y1, text, block_number, block_type = block

        # Block type 0 is text, the other types are images
        if block_type != 0:
            continue

        block_rect = pymupdf.Rect(x0, y0, x1, y1)
        inside_table = False
        for table_rect in table_rects:
            overlap = block_rect & table_rect
            if not overlap.is_empty and overlap.get_area() > 0.5 * block_rect.get_area():
                inside_table = True
                break

        if not inside_table:
            items.append((y0, text.strip()))

    # Add each table at its position on the page
    for table, table_rect in zip(tables, table_rects):
        items.append((table_rect.y0, table_to_text(page, table)))

    items.sort(key=lambda item: item[0])

    texts = []
    for y_position, text in items:
        if text:
            texts.append(text)
    return "\n".join(texts)


def read_pdf(path):
    """Read a PDF and return its title and the text of every page."""
    document = pymupdf.open(path)
    title = document.metadata.get("title") or path.stem

    pages = []
    for index in range(len(document)):
        text = page_to_text(document[index])
        pages.append({"page": index + 1, "text": text})

    document.close()
    return {"title": title, "pages": pages}


def clean_page_lines(page):
    """Split a page into lines and drop headers, footers and table of contents rows."""
    lines = []
    for raw_line in page["text"].split("\n"):
        text = raw_line.strip()

        if not text:
            continue
        if HEADER_TEXT in text:
            continue
        if text == "ONLY":
            continue
        if FOOTER_ID_RE.search(text):
            continue
        if PAGE_NUMBER_RE.search(text):
            continue
        if TOC_HEADER_RE.match(text):
            continue
        if text.upper().startswith("TABLE OF CONTENTS"):
            continue

        lines.append({"page": page["page"], "text": text})
    return lines


def find_match(pattern, text):
    """Return the first group of a regex match, or None."""
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1)


def find_domain(section_title, heading):
    """Work out which insurance line a rule belongs to from its headings."""
    title = section_title.lower()
    for word, domain in DOMAIN_WORDS:
        if word in title:
            return domain

    # Remove the clause number, then look at the first words of the heading
    start = re.sub(r"^[\d.]+\s*", "", heading.lower())
    for word, domain in DOMAIN_WORDS:
        if start.startswith(word):
            return domain

    return DOMAIN_ALL


# ---------------------------------------------------------------------------
# Finding headings and building blocks
# ---------------------------------------------------------------------------


def is_caps_heading(text):
    """Return True for an unnumbered all-capitals heading line."""
    if text.startswith("|"):
        return False
    if len(text) > 90:
        return False
    if len(text.split()) < 2:
        return False
    if ":" in text:
        return False
    if not text.upper() == text:
        return False
    return any(character.isalpha() for character in text)


def read_policy_heading(text, in_preamble):
    """Return heading details for a customer policy line, or None."""
    match = SECTION_RE.match(text)
    if match:
        return {"kind": "section", "number": match.group(1), "code": None, "title": match.group(2).strip()}

    match = CLAUSE_RE.match(text)
    if match:
        return {"kind": "clause", "number": match.group(1), "code": match.group(3), "title": text}

    match = PLAIN_CLAUSE_RE.match(text)
    if match:
        return {"kind": "clause", "number": match.group(1), "code": None, "title": text}

    # Before Section 2 the schedule has headings such as '1. POLICY IDENTIFICATION'
    if in_preamble:
        match = SCHEDULE_RE.match(text)
        if match:
            number = "1." + match.group(1)
            return {"kind": "clause", "number": number, "code": None, "title": number + " " + match.group(2)}

        if is_caps_heading(text):
            return {"kind": "clause", "number": None, "code": None, "title": text}

    return None


def read_internal_heading(text):
    """Return heading details for an internal document line, or None."""
    match = INTERNAL_SECTION_RE.match(text)
    if match:
        return {"kind": "section", "number": match.group(1), "code": None, "title": match.group(2).strip()}

    match = INTERNAL_CLAUSE_RE.match(text)
    if match:
        return {"kind": "clause", "number": match.group(1), "code": None, "title": text}

    return None


def join_wrapped_heading(lines, index):
    """Join a heading with the next line when its brackets are still open."""
    text = lines[index]["text"]
    if text.count("(") > text.count(")") and index + 1 < len(lines):
        return text + " " + lines[index + 1]["text"], index + 1
    return text, index


def new_block(section_title, number, code, heading, page):
    """Create an empty block that starts at a heading."""
    return {
        "section_title": section_title,
        "clause_number": number,
        "clause_code": code,
        "heading": heading,
        "page": page,
        "lines": [],
    }


def build_blocks(lines, doc_type):
    """Group the lines of a document into one block per clause."""
    is_policy = doc_type == DOC_CUSTOMER_POLICY
    in_preamble = is_policy
    section_title = "POLICY SCHEDULE / CERTIFICATE OF INSURANCE"
    if not is_policy:
        section_title = ""

    blocks = []
    current = new_block(section_title, None, None, "Document introduction", 1)

    index = 0
    while index < len(lines):
        text = lines[index]["text"]

        if is_policy:
            heading = read_policy_heading(text, in_preamble)
        else:
            heading = read_internal_heading(text)

        if heading is None:
            current["lines"].append(lines[index])
            index += 1
            continue

        # A heading may continue on the next line
        joined_text, last_index = join_wrapped_heading(lines, index)
        if last_index != index:
            if is_policy:
                heading = read_policy_heading(joined_text, in_preamble)
            else:
                heading = read_internal_heading(joined_text)
            text = joined_text

        blocks.append(current)

        if heading["kind"] == "section":
            in_preamble = False
            section_title = heading["title"]
            full_heading = heading["number"] + ". " + heading["title"]
            if is_policy:
                full_heading = "SECTION " + heading["number"] + ": " + heading["title"]
            current = new_block(section_title, heading["number"], None, full_heading, lines[index]["page"])
        else:
            current = new_block(section_title, heading["number"], heading["code"], heading["title"], lines[index]["page"])

        index = last_index + 1

    blocks.append(current)
    return blocks


# ---------------------------------------------------------------------------
# Splitting blocks into chunks
# ---------------------------------------------------------------------------


def split_block(block):
    """Split a long block into pieces, preferring to cut before a numbered sub-clause."""
    pieces = []
    current_lines = []
    current_size = 0
    active_sub = None
    piece_sub = None

    for line in block["lines"]:
        text = line["text"]
        sub_match = SUBCLAUSE_RE.match(text)
        too_big = current_size + len(text) + 1 > MAX_CHUNK_CHARS

        # Cut before a sub-clause when the piece is full, or anywhere when it is far too big
        must_cut = too_big and (sub_match is not None or current_size > HARD_CHUNK_CHARS)
        if current_lines and must_cut:
            pieces.append({"lines": current_lines, "sub_number": piece_sub})
            current_lines = []
            current_size = 0
            piece_sub = active_sub
            if sub_match is not None:
                piece_sub = sub_match.group(1)

        if sub_match is not None:
            active_sub = sub_match.group(1)

        current_lines.append(line)
        current_size = current_size + len(text) + 1

    if current_lines:
        pieces.append({"lines": current_lines, "sub_number": piece_sub})

    return pieces


def build_chunks(path, doc_type, domain):
    """Read one PDF and return its chunks as dictionaries, ready for the database."""
    pdf = read_pdf(path)
    source_file = path.relative_to(SOURCES_DIR).as_posix()

    all_text = "\n".join(page["text"] for page in pdf["pages"])

    policy_number = None
    product = None
    version = None
    effective_date = None

    if doc_type == DOC_CUSTOMER_POLICY:
        policy_number = find_match(POLICY_NUMBER_RE, all_text)
        if policy_number is None:
            raise ValueError(f"No policy number found in {source_file}")
        product = pdf["title"].split(" - ")[0].strip()
        version = find_match(FORM_VERSION_RE, all_text)
        inception = find_match(INCEPTION_RE, all_text)
        if inception is not None:
            effective_date = datetime.strptime(inception, "%d %B %Y").date().isoformat()
        label = f"{product} | Policy {policy_number}"
    else:
        document_id = find_match(DOCUMENT_ID_RE, all_text)
        if document_id is not None:
            version = document_id.split("-")[-1]
        label = pdf["title"]

    lines = []
    for page in pdf["pages"]:
        lines.extend(clean_page_lines(page))

    chunks = []
    for block in build_blocks(lines, doc_type):
        body_size = sum(len(line["text"]) for line in block["lines"])
        if body_size < MIN_BODY_CHARS:
            continue

        chunk_domain = domain
        if doc_type != DOC_CUSTOMER_POLICY:
            chunk_domain = find_domain(block["section_title"], block["heading"])

        pieces = split_block(block)
        for number, piece in enumerate(pieces, start=1):
            heading = block["heading"]
            if len(pieces) > 1:
                heading = f"{heading} (part {number} of {len(pieces)})"

            clause_number = block["clause_number"]
            if piece["sub_number"] is not None:
                clause_number = piece["sub_number"]

            body = "\n".join(line["text"] for line in piece["lines"])
            chunks.append({
                "document_type": doc_type,
                "insurance_domain": chunk_domain,
                "source_file": source_file,
                "policy_number": policy_number,
                "product": product,
                "version": version,
                "effective_date": effective_date,
                "section_title": block["section_title"],
                "clause_number": clause_number,
                "clause_code": block["clause_code"],
                "heading": heading,
                "page_number": piece["lines"][0]["page"],
                "page_end": piece["lines"][-1]["page"],
                "chunk_index": len(chunks),
                "content": label + "\n" + heading + "\n" + body,
            })

    return chunks


# ---------------------------------------------------------------------------
# Saving to the database
# ---------------------------------------------------------------------------


def find_source_files():
    """Return (path, document type, domain) for every PDF in the sources folder."""
    files = []

    for line in INSURANCE_LINES:
        for path in sorted((CUSTOMER_POLICIES_DIR / line).glob("*.pdf")):
            files.append((path, DOC_CUSTOMER_POLICY, line))

    for path in sorted(CLAIMS_GUIDELINES_DIR.glob("*.pdf")):
        files.append((path, DOC_CLAIMS_GUIDELINES, DOMAIN_ALL))

    for path in sorted(APPROVAL_POLICY_DIR.glob("*.pdf")):
        files.append((path, DOC_APPROVAL_POLICY, DOMAIN_ALL))

    return files


def save_chunks(db, source_file, chunks, vectors):
    """Replace the saved chunks of one document with new ones."""
    db.execute(delete(DocumentChunk).where(DocumentChunk.source_file == source_file))

    for chunk, vector in zip(chunks, vectors):
        row = DocumentChunk(embedding=vector, **chunk)
        db.add(row)

    db.commit()


def ingest_file(db, path, doc_type, domain):
    """Chunk, embed and save one PDF. Returns the chunks."""
    chunks = build_chunks(path, doc_type, domain)

    texts = []
    for chunk in chunks:
        texts.append(chunk["content"])

    vectors = embed_texts(texts)
    save_chunks(db, chunks[0]["source_file"], chunks, vectors)
    return chunks


def warn_about_missing_policies(db, policy_numbers):
    """Print a warning for every policy PDF that has no matching row in the policies table."""
    for number in sorted(policy_numbers):
        policy = db.query(Policy).filter(Policy.policy_number == number).first()
        if policy is None:
            print(f"WARNING: {number} is in a PDF but has no row in the policies table.")


def main():
    """Ingest every PDF. Use --dry-run to only print the chunks."""
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        for path, doc_type, domain in find_source_files():
            chunks = build_chunks(path, doc_type, domain)
            print(f"\n{path.name}: {len(chunks)} chunks | policy {chunks[0]['policy_number']}")
            for chunk in chunks:
                print(
                    f"  {str(chunk['clause_number']):8} {str(chunk['clause_code']):6} "
                    f"p{chunk['page_number']}-{chunk['page_end']} {chunk['insurance_domain']:16} "
                    f"{len(chunk['content']):5} {chunk['heading'][:60]}"
                )
        return

    db = SessionLocal()
    try:
        policy_numbers = set()
        for path, doc_type, domain in find_source_files():
            chunks = ingest_file(db, path, doc_type, domain)
            print(f"{path.name}: {len(chunks)} chunks saved")
            if doc_type == DOC_CUSTOMER_POLICY:
                policy_numbers.add(chunks[0]["policy_number"])

        warn_about_missing_policies(db, policy_numbers)
    finally:
        db.close()


if __name__ == "__main__":
    main()