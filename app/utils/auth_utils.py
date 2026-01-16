from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional

# إعدادات التشفير (يستخدم مكتبة bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 🔴 إعدادات التوكن (يجب أن تتطابق مع auth.py)
SECRET_KEY = "YOUR_SECRET_KEY_HERE"  # تأكد أن هذا المفتاح قوي وسري
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # التوكن صالح لمدة أسبوع (لراحة المستخدم)

# --- دالة التحقق من صحة الباسورد ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# --- دالة تشفير الباسورد الجديد ---
def get_password_hash(password):
    return pwd_context.hash(password)

# --- دالة إنشاء التوكن (Access Token) ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt