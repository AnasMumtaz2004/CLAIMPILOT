import hashlib
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path

import cv2
import imagehash
import numpy as np
import pymupdf
import pytesseract
from fastapi import HTTPException
from PIL import Image
from PIL import ImageOps
from sqlalchemy import desc
from sqlalchemy import func

from config import settings
from database.connection import SessionLocal
from database.models import ClaimDocument
from database.models import new_id
from services.audit_service import add_audit
from services.claim_service import DOC_TYPES_BY_LINE
from services.claim_service import as_utc

BLUR_THRESHOLD = 100.0
RESIZE_MAX_SIDE = 1600
UPLOAD_STATUSES = ["draft", "info_required"]

# OCR settings
OCR_DPI = 200
OCR_MAX_PAGES = 20
OCR_MAX_SIDE = 2500
OCR_MIN_PAGE_CONFIDENCE = 60.0
TEXT_LAYER_MIN_CHARS = 50


def detect_kind(data):
    """Detect file type from the first bytes."""
    if len(data) < 8:
        raise ValueError("Only JPG, PNG and PDF files are allowed.")

    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"

    if data[:8] == b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a":
        return "png"

    if data[:5] == b"%PDF-":
        return "pdf"

    raise ValueError("Only JPG, PNG and PDF files are allowed.")


