from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

# --- جدول المستخدمين (العملاء) ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    company_name = Column(String)
    job_title = Column(String) 
    
    credits = Column(Integer, default=50) 
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # العلاقات
    leads = relationship("Lead", back_populates="owner")
    searches = relationship("SearchHistory", back_populates="user")
    payments = relationship("PaymentRequest", back_populates="owner")
    
    # ✅ (1) هنا سمينا العلاقة "messages"
    messages = relationship("ChatMessage", back_populates="user")

# --- جدول البيانات المستخرجة (Leads) ---
class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    company_name = Column(String, index=True)
    industry = Column(String, nullable=True)
    location = Column(String)
    phone = Column(String)
    website = Column(String)
    
    email = Column(String, index=True)
    email_status = Column(String) 
    confidence_score = Column(Float) 
    
    decision_maker_name = Column(String, nullable=True)
    decision_maker_role = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)

    is_contacted = Column(Boolean, default=False) 
    last_contact_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    owner = relationship("User", back_populates="leads")

# --- جدول سجل البحث ---
class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    keyword = Column(String)
    location = Column(String)
    results_count = Column(Integer)
    search_date = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="searches")

# --- جدول طلبات الدفع والصور ---
class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer) 
    tokens_requested = Column(Integer) 
    proof_image = Column(String) 
    status = Column(String, default="Pending") 
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="payments")

# --- جدول نظام الدعم الفني (Chat) ---
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id")) 
    
    message = Column(Text) 
    sender = Column(String) 
    
    is_read = Column(Boolean, default=False) 
    created_at = Column(DateTime, default=datetime.utcnow)

    # ✅ (2) تم التصحيح: يجب أن يشير back_populates إلى "messages" الموجودة في User
    user = relationship("User", back_populates="messages")

# --- جدول المصروفات التشغيلية ---
class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, index=True) 
    amount = Column(Float)             
    created_at = Column(DateTime, default=datetime.utcnow)

    # --- جدول الكوبونات (الجديد) ---
class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True) # كود الكوبون (مثلا SALE2026)
    value = Column(Integer) # قيمته بالتوكن
    is_active = Column(Boolean, default=True) # هل هو صالح للاستخدام؟
    created_at = Column(DateTime, default=datetime.utcnow)