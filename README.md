# מערכת טופס 101 - PostgreSQL & PDF Generation

## הכנות ראשונות:
1. העתק את הקבצים `טופס 101.1.jpg` ו-`טופס 101.2.jpg` אל תוך תיקיית הפרויקט הנוכחית (התיקייה בה נמצא main.py).
2. עדכן את קובץ ה-`.env` עם מחרוזת החיבור (DATABASE_URL) שקיבלת מ-Neon.

## הרצה מקומית:
1. פתח מסוף בתיקייה וצור סביבה וירטואלית: `python -m venv venv`
2. הפעל אותה: `venv\Scripts\activate` (או ב-Mac/Linux: `source venv/bin/activate`)
3. התקן חבילות: `pip install -r requirements.txt`
4. הרץ את השרת: `uvicorn main:app --reload`
