# pdf_service.py
import os
import base64
import json
import re
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# המילון שולב ישירות לקובץ עם הקואורדינטות המדויקות מה-JSON שסיפקת
DEFAULT_FIELD_COORDINATES = {
    "tax_year": {"x": 218, "y": 83, "width": 68, "height": 17, "num_chars": 4},
    "employer_name": {"x": 250, "y": 120, "width": 200, "height": 20},
    "employer_tik_nikuyim": {"x": 650, "y": 120, "width": 150, "height": 20, "num_chars": 8},
    "tz": {"x": 439, "y": 211, "width": 101, "height": 24, "num_chars": 9},
    "last_name": {"x": 314, "y": 212, "width": 123, "height": 27},
    "first_name": {"x": 210, "y": 210, "width": 100, "height": 27},
    "birth_date": {"x": 120, "y": 212, "width": 88, "height": 25, "num_chars": 8},
    "sex_female": {"x": 506, "y": 293, "width": 28, "height": 11},
    "sex_male": {"x": 550, "y": 293, "width": 28, "height": 11}, # מיקום משוער ע"ב הנקבה
    "address_street": {"x": 226, "y": 240, "width": 164, "height": 22},
    "address_house_num": {"x": 204, "y": 241, "width": 22, "height": 19},
    "address_city": {"x": 109, "y": 241, "width": 94, "height": 23},
    "address_zip": {"x": 50, "y": 241, "width": 50, "height": 20},
    "kupat_holim_name": {"x": 33, "y": 291, "width": 39, "height": 12},
    "resident_yes": {"x": 290, "y": 276, "width": 27, "height": 14},
    "resident_no": {"x": 250, "y": 276, "width": 27, "height": 14},
    "marital_single": {"x": 457, "y": 276, "width": 36, "height": 15},
    "marital_married": {"x": 391, "y": 278, "width": 42, "height": 13},
    "other_income_salary": {"x": 169, "y": 357, "width": 76, "height": 11},
    "work_start_date": {"x": 31, "y": 372, "width": 91, "height": 18, "num_chars": 8},
    "declaration_date": {"x": 146, "y": 641, "width": 78, "height": 14, "num_chars": 8},
    "mobile": {"x": 180, "y": 345, "width": 150, "height": 20},
    "email": {"x": 500, "y": 345, "width": 250, "height": 20},
    "spouse_tz": {"x": 180, "y": 470, "width": 198, "height": 20, "num_chars": 9},
    "spouse_last_name": {"x": 450, "y": 470, "width": 150, "height": 20},
    "spouse_first_name": {"x": 700, "y": 470, "width": 150, "height": 20},
    "spouse_birth_date": {"x": 180, "y": 510, "width": 100, "height": 20, "num_chars": 8},
    "spouse_aliyah_date": {"x": 350, "y": 510, "width": 100, "height": 20, "num_chars": 8},
    "spouse_income_none": {"x": 450, "y": 510, "width": 15, "height": 15},
    "spouse_income_has": {"x": 600, "y": 510, "width": 15, "height": 15},
    "child_name": {"x": 180, "y": 600, "width": 150, "height": 20},
    "child_tz": {"x": 450, "y": 600, "width": 198, "height": 20, "num_chars": 9, "step_x": 22},
    "child_dob": {"x": 720, "y": 600, "width": 100, "height": 20, "num_chars": 8, "step_x": 12},
    "child_row_height": {"y": 28},
    "no_other_income": {"x": 150, "y": 780, "width": 15, "height": 15},
    "other_income_pension": {"x": 150, "y": 840, "width": 15, "height": 15},
    "other_income_allowance": {"x": 150, "y": 870, "width": 15, "height": 15},
    "other_income_partial": {"x": 150, "y": 900, "width": 15, "height": 15},
    "credit_here": {"x": 500, "y": 780, "width": 15, "height": 15},
    "credit_nothere": {"x": 500, "y": 810, "width": 15, "height": 15},
    "tax_coordination_approval": {"x": 150, "y": 880, "width": 15, "height": 15},
    "credit_disabled_blind": {"x": 120, "y": 940, "width": 15, "height": 15},
    "credit_resident_locality": {"x": 120, "y": 970, "width": 15, "height": 15},
    "locality_name": {"x": 300, "y": 970, "width": 150, "height": 20},
    "credit_single_parent": {"x": 120, "y": 1000, "width": 15, "height": 15},
    "credit_children_in_custody": {"x": 120, "y": 1030, "width": 15, "height": 15},
    "credit_children_not_in_custody": {"x": 120, "y": 1060, "width": 15, "height": 15},
    "credit_single_parent_toddlers": {"x": 120, "y": 1090, "width": 15, "height": 15},
    "credit_children_disabled": {"x": 120, "y": 1120, "width": 15, "height": 15},
    "credit_alimony_ex_spouse": {"x": 120, "y": 1150, "width": 15, "height": 15},
    "credit_academic_degree": {"x": 120, "y": 1180, "width": 15, "height": 15},
    "credit_reserve_duty": {"x": 120, "y": 1210, "width": 15, "height": 15},
    "credit_new_immigrant": {"x": 120, "y": 1240, "width": 15, "height": 15},
    "declared_true": {"x": 120, "y": 1260, "width": 15, "height": 15},
    "signature": {"x": 220, "y": 1300, "width": 160, "height": 70}
}

MAX_FONT_SIZE = 30
MIN_FONT_SIZE = 12
BOLD_MAX_FONT_SIZE = 34
CHECKBOX_FONT_SIZE = 28

_FONT_CACHE = {}


def _font_path_candidates():
    bundled = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    system = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ["arial.ttf", bundled, system]


def load_font(size: int):
    """טוען פונט לפי גודל, עם מטמון קטן כדי לא לפתוח את קובץ הפונט שוב ושוב."""
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    for path in _font_path_candidates():
        try:
            f = ImageFont.truetype(path, size)
            _FONT_CACHE[size] = f
            return f
        except IOError:
            continue
    f = ImageFont.load_default()
    _FONT_CACHE[size] = f
    return f


def fit_font_to_box(text: str, box_width: int, box_height: int, max_size=MAX_FONT_SIZE, min_size=MIN_FONT_SIZE):
    """
    Auto-Fit: מוצא את הגודל הגדול ביותר שבו הטקסט עדיין נכנס לגובה/רוחב התיבה.
    מחזיר (font, overflowed: bool) - overflowed=True אם גם בגודל המינימלי הטקסט לא נכנס.
    """
    if not text:
        return load_font(max_size), False
    for size in range(max_size, min_size - 1, -1):
        font = load_font(size)
        bbox = font.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= box_width and h <= box_height:
            return font, False
    return load_font(min_size), True


def draw_text_autofit(draw, text: str, box: dict, overflow_log: list, field_key: str, max_size=MAX_FONT_SIZE):
    """מצייר טקסט בתוך תיבה נתונה עם התאמת גודל אוטומטית, ורושם overflow אם רלוונטי."""
    text = str(text or "")
    if not text:
        return
    font, overflowed = fit_font_to_box(text, box["width"], box["height"], max_size=max_size)
    draw.text((box["x"], box["y"]), text, fill="black", font=font)
    if overflowed:
        overflow_log.append({
            "field": field_key,
            "text": text,
            "reason": "הטקסט ארוך מדי עבור התיבה גם בגודל הגופן המינימלי",
        })


def draw_grid_cells_autofit(draw, text: str, box: dict, num_chars: int, overflow_log: list, field_key: str, manual_step_x: int = None):
    """מדפיס ספרות/אותיות במשבצות. רוחב המשבצת מחושב אוטומטית מ-width/num_chars,
    אלא אם סופק step_x ידני. בודק overflow אם המספר שהוזן ארוך מ-num_chars."""
    text = str(text or "")
    if not text:
        return
    step_x = manual_step_x or (box["width"] / max(num_chars, 1))
    font_size = min(MAX_FONT_SIZE, max(MIN_FONT_SIZE, int(step_x * 0.75)))
    font = load_font(font_size)

    if len(text) > num_chars:
        overflow_log.append({
            "field": field_key,
            "text": text,
            "reason": f"הוזנו {len(text)} תווים אך התיבה מוגדרת ל-{num_chars} משבצות בלבד",
        })

    current_x = box["x"]
    for char in text[:num_chars] if len(text) > num_chars else text:
        draw.text((current_x, box["y"]), char, fill="black", font=font)
        current_x += step_x


def draw_checkbox(draw, is_checked: bool, box: dict):
    if is_checked or str(is_checked).lower() == "true":
        font = load_font(min(CHECKBOX_FONT_SIZE, max(box["width"], box["height"])))
        draw.text((box["x"], box["y"]), "X", fill="black", font=font)


def to_ddmmyy_digits(iso_date: str, is_8_digits: bool = False) -> str:
    """מעבד תאריך. אם הקואורדינטה דורשת 8 ספרות (YYYY), מחזיר בהתאם, אחרת 6 ספרות (YY)"""
    if not iso_date:
        return ""
    try:
        year, month, day = iso_date.split("-")
        return f"{day}{month}{year}" if is_8_digits else f"{day}{month}{year[2:]}"
    except Exception:
        return ""


def _box(coords: dict, key: str) -> dict:
    b = coords.get(key) or DEFAULT_FIELD_COORDINATES.get(key) or {"x": 0, "y": 0, "width": 200, "height": 40}
    # השלמת ברירות מחדל אם חסרים width/height (למשל כיול ישן שנשמר לפני השדרוג)
    return {
        "x": b.get("x", 0), "y": b.get("y", 0),
        "width": b.get("width", 200), "height": b.get("height", 40),
        "num_chars": b.get("num_chars"), "step_x": b.get("step_x"),
    }


def generate_101_pdf(form_data: dict, signature_base64: str = None, coordinates: dict = None):
    """
    מחזיר (pdf_path, overflow_warnings). overflow_warnings היא רשימת אזהרות (יכולה להיות ריקה)
    על שדות שהטקסט בהם לא נכנס בשלמותו לתיבה המוגדרת - נבדק *לפני* סיום ההפקה.
    """
    if not os.path.exists("form101_page1.jpg") or not os.path.exists("form101_page2.jpg"):
        raise FileNotFoundError("Missing template images ('form101_page1.jpg', 'form101_page2.jpg') in root directory.")

    coords = dict(DEFAULT_FIELD_COORDINATES)
    if coordinates:
        coords.update(coordinates)

    overflow_log = []

    page1 = Image.open("form101_page1.jpg").convert('RGB')
    page2 = Image.open("form101_page2.jpg").convert('RGB')
    draw = ImageDraw.Draw(page1)

    # === שנת המס (עודכן ל-Grid ע"ב ה-JSON) ===
    b_tax = _box(coords, "tax_year")
    draw_grid_cells_autofit(draw, form_data.get("tax_year", ""), b_tax, b_tax["num_chars"] or 4, overflow_log, "tax_year", b_tax.get("step_x"))

    # === חלק א' - פרטי המעסיק ===
    draw_text_autofit(draw, form_data.get("employer_name", ""), _box(coords, "employer_name"), overflow_log, "employer_name")

    tik_value = str(form_data.get("employer_tik_nikuyim", ""))
    tik_remaining = tik_value[1:] if tik_value.startswith("9") else tik_value
    b = _box(coords, "employer_tik_nikuyim")
    draw_grid_cells_autofit(draw, tik_remaining, b, b["num_chars"] or 8, overflow_log, "employer_tik_nikuyim", b.get("step_x"))

    # === חלק ב' - פרטי העובד/ת ===
    b = _box(coords, "tz")
    draw_grid_cells_autofit(draw, form_data.get("tz", ""), b, b["num_chars"] or 9, overflow_log, "tz", b.get("step_x"))
    draw_text_autofit(draw, form_data.get("last_name", ""), _box(coords, "last_name"), overflow_log, "last_name")
    draw_text_autofit(draw, form_data.get("first_name", ""), _box(coords, "first_name"), overflow_log, "first_name")
    
    b_birth = _box(coords, "birth_date")
    draw_grid_cells_autofit(draw, to_ddmmyy_digits(form_data.get("birth_date", ""), b_birth["num_chars"] == 8), b_birth, b_birth["num_chars"] or 6, overflow_log, "birth_date", b_birth.get("step_x"))
    
    b_aliyah = _box(coords, "aliyah_date")
    draw_grid_cells_autofit(draw, to_ddmmyy_digits(form_data.get("aliyah_date", ""), b_aliyah["num_chars"] == 8), b_aliyah, b_aliyah["num_chars"] or 6, overflow_log, "aliyah_date", b_aliyah.get("step_x"))

    sex_box = _box(coords, "sex_male") if form_data.get("sex") == "זכר" else _box(coords, "sex_female")
    draw_checkbox(draw, True, sex_box)

    # חילוץ רחוב ומספר בית מתוך השדה המשולב
    address = str(form_data.get("address_street", ""))
    match = re.search(r'([^\d]+)\s*(\d+)?', address)
    street = match.group(1).strip() if match else address
    house_num = match.group(2) if match and match.group(2) else ""

    draw_text_autofit(draw, street, _box(coords, "address_street"), overflow_log, "address_street")
    draw_text_autofit(draw, house_num, _box(coords, "address_house_num"), overflow_log, "address_house_num")
    draw_text_autofit(draw, form_data.get("address_city", ""), _box(coords, "address_city"), overflow_log, "address_city")
    draw_text_autofit(draw, form_data.get("address_zip", "") or "", _box(coords, "address_zip"), overflow_log, "address_zip")

    full_mobile = f"{form_data.get('mobile_prefix', '')}-{form_data.get('mobile_number', '')}"
    draw_text_autofit(draw, full_mobile, _box(coords, "mobile"), overflow_log, "mobile")
    draw_text_autofit(draw, form_data.get("email", ""), _box(coords, "email"), overflow_log, "email")

    draw_text_autofit(draw, form_data.get("kupat_holim_name", ""), _box(coords, "kupat_holim_name"), overflow_log, "kupat_holim_name")

    is_resident = str(form_data.get("is_israeli_resident")).lower() == "true"
    draw_checkbox(draw, is_resident, _box(coords, "resident_yes"))
    draw_checkbox(draw, not is_resident, _box(coords, "resident_no"))

    if form_data.get("has_spouse") or form_data.get("marital_status") == "נשוי/ה":
        draw_checkbox(draw, True, _box(coords, "marital_married"))
    else:
        draw_checkbox(draw, True, _box(coords, "marital_single"))

    # === חלק ג' - פרטי בן/בת הזוג ===
    if form_data.get("has_spouse") or form_data.get("marital_status") == "נשוי/ה":
        b = _box(coords, "spouse_tz")
        draw_grid_cells_autofit(draw, form_data.get("spouse_tz", ""), b, b["num_chars"] or 9, overflow_log, "spouse_tz", b.get("step_x"))
        draw_text_autofit(draw, form_data.get("spouse_last_name", ""), _box(coords, "spouse_last_name"), overflow_log, "spouse_last_name")
        draw_text_autofit(draw, form_data.get("spouse_first_name", ""), _box(coords, "spouse_first_name"), overflow_log, "spouse_first_name")
        
        b = _box(coords, "spouse_birth_date")
        draw_grid_cells_autofit(draw, to_ddmmyy_digits(form_data.get("spouse_birth_date", ""), b["num_chars"] == 8), b, b["num_chars"] or 6, overflow_log, "spouse_birth_date", b.get("step_x"))
        
        b = _box(coords, "spouse_aliyah_date")
        draw_grid_cells_autofit(draw, to_ddmmyy_digits(form_data.get("spouse_aliyah_date", ""), b["num_chars"] == 8), b, b["num_chars"] or 6, overflow_log, "spouse_aliyah_date", b.get("step_x"))

        spouse_income = form_data.get("spouse_has_income")
        if spouse_income == "אין לו/לה הכנסה":
            draw_checkbox(draw, True, _box(coords, "spouse_income_none"))
        else:
            draw_checkbox(draw, True, _box(coords, "spouse_income_has"))

    # === חלק ד' - פרטי ילדים ===
    children_raw = form_data.get("children_json", form_data.get("children_data", "[]"))
    try:
        children_list = json.loads(children_raw) if isinstance(children_raw, str) else children_raw
    except Exception:
        children_list = []

    name_box_base = _box(coords, "child_name")
    tz_box_base = _box(coords, "child_tz")
    dob_box_base = _box(coords, "child_dob")
    row_height = _box(coords, "child_row_height")["y"] or 55

    for index, child in enumerate(children_list[:5]):
        offset = index * row_height
        name_box = dict(name_box_base, y=name_box_base["y"] + offset)
        tz_box = dict(tz_box_base, y=tz_box_base["y"] + offset)
        dob_box = dict(dob_box_base, y=dob_box_base["y"] + offset)

        draw_text_autofit(draw, child.get("name", ""), name_box, overflow_log, f"child_name[{index}]")
        draw_grid_cells_autofit(draw, child.get("tz", ""), tz_box, tz_box_base["num_chars"] or 9, overflow_log, f"child_tz[{index}]", tz_box_base.get("step_x"))
        draw_grid_cells_autofit(draw, to_ddmmyy_digits(child.get("dob", ""), dob_box["num_chars"] == 8), dob_box, dob_box_base["num_chars"] or 6, overflow_log, f"child_dob[{index}]", dob_box_base.get("step_x"))

    # === חלק ה'/ו' - הכנסות נוספות ותיאום מס ===
    draw_checkbox(draw, form_data.get("no_other_income", False), _box(coords, "no_other_income"))
    draw_checkbox(draw, form_data.get("has_other_income_salary", False), _box(coords, "other_income_salary"))
    draw_checkbox(draw, form_data.get("has_other_income_pension", False), _box(coords, "other_income_pension"))
    draw_checkbox(draw, form_data.get("has_other_income_allowance", False), _box(coords, "other_income_allowance"))
    draw_checkbox(draw, form_data.get("has_other_income_partial", False), _box(coords, "other_income_partial"))

    if form_data.get("tax_credit_request") == "here":
        draw_checkbox(draw, True, _box(coords, "credit_here"))
    else:
        draw_checkbox(draw, True, _box(coords, "credit_nothere"))

    draw_checkbox(draw, form_data.get("has_tax_coordination_approval", False), _box(coords, "tax_coordination_approval"))

    # === חלק ז' - עילות לבקשת פטור/זיכוי ===
    credit_field_names = [
        "credit_disabled_blind", "credit_resident_locality", "credit_single_parent",
        "credit_children_in_custody", "credit_children_not_in_custody", "credit_single_parent_toddlers",
        "credit_children_disabled", "credit_alimony_ex_spouse", "credit_academic_degree",
        "credit_reserve_duty", "credit_new_immigrant",
    ]
    for field_name in credit_field_names:
        draw_checkbox(draw, form_data.get(field_name, False), _box(coords, field_name))

    if form_data.get("credit_resident_locality") and form_data.get("locality_name"):
        draw_text_autofit(draw, form_data.get("locality_name", ""), _box(coords, "locality_name"), overflow_log, "locality_name")

    # === חלק ח' - הצהרה וחתימה ===
    draw_checkbox(draw, form_data.get("declared_true", False), _box(coords, "declared_true"))

    if signature_base64 and "," in signature_base64:
        try:
            header, encoded = signature_base64.split(",", 1)
            sig_data = base64.b64decode(encoded)
            sig_img = Image.open(BytesIO(sig_data)).convert("RGBA")
            sig_box = _box(coords, "signature")
            # Auto-Fit לחתימה: מקטינים תוך שמירת יחס הממדים כדי להיכנס בדיוק לתיבה שהוגדרה
            sig_img.thumbnail((sig_box["width"], sig_box["height"]))
            page1.paste(sig_img, (sig_box["x"], sig_box["y"]), sig_img)
        except Exception:
            pass

    os.makedirs("generated_pdfs", exist_ok=True)
    pdf_filename = f"generated_pdfs/101_{form_data.get('tz', 'unknown')}.pdf"
    page1.save(pdf_filename, save_all=True, append_images=[page2])

    return pdf_filename, overflow_log