def check_file(data):
    """Check file size and type."""
    if len(data) == 0:
        raise ValueError("The file is empty.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise ValueError(f"File is larger than {settings.max_upload_mb} MB.")

    return detect_kind(data)


def file_sha256(data):
    """Compute SHA256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def dms_to_decimal(dms, ref):
    """Convert GPS degrees/minutes/seconds to decimal."""
    degrees = float(dms[0])
    minutes = float(dms[1])
    seconds = float(dms[2])
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ["S", "W"]:
        decimal = -decimal
    return decimal


def read_exif(image):
    """Read EXIF metadata from an image."""
    try:
        exif_data = image.getexif()
        if not exif_data:
            return {"taken_at": None, "camera": None, "gps": None}

        taken_at = None
        datetime_original = exif_data.get(0x9003)
        if not datetime_original:
            exif_ifd = exif_data.get_ifd(0x8769)
            if exif_ifd:
                datetime_original = exif_ifd.get(0x9003)

        if not datetime_original:
            datetime_original = exif_data.get(0x0132)

        if datetime_original:
            try:
                parsed = datetime.strptime(datetime_original, "%Y:%m:%d %H:%M:%S")
                taken_at = parsed.isoformat()
            except Exception:
                taken_at = None

        camera = None
        make = exif_data.get(0x010F)
        model = exif_data.get(0x0110)
        if make or model:
            parts = []
            if make:
                parts.append(make.strip())
            if model:
                parts.append(model.strip())
            camera = " ".join(parts)

        gps = None
        gps_ifd = exif_data.get_ifd(0x8825)
        if gps_ifd:
            lat_ref = gps_ifd.get(1)
            lat_dms = gps_ifd.get(2)
            lon_ref = gps_ifd.get(3)
            lon_dms = gps_ifd.get(4)

            if lat_ref and lat_dms and lon_ref and lon_dms:
                lat = dms_to_decimal(lat_dms, lat_ref)
                lon = dms_to_decimal(lon_dms, lon_ref)
                gps = {"lat": lat, "lon": lon}

        return {"taken_at": taken_at, "camera": camera, "gps": gps}
    except Exception:
        return {"taken_at": None, "camera": None, "gps": None}


def image_phash(image):
    """Compute perceptual hash."""
    return str(imagehash.phash(image))


def blur_score(image):
    """Compute blur score using Laplacian variance."""
    rgb_image = image.convert("RGB")
    gray = cv2.cvtColor(np.array(rgb_image), cv2.COLOR_RGB2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(laplacian.var())


def make_resized(image):
    """Resize image to fit within max dimensions."""
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    result = image.copy()
    result.thumbnail((RESIZE_MAX_SIDE, RESIZE_MAX_SIDE))
    return result


def cleanup_for_ocr(image):
    """Prepare image for OCR."""
    image = ImageOps.exif_transpose(image)
    gray = image.convert("L")
    gray = ImageOps.autocontrast(gray)

    gray_np = np.array(gray)
    denoised = cv2.fastNlMeansDenoising(gray_np, None, 10, 7, 21)

    threshold_value, thresholded = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return Image.fromarray(thresholded)


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------


def set_tesseract_path():
    """Use the Tesseract path from the settings when one is given."""
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


def detect_rotation(image):
    """Ask Tesseract how far the page is turned. Returns 0, 90, 180 or 270."""
    try:
        info = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
    except RuntimeError:
        # Too little text to detect the orientation, so assume the page is upright
        return 0

    return int(info.get("rotate", 0))


def read_at_angle(image, angle):
    """Turn the page by the given angle, clean it and read it."""
    turned = image
    if angle != 0:
        # Tesseract gives the clockwise angle needed, PIL rotates counter-clockwise
        turned = image.rotate(-angle, expand=True)

    cleaned = cleanup_for_ocr(turned)
    return read_words(cleaned)


def read_words(image):
    """Run OCR on a cleaned image and return the text and the average confidence."""
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    # Collect the words of each text line, and the confidence of each word
    lines = {}
    confidences = []
    for index in range(len(data["text"])):
        word = data["text"][index].strip()
        if not word:
            continue

        confidence = float(data["conf"][index])
        if confidence < 0:
            continue

        key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
        if key not in lines:
            lines[key] = []
        lines[key].append(word)
        confidences.append(confidence)

    if len(confidences) == 0:
        return "", 0.0

    text_lines = []
    for key in sorted(lines):
        text_lines.append(" ".join(lines[key]))

    average = sum(confidences) / len(confidences)
    return "\n".join(text_lines), round(average, 1)


def ocr_image(image):
    """Read one page image. Returns the text and the confidence."""
    set_tesseract_path()

    # Very large photos make cleaning and OCR slow, so shrink them first
    small = ImageOps.exif_transpose(image).convert("RGB")
    small.thumbnail((OCR_MAX_SIDE, OCR_MAX_SIDE))

    # First try the angle that Tesseract suggests
    first_angle = detect_rotation(small)
    best_text, best_confidence = read_at_angle(small, first_angle)
    if best_confidence >= OCR_MIN_PAGE_CONFIDENCE:
        return best_text, best_confidence

    # The orientation guess is not always right on short pages, so try the other angles
    # A page that is turned the wrong way is read with very low confidence
    for angle in [0, 90, 180, 270]:
        if angle == first_angle:
            continue

        text, confidence = read_at_angle(small, angle)
        if confidence > best_confidence:
            best_text = text
            best_confidence = confidence

    return best_text, best_confidence


def make_page(number, text, confidence, method):
    """Build the result of one page."""
    return {
        "page": number,
        "text": text,
        "confidence": confidence,
        "method": method,
        "low_confidence": confidence < OCR_MIN_PAGE_CONFIDENCE,
    }


def read_document_pages(full_path):
    """Read every page of a saved file. Returns the pages and the real page count."""
    with open(full_path, "rb") as file:
        data = file.read()

    kind = detect_kind(data)

    if kind != "pdf":
        image = Image.open(BytesIO(data))
        text, confidence = ocr_image(image)
        return [make_page(1, text, confidence, "ocr")], 1

    pdf = pymupdf.open(stream=data, filetype="pdf")
    page_count = len(pdf)

    pages = []
    for index in range(min(page_count, OCR_MAX_PAGES)):
        page = pdf[index]

        # A PDF that already has real text does not need OCR
        layer_text = page.get_text().strip()
        if len(layer_text) >= TEXT_LAYER_MIN_CHARS:
            pages.append(make_page(index + 1, layer_text, 100.0, "text_layer"))
            continue

        pixmap = page.get_pixmap(dpi=OCR_DPI)
        image = Image.open(BytesIO(pixmap.tobytes("png")))
        text, confidence = ocr_image(image)
        pages.append(make_page(index + 1, text, confidence, "ocr"))

    pdf.close()
    return pages, page_count


def build_ocr_result(document_id, pages, page_count, error):
    """Build the dictionary that is saved in the document's extracted column."""
    overall_confidence = None
    has_low_confidence = False

    if len(pages) > 0:
        total = 0.0
        for page in pages:
            total = total + page["confidence"]
            if page["low_confidence"]:
                has_low_confidence = True
        overall_confidence = round(total / len(pages), 1)

    return {
        "document_id": document_id,
        "pages": pages,
        "page_count": page_count,
        "pages_processed": len(pages),
        "truncated": page_count > len(pages),
        "overall_confidence": overall_confidence,
        "has_low_confidence": has_low_confidence,
        "error": error,
    }


def process_document_ocr(db, document_id):
    """Run OCR for one saved document and store the result on its row."""
    doc = db.query(ClaimDocument).filter(ClaimDocument.id == document_id).first()
    if doc is None:
        return

    doc.ocr_status = "processing"
    db.commit()

    try:
        full_path = os.path.join(settings.storage_dir, doc.original_path)
        pages, page_count = read_document_pages(full_path)
        result = build_ocr_result(doc.id, pages, page_count, None)

        status = "done"
        if result["has_low_confidence"]:
            status = "low_quality"
    except Exception as error:
        # OCR can fail in many ways (bad file, Tesseract missing) and none of them may crash the app
        result = build_ocr_result(doc.id, [], 0, str(error))
        status = "failed"

    doc.extracted = result
    doc.ocr_status = status

    add_audit(
        db,
        "system",
        "document_ocr_finished",
        doc.claim_id,
        {"document_id": doc.id, "status": status, "confidence": result["overall_confidence"]},
    )
    db.commit()


def run_document_ocr_task(document_id):
    """Background task: open a new database session and run OCR for one document."""
    db = SessionLocal()
    try:
        process_document_ocr(db, document_id)
    finally:
        db.close()


def get_document_ocr(db, staff, claim, document_id):
    """Return the OCR text of one document for staff. Logs the access."""
    doc = db.query(ClaimDocument).filter(
        ClaimDocument.id == document_id,
        ClaimDocument.claim_id == claim.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    extracted = doc.extracted or {}

    add_audit(db, staff.id, "document_ocr_viewed", claim.id, {"document_id": doc.id})
    db.commit()

    return {
        "document_id": doc.id,
        "doc_type": doc.doc_type,
        "ocr_status": doc.ocr_status,
        "overall_confidence": extracted.get("overall_confidence"),
        "page_count": extracted.get("page_count", 0),
        "truncated": extracted.get("truncated", False),
        "error": extracted.get("error"),
        "pages": extracted.get("pages", []),
    }


# ---------------------------------------------------------------------------
# Saving and listing documents
# ---------------------------------------------------------------------------


def save_upload(claim_id, data):
    """Save uploaded file and create thumbnail."""
    kind = check_file(data)

    file_id = new_id()

    ext_map = {"jpeg": "jpg", "png": "png", "pdf": "pdf"}
    ext = ext_map[kind]

    original_path = f"originals/{claim_id}/{file_id}.{ext}"
    resized_path = f"resized/{claim_id}/{file_id}.jpg"

    original_full = os.path.join(settings.storage_dir, original_path)
    resized_full = os.path.join(settings.storage_dir, resized_path)

    os.makedirs(os.path.dirname(original_full), exist_ok=True)
    os.makedirs(os.path.dirname(resized_full), exist_ok=True)

    with open(original_full, "wb") as f:
        f.write(data)

    mime_map = {"jpeg": "image/jpeg", "png": "image/png", "pdf": "application/pdf"}
    mime_type = mime_map[kind]

    size_bytes = len(data)
    hash_value = file_sha256(data)

    if kind in ["jpeg", "png"]:
        try:
            image = Image.open(BytesIO(data))
            image.load()
        except Exception:
            raise ValueError("The image could not be read.")

        exif = read_exif(image)
        img_hash = image_phash(image)
        quality = blur_score(image)

        resized = make_resized(image)
        resized.save(resized_full, "JPEG", quality=85)
    else:
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except Exception:
            raise ValueError("The PDF could not be read.")

        page = doc[0]
        pix = page.get_pixmap(dpi=100)
        pix.save(resized_full)

        img_hash = ""
        quality = None
        exif = {}

    return {
        "original_path": original_path.replace("\\", "/"),
        "resized_path": resized_path.replace("\\", "/"),
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "file_hash": hash_value,
        "image_hash": img_hash,
        "quality_score": quality,
        "exif": exif,
    }


def document_to_dict(doc):
    """Convert a document to a dictionary. The OCR text is not included."""
    retake = False
    if doc.doc_type.startswith("photo") and doc.quality_score is not None:
        if doc.quality_score < BLUR_THRESHOLD:
            retake = True

    quality_score = None
    if doc.quality_score is not None:
        quality_score = float(doc.quality_score)

    return {
        "id": doc.id,
        "claim_id": doc.claim_id,
        "doc_type": doc.doc_type,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
        "quality_score": quality_score,
        "retake": retake,
        "ocr_status": doc.ocr_status,
        "uploaded_at": as_utc(doc.uploaded_at).isoformat(),
    }


def list_claim_documents(db, claim):
    """Return all documents on a claim, newest first."""
    docs = db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim.id).order_by(desc(ClaimDocument.uploaded_at)).all()
    return [document_to_dict(d) for d in docs]


def upload_claim_document(db, user, claim, doc_type, file):
    """Validate, store and record one uploaded document."""
    if claim.status not in UPLOAD_STATUSES:
        raise HTTPException(status_code=400, detail="Documents cannot be added to this claim right now.")

    allowed_types = DOC_TYPES_BY_LINE.get(claim.line, [])
    if doc_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Unknown document type.")

    doc_count = db.query(func.count(ClaimDocument.id)).filter(ClaimDocument.claim_id == claim.id).scalar()
    if doc_count >= settings.max_files_per_claim:
        raise HTTPException(status_code=400, detail="Too many files for this claim.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)

    try:
        kind = check_file(data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if doc_type.startswith("photo_") and kind not in ["jpeg", "png"]:
        raise HTTPException(status_code=400, detail="Photos must be JPG or PNG images.")

    hash_value = file_sha256(data)
    existing = db.query(ClaimDocument).filter(
        ClaimDocument.claim_id == claim.id,
        ClaimDocument.file_hash == hash_value,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="This file was already uploaded for this claim.")

    try:
        result = save_upload(claim.id, data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    doc = ClaimDocument(
        claim_id=claim.id,
        doc_type=doc_type,
        original_path=result["original_path"],
        resized_path=result["resized_path"],
        mime_type=result["mime_type"],
        size_bytes=result["size_bytes"],
        file_hash=result["file_hash"],
        image_hash=result["image_hash"],
        quality_score=result["quality_score"],
        exif=result["exif"],
        ocr_status="pending",
    )
    db.add(doc)
    db.flush()

    add_audit(
        db,
        user.id,
        "document_uploaded",
        claim.id,
        {"document_id": doc.id, "doc_type": doc_type, "file_hash": result["file_hash"]},
    )
    db.commit()
    return document_to_dict(doc)


def open_claim_document(db, user, claim, document_id):
    """Return a document row and its file path after an ownership check. Logs the access."""
    doc = db.query(ClaimDocument).filter(
        ClaimDocument.id == document_id,
        ClaimDocument.claim_id == claim.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    file_path = Path(settings.storage_dir) / doc.original_path
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="The file is missing from storage.")

    add_audit(db, user.id, "document_viewed", claim.id, {"document_id": doc.id})
    db.commit()
    return doc, file_path


# ---------------------------------------------------------------------------
# Used by the AI agents
# ---------------------------------------------------------------------------


def get_ocr_text_for_agent(db, claim_id, document_id):
    """Return the OCR result of one document on a claim for an AI agent, or None if there is no such document."""
    doc = db.query(ClaimDocument).filter(
        ClaimDocument.id == document_id,
        ClaimDocument.claim_id == claim_id,
    ).first()
    if doc is None:
        return None

    extracted = doc.extracted or {}
    return {
        "document_id": doc.id,
        "doc_type": doc.doc_type,
        "ocr_status": doc.ocr_status,
        "overall_confidence": extracted.get("overall_confidence"),
        "page_count": extracted.get("page_count", 0),
        "pages_processed": extracted.get("pages_processed", 0),
        "truncated": extracted.get("truncated", False),
        "error": extracted.get("error"),
        "pages": extracted.get("pages", []),
    }


def run_ocr_now(db, document_id):
    """Read a document with OCR now, and return its new OCR status."""
    process_document_ocr(db, document_id)

    doc = db.query(ClaimDocument).filter(ClaimDocument.id == document_id).first()
    if doc is None:
        return "failed"

    db.refresh(doc)
    return doc.ocr_status