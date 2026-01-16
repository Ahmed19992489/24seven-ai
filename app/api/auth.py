from fastapi import APIRouter, Depends, HTTPException, status
from google.oauth2 import id_token
from google.auth.transport import requests
from sqlalchemy.orm import Session
from app import models, schemas, database
from datetime import datetime, timedelta
from jose import jwt
import os

router = APIRouter()

# تأكد أن هذا المفتاح هو الجديد الذي وضعته في dashboard.html
GOOGLE_CLIENT_ID = "625457191585-2g87nj1pq6g7ke79loijr9o1pobdmlu9.apps.googleusercontent.com"
SECRET_KEY = "your-very-secret-key"
ALGORITHM = "HS256"

@router.post("/google-login")
async def google_login(data: schemas.GoogleLogin, db: Session = Depends(database.get_db)):
    try:
        # 🔴 التعديل السحري: إضافة clock_skew للسماح بفارق الوقت بين الموبايل والسيرفر
        # وتجاهل التحقق من الرابط إذا كان التوكن قادماً من مفتاحك الصحيح
        idinfo = id_token.verify_oauth2_token(
            data.token, 
            requests.Request(), 
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=60 # يسمح بفارق دقيقة في التوقيت
        )

        email = idinfo['email']
        name = idinfo.get('name', email.split('@')[0])

        # البحث عن المستخدم أو إنشاؤه
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            user = models.User(
                email=email,
                full_name=name,
                credits=100 # رصيد مجاني للعميل الجديد
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # إنشاء توكن المنصة الخاص بنا
        access_token = create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}

    except ValueError as e:
        print(f"❌ Google Token Validation Error: {e}")
        # سنقوم بطباعة تفاصيل الخطأ في الـ CMD لنعرف السبب بدقة
        raise HTTPException(status_code=400, detail=f"Invalid Token: {str(e)}")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# دالة جلب المستخدم الحالي المستخدمة في الروابط الأخرى
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/google-login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user = db.query(models.User).filter(models.User.email == email).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.get("/me")
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return {
        "email": current_user.email,
        "full_name": current_user.full_name,
        "credits": current_user.credits
    }