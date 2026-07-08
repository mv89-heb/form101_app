# models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from datetime import datetime
import database


class FormCalibration(database.Base):
    """שומר את עדכוני הקואורדינטות שבוצעו דרך עורך הכיול (/calibrate).
    שורה יחידה (id=1) עם כל מפת הקואורדינטות כ-JSON, כדי שהכיול ישרוד גם רי-דיפלוי."""
    __tablename__ = "form_calibration_v1"

    id = Column(Integer, primary_key=True, index=True)
    coordinates_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EmployeeForm(database.Base):
    __tablename__ = "employee_forms_v4" 

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    pdf_path = Column(String, nullable=True)

    # חלק א' - פרטי המעסיק
    employer_name = Column(String)
    employer_tik_nikuyim = Column(String)
    tax_year = Column(String)

    # חלק ב' - פרטי העובד/ת
    tz = Column(String, index=True)
    last_name = Column(String)
    first_name = Column(String)
    birth_date = Column(String)
    aliyah_date = Column(String, nullable=True)
    sex = Column(String)
    address_street = Column(String)
    address_city = Column(String)
    address_zip = Column(String, nullable=True)
    mobile_prefix = Column(String)
    mobile_number = Column(String)
    email = Column(String)
    is_israeli_resident = Column(Boolean, default=True)
    kibbutz_member = Column(String, nullable=True)
    kupat_holim_name = Column(String)

    # חלק ג' - פרטים על בן/בת הזוג
    has_spouse = Column(Boolean, default=False)
    spouse_tz = Column(String, nullable=True)
    spouse_last_name = Column(String, nullable=True)
    spouse_first_name = Column(String, nullable=True)
    spouse_birth_date = Column(String, nullable=True)
    spouse_aliyah_date = Column(String, nullable=True)
    spouse_has_income = Column(String, nullable=True)

    # חלק ד' - פרטים על ילדיי 
    children_json = Column(Text, nullable=True)

    # חלק ה' - פרטים על הכנסות אחרות
    no_other_income = Column(Boolean, default=False)
    has_other_income_salary = Column(Boolean, default=False)
    has_other_income_pension = Column(Boolean, default=False)
    has_other_income_allowance = Column(Boolean, default=False)
    has_other_income_partial = Column(Boolean, default=False)
    
    # הבחירה מכפתורי הרדיו (here / not_here)
    tax_credit_request = Column(String, default="here")

    # חלק ו' - אישורים מצורפים
    has_tax_coordination_approval = Column(Boolean, default=False)

    # חלק ז' - בקשות לפטור או זיכוי ממס
    credit_disabled_blind = Column(Boolean, default=False)
    credit_resident_locality = Column(Boolean, default=False)
    locality_name = Column(String, nullable=True)
    locality_start_date = Column(String, nullable=True)
    credit_single_parent = Column(Boolean, default=False)
    credit_children_in_custody = Column(Boolean, default=False)
    credit_children_not_in_custody = Column(Boolean, default=False)
    credit_single_parent_toddlers = Column(Boolean, default=False)
    credit_children_disabled = Column(Boolean, default=False)
    credit_alimony_ex_spouse = Column(Boolean, default=False)
    credit_academic_degree = Column(Boolean, default=False)
    credit_reserve_duty = Column(Boolean, default=False)
    credit_new_immigrant = Column(Boolean, default=False)

    # חלק ח' - הצהרה וחתימה
    declared_true = Column(Boolean, default=False)
    signature_data = Column(Text, nullable=True)