def generate_101_pdf_with_debug_boxes(form_data: dict, signature_base64: str, coordinates: dict):
    """
    גרסה לעורך הכיול בלבד: מפיקה PDF זהה, אך מציירת גם מסגרת דקה סביב כל תיבה -
    ירוקה אם הטקסט נכנס בשלמותו, אדומה אם יש overflow - כדי לאתר מיד שדות שצריך להגדיל.
    """
    pdf_path, overflow_log = generate_101_pdf(form_data, signature_base64, coordinates)
    overflow_fields = {o["field"] for o in overflow_log}

    # מציירים מסגרות ישירות על עמוד 1 של ה-PDF שנוצר
    page1 = Image.open("form101_page1.jpg").convert('RGB')
    draw = ImageDraw.Draw(page1)
    coords = dict(DEFAULT_FIELD_COORDINATES)
    if coordinates:
        coords.update(coordinates)

    for key, box in coords.items():
        if key == "child_row_height" or "width" not in box:
            continue
        color = (220, 53, 69) if key in overflow_fields else (25, 135, 84)
        draw.rectangle(
            [box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"]],
            outline=color, width=3
        )

    page2 = Image.open("form101_page2.jpg").convert('RGB')
    debug_pdf_path = pdf_path.replace(".pdf", "_debug.pdf")
    page1.save(debug_pdf_path, save_all=True, append_images=[page2])
    return debug_pdf_path, overflow_log
