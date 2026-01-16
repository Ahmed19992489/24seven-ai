import dns.resolver
from email_validator import validate_email
import pandas as pd

class EmailVerifier:
    def __init__(self):
        # إعدادات الـ DNS الدوارة (Rotating DNS) لمنع الحجب
        self.resolver = dns.resolver.Resolver()
        self.resolver.nameservers = ['1.1.1.1', '8.8.8.8', '9.9.9.9'] # Cloudflare, Google, Quad9
        self.resolver.timeout = 5
        self.resolver.lifetime = 5

    def check_mx_record(self, email):
        """فحص وجود سيرفر إيميل حقيقي"""
        try:
            domain = str(email).split('@')[1]
            records = self.resolver.resolve(domain, 'MX')
            return True if records else False
        except:
            return False

    def verify(self, email):
        """
        الدالة الرئيسية: تعيد (الحالة، نسبة الثقة)
        """
        # 1. تنظيف أولي
        email_str = str(email).strip().lower()
        if not email or "غير متوفر" in email_str or "@" not in email_str:
            return "Missing", 0.0

        try:
            # 2. التحقق الهيكلي (Syntax)
            valid = validate_email(email_str, check_deliverability=False)
            clean_email = valid.email
            
            # 3. التحقق التقني (DNS MX)
            has_mx = self.check_mx_record(clean_email)
            
            if has_mx:
                return "Valid", 100.0
            else:
                return "Risky (No MX)", 30.0
                
        except Exception:
            return "Invalid", 0.0