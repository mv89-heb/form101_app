# validators.py
"""
פונקציות ולידציה משותפות לשרת - טופס 101.
כולל בדיקת ספרת ביקורת אמיתית למספר זהות ישראלי, בדיקות תאריכים,
וזיהוי כפילויות/סתירות בין שדות הטופס.
"""
from datetime import datetime, date


def validate_israeli_id(id_number: str) -> bool:
    """
    בדיקת תקינות מספר זהות ישראלי לפי אלגוריתם ספרת הביקורת הרשמי.
    מקבל מחרוזת של עד 9 ספרות (משלים אפסים משמאל במידת הצורך).
    """
    if not id_number:
        return False
    id_number = id_number.strip()
    if not id_number.isdigit():
        return False
    id_number = id_number.zfill(9)
    if len(id_number) != 9:
        return False

    total = 0
    for i, digit_char in enumerate(id_number):
        digit = int(digit_char)
        weight = 1 if i % 2 == 0 else 2
        val = digit * weight
        if val > 9:
            val -= 9
        total += val

    return total % 10 == 0


def validate_date_not_future(date_str: str) -> bool:
    """מוודא שתאריך נתון אינו בעתיד."""
    if not date_str:
        return True
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return d <= date.today()
    except ValueError:
        return False


def calculate_age(birth_date_str: str) -> int:
    """מחשב גיל נכון לשנה הנוכחית לפי תאריך לידה (YYYY-MM-DD)."""
    try:
        b = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return -1
    today = date.today()
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def find_id_duplicates(*ids: str) -> bool:
    """
    בודק אם יש כפילות בין מספרי זהות שהוזנו (למשל עובד ובן/בת זוגו,
    או עובד וילדיו). מתעלם ממחרוזות ריקות.
    """
    cleaned = [i.strip() for i in ids if i]
    return len(cleaned) != len(set(cleaned))
