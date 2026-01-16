from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# --- التعريف الخاص بدخول جوجل (الذي يطلبه الخطأ حالياً) ---
class GoogleLogin(BaseModel):
    token: str

# --- تعريفات المستخدم ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    credits: int
    is_active: bool

    class Config:
        from_attributes = True

# --- تعريفات البيانات المستخرجة (Leads) ---
class LeadBase(BaseModel):
    company_name: str
    location: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    industry: Optional[str] = None

class Lead(LeadBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True