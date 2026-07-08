# main.py
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uvicorn
import json
import os
import base64

import database
import models
from pdf_service import generate_101_pdf, generate_101_pdf_with_debug_boxes
from knowledge_base import KNOWLEDGE_BASE
from validators import validate_israeli_id, validate_date_not_future, find_id_duplicates
from field_coordinates import DEFAULT_FIELD_COORDINATES, FIELD_LABELS_FOR_EDITOR

# יצירת הטבלאות במסד הנתונים בענן (Neon)
database.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Smart Form 101 Enterprise System")
templates = Jinja2Templates(directory="templates")


def load_calibration(db: Session) -> dict:
    """טוען את מפת הקואורדינטות העדכנית ביותר מה-DB (אחרי כיול ידני), או ברירת מחדל אם אין."""
    record = db.query(models.FormCalibration).filter(models.FormCalibration.id == 1).first()
    if record:
        try:
            saved = json.loads(record.coordinates_json)
            merged = dict(DEFAULT_FIELD_COORDINATES)
            merged.update(saved)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_FIELD_COORDINATES)

@app.get("/")
async def get_form(request: Request):
    # שימוש במבנה העדכני של ה-TemplateResponse למניעת שגיאות טיפוס
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"request": request}
    )

@app.get("/api/knowledge-base/{section}")
async def get_kb_section(section: str):
    if section in KNOWLEDGE_BASE:
        return KNOWLEDGE_BASE[section]
    return {
        "title": "מידע כללי",
        "simple_explanation": "הסעיף המבוקש לא נמצא בבסיס הידע.",
        "why_asked": "-",
        "tax_impact": "-",
        "warning": "-",
        "official_link": "https://www.gov.il/he/departments/israel_tax_authority",
    }

@app.get("/calibrate")
async def calibration_editor(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="calibrate.html",
        context={"request": request, "fields": FIELD_LABELS_FOR_EDITOR}
    )


@app.get("/calibrate/template-image")
async def calibration_template_image():
    """מגיש את תמונת הטופס הריקה כרקע לעורך הכיול."""
    safe_path = os.path.abspath("form101_page1.jpg")
    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="תבנית הטופס לא נמצאה בשרת.")
    return FileResponse(safe_path, media_type="image/jpeg")


@app.get("/api/calibration")
async def get_calibration(db: Session = Depends(database.get_db)):
    """מחזיר את מפת הקואורדינטות הנוכחית (מכוילת אם קיימת, אחרת ברירת מחדל)."""
    return load_calibration(db)


@app.post("/api/calibration")
async def save_calibration(request: Request, db: Session = Depends(database.get_db)):
    """שומר מפת קואורדינטות חדשה שנערכה דרך עורך הכיול. שורה יחידה (id=1) ב-DB."""
    try:
        new_coords = await request.json()
    except Exception:
        return {"status": "error", "message": "פורמט הנתונים שנשלח אינו JSON תקין."}

    if not isinstance(new_coords, dict) or not new_coords:
        return {"status": "error", "message": "לא התקבלו קואורדינטות לשמירה."}

    # ולידציה בסיסית - כל ערך חייב להיות בגבולות סבירים של גודל התמונה (2480x3508)
    for key, val in new_coords.items():
        if not isinstance(val, dict) or "x" not in val or "y" not in val:
            return {"status": "error", "message": f"פורמט לא תקין עבור השדה {key}."}
        if not (0 <= val.get("x", 0) <= 2600) or not (0 <= val.get("y", 0) <= 3600):
            return {"status": "error", "message": f"ערך חורג מגבולות העמוד עבור השדה {key}."}

    record = db.query(models.FormCalibration).filter(models.FormCalibration.id == 1).first()
    if record:
        record.coordinates_json = json.dumps(new_coords, ensure_ascii=False)
    else:
        record = models.FormCalibration(id=1, coordinates_json=json.dumps(new_coords, ensure_ascii=False))
        db.add(record)
    db.commit()

    return {"status": "success", "message": "הקואורדינטות נשמרו בהצלחה."}


@app.post("/api/calibration/preview")
async def preview_calibration(request: Request, db: Session = Depends(database.get_db)):
    """מפיק PDF תצוגה מקדימה עם נתוני דמה ומסגרות דיבוג (ירוק=נכנס, אדום=overflow) לפי
    הקואורדינטות שנשלחו (עוד לפני שמירה), כדי לאפשר בדיקה חזותית מיידית."""
    try:
        new_coords = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="פורמט הנתונים אינו JSON תקין.")

    merged = dict(DEFAULT_FIELD_COORDINATES)
    merged.update(new_coords)

    sample_data = _sample_form_data()
    pdf_path, overflow_warnings = generate_101_pdf_with_debug_boxes(sample_data, None, coordinates=merged)
    response = FileResponse(pdf_path, media_type="application/pdf", filename="preview.pdf")
    # כותרות HTTP חייבות latin-1 - מקודדים את ה-JSON (שמכיל עברית) ב-base64 כדי להעביר אותו בבטחה
    warnings_json = json.dumps(overflow_warnings, ensure_ascii=False)
    response.headers["X-Overflow-Warnings-B64"] = base64.b64encode(warnings_json.encode("utf-8")).decode("ascii")
    return response


@app.post("/api/calibration/check-overflow")
async def check_overflow(request: Request):
    """בודק overflow בלבד (בלי להוריד PDF) - שימושי לבדיקה מהירה תוך כדי גרירת שדות."""
    try:
        new_coords = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="פורמט הנתונים אינו JSON תקין.")

    merged = dict(DEFAULT_FIELD_COORDINATES)
    merged.update(new_coords)
    sample_data = _sample_form_data()
    _, overflow_warnings = generate_101_pdf(sample_data, None, coordinates=merged)
    return {"overflow_warnings": overflow_warnings}


def _sample_form_data():
    return {
        "employer_name": "חברת בדיקה בעמ", "employer_tik_nikuyim": "912345678", "tax_year": "2026",
        "tz": "302810049", "last_name": "כהן", "first_name": "דוד", "birth_date": "1990-05-15",
        "aliyah_date": "2005-03-01", "sex": "זכר", "address_street": "הרצל 10", "address_city": "ירושלים",
        "address_zip": "9100000", "mobile_prefix": "050", "mobile_number": "1234567", "email": "david@example.com",
        "kupat_holim_name": "כללית", "is_israeli_resident": "true", "has_spouse": True, "spouse_tz": "203810049",
        "spouse_last_name": "כהן", "spouse_first_name": "רבקה", "spouse_birth_date": "1992-07-20",
        "spouse_aliyah_date": "2010-09-10", "spouse_has_income": "אין לו/לה הכנסה",
        "children_json": '[{"name":"יוסי","tz":"111111118","dob":"2015-01-01"}]',
        "no_other_income": True, "tax_credit_request": "here", "credit_children_in_custody": True,
        "credit_academic_degree": True, "declared_true": True,
    }


@app.post("/submit")
async def submit_form(
    request: Request,
    employer_name: str = Form(...),
    employer_tik_nikuyim: str = Form(...),
    tax_year: str = Form(...),
    tz: str = Form(...),
    last_name: str = Form(...),
    first_name: str = Form(...),
    birth_date: str = Form(...),
    aliyah_date: str = Form(None),
    sex: str = Form(...),
    address_street: str = Form(...),
    address_city: str = Form(...),
    address_zip: str = Form(None),
    mobile_number: str = Form(...),
    mobile_prefix: str = Form(...),
    email: str = Form(...),
    kupat_holim_name: str = Form(...),
    is_israeli_resident: str = Form("true"),
    kibbutz_member: str = Form("לא"),
    has_spouse: bool = Form(False),
    spouse_tz: str = Form(None),
    spouse_last_name: str = Form(None),
    spouse_first_name: str = Form(None),
    spouse_birth_date: str = Form(None),
    spouse_aliyah_date: str = Form(None),
    spouse_has_income: str = Form(None),
    children_data: str = Form("[]"),
    no_other_income: bool = Form(False),
    has_other_income_salary: bool = Form(False),
    has_other_income_pension: bool = Form(False),
    has_other_income_allowance: bool = Form(False),
    has_other_income_partial: bool = Form(False),
    tax_credit_request: str = Form("here"),
    has_tax_coordination_approval: bool = Form(False),
    credit_disabled_blind: bool = Form(False),
    credit_resident_locality: bool = Form(False),
    locality_name: str = Form(None),
    locality_start_date: str = Form(None),
    credit_single_parent: bool = Form(False),
    credit_children_in_custody: bool = Form(False),
    credit_children_not_in_custody: bool = Form(False),
    credit_single_parent_toddlers: bool = Form(False),
    credit_children_disabled: bool = Form(False),
    credit_alimony_ex_spouse: bool = Form(False),
    credit_academic_degree: bool = Form(False),
    credit_reserve_duty: bool = Form(False),
    credit_new_immigrant: bool = Form(False),
    declared_true: bool = Form(False),
    signature_data: str = Form(None),
    db: Session = Depends(database.get_db)
):
    # --- ולידציות שרת אמיתיות (לא רק תבנית regex) ---
    errors = []
    if not validate_israeli_id(tz):
        errors.append("מספר תעודת הזהות של העובד/ת אינו תקין (ספרת ביקורת שגויה).")
    if has_spouse and spouse_tz and not validate_israeli_id(spouse_tz):
        errors.append("מספר תעודת הזהות של בן/בת הזוג אינו תקין.")
    if not validate_date_not_future(birth_date):
        errors.append("תאריך הלידה אינו יכול להיות בעתיד.")
    if aliyah_date and not validate_date_not_future(aliyah_date):
        errors.append("תאריך העלייה אינו יכול להיות בעתיד.")

    try:
        children_check = json.loads(children_data) if children_data else []
        child_ids = [c.get("tz", "") for c in children_check if isinstance(c, dict)]
        for cid in child_ids:
            if cid and not validate_israeli_id(cid):
                errors.append(f"מספר הזהות של אחד הילדים ({cid}) אינו תקין.")
    except Exception:
        child_ids = []
        errors.append("פורמט נתוני הילדים אינו תקין.")

    if find_id_duplicates(tz, spouse_tz if has_spouse else None, *child_ids):
        errors.append("קיימת כפילות במספרי הזהות שהוזנו (עובד/ת, בן/בת זוג וילדים חייבים להיות שונים).")

    if not declared_true:
        errors.append("יש לאשר את ההצהרה בחלק ח' לפני שליחת הטופס.")

    if errors:
        return {"status": "error", "message": " | ".join(errors)}

    try:
        # 1. ריכוז כל השדות למילון מובנה עבור שירות ה-PDF
        form_fields = {
            "employer_name": employer_name,
            "employer_tik_nikuyim": employer_tik_nikuyim,
            "tax_year": tax_year,
            "tz": tz,
            "last_name": last_name,
            "first_name": first_name,
            "birth_date": birth_date,
            "aliyah_date": aliyah_date,
            "sex": sex,
            "address_street": address_street,
            "address_city": address_city,
            "address_zip": address_zip,
            "mobile_prefix": mobile_prefix,
            "mobile_number": mobile_number,
            "email": email,
            "kupat_holim_name": kupat_holim_name,
            "is_israeli_resident": is_israeli_resident,
            "kibbutz_member": kibbutz_member,
            "has_spouse": has_spouse,
            "spouse_tz": spouse_tz,
            "spouse_last_name": spouse_last_name,
            "spouse_first_name": spouse_first_name,
            "spouse_birth_date": spouse_birth_date,
            "spouse_aliyah_date": spouse_aliyah_date,
            "spouse_has_income": spouse_has_income,
            "children_json": children_data,  # מיפוי השדה למבנה הצפוי ב-pdf_service
            "no_other_income": no_other_income,
            "has_other_income_salary": has_other_income_salary,
            "has_other_income_pension": has_other_income_pension,
            "has_other_income_allowance": has_other_income_allowance,
            "has_other_income_partial": has_other_income_partial,
            "tax_credit_request": tax_credit_request,
            "has_tax_coordination_approval": has_tax_coordination_approval,
            "credit_disabled_blind": credit_disabled_blind,
            "credit_resident_locality": credit_resident_locality,
            "locality_name": locality_name,
            "locality_start_date": locality_start_date,
            "credit_single_parent": credit_single_parent,
            "credit_children_in_custody": credit_children_in_custody,
            "credit_children_not_in_custody": credit_children_not_in_custody,
            "credit_single_parent_toddlers": credit_single_parent_toddlers,
            "credit_children_disabled": credit_children_disabled,
            "credit_alimony_ex_spouse": credit_alimony_ex_spouse,
            "credit_academic_degree": credit_academic_degree,
            "credit_reserve_duty": credit_reserve_duty,
            "credit_new_immigrant": credit_new_immigrant,
            "declared_true": declared_true
        }

        # 2. הפקת קובץ ה-PDF המשולב עם נתוני המילון, החתימה הגרפית, וקואורדינטות מכוילות
        coords = load_calibration(db)
        pdf_file_path, overflow_warnings = generate_101_pdf(form_fields, signature_data, coordinates=coords)
        
        # 3. שמירת כל הנתונים בצורה מלאה ומסונכרנת למסד הנתונים בענן
        new_form = models.EmployeeForm(
            employer_name=employer_name,
            employer_tik_nikuyim=employer_tik_nikuyim,
            tax_year=tax_year,
            tz=tz,
            last_name=last_name,
            first_name=first_name,
            birth_date=birth_date,
            aliyah_date=aliyah_date,
            sex=sex,
            address_street=address_street,
            address_city=address_city,
            address_zip=address_zip,
            mobile_prefix=mobile_prefix,
            mobile_number=mobile_number,
            email=email,
            kupat_holim_name=kupat_holim_name,
            is_israeli_resident=(is_israeli_resident == "true"),
            kibbutz_member=kibbutz_member,
            has_spouse=has_spouse,
            spouse_tz=spouse_tz,
            spouse_last_name=spouse_last_name,
            spouse_first_name=spouse_first_name,
            spouse_birth_date=spouse_birth_date,
            spouse_aliyah_date=spouse_aliyah_date,
            spouse_has_income=spouse_has_income,
            children_json=children_data,
            no_other_income=no_other_income,
            has_other_income_salary=has_other_income_salary,
            has_other_income_pension=has_other_income_pension,
            has_other_income_allowance=has_other_income_allowance,
            has_other_income_partial=has_other_income_partial,
            tax_credit_request=tax_credit_request,
            has_tax_coordination_approval=has_tax_coordination_approval,
            credit_disabled_blind=credit_disabled_blind,
            credit_resident_locality=credit_resident_locality,
            locality_name=locality_name,
            locality_start_date=locality_start_date,
            credit_single_parent=credit_single_parent,
            credit_children_in_custody=credit_children_in_custody,
            credit_children_not_in_custody=credit_children_not_in_custody,
            credit_single_parent_toddlers=credit_single_parent_toddlers,
            credit_children_disabled=credit_children_disabled,
            credit_alimony_ex_spouse=credit_alimony_ex_spouse,
            credit_academic_degree=credit_academic_degree,
            credit_reserve_duty=credit_reserve_duty,
            credit_new_immigrant=credit_new_immigrant,
            declared_true=declared_true,
            signature_data=signature_data,
            pdf_path=pdf_file_path
        )
        
        db.add(new_form)
        db.commit()
        db.refresh(new_form)
        
        return {
            "status": "success", 
            "message": "הטופס נבדק, נחתם ונשמר בהצלחה במסד הנתונים ובתיקיית הקבצים המופקים!",
            "form_id": new_form.id,
            "download_url": f"/download/{new_form.id}",
            "overflow_warnings": overflow_warnings
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/download/{form_id}")
async def download_pdf(form_id: int, db: Session = Depends(database.get_db)):
    record = db.query(models.EmployeeForm).filter(models.EmployeeForm.id == form_id).first()
    if not record or not record.pdf_path:
        raise HTTPException(status_code=404, detail="הקובץ המבוקש לא נמצא.")

    # הגנה מפני path traversal - וידוא שהקובץ אכן נמצא בתוך תיקיית הפלט הצפויה
    safe_dir = os.path.abspath("generated_pdfs")
    safe_path = os.path.abspath(record.pdf_path)
    if not safe_path.startswith(safe_dir) or not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="הקובץ המבוקש לא נמצא בשרת.")

    filename = f"טופס_101_{record.first_name}_{record.last_name}.pdf"
    return FileResponse(safe_path, media_type="application/pdf", filename=filename)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
