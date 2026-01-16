import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

# --- إعدادات السيرفر ---
# تأكد من صحة الإيميل والباسورد هنا
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "kreta20161@gmail.com"
SENDER_PASSWORD = "okuv bliw ckib stnq"
SENDER_NAME = "24Seven AI Team"

# --- دالة الترحيب بالعميل ---
def send_welcome_email(to_email: str, name: str):
    try:
        subject = "Welcome to 24Seven AI! 🚀"
        body = f"""
        <div style="direction: ltr; font-family: Arial, sans-serif;">
            <h2 style="color: #4f46e5;">Welcome, {name}!</h2>
            <p>Your account has been successfully created via Google Login.</p>
            <p>You can now start using the platform to extract leads.</p>
            <hr>
            <p style="color: #888;">24Seven AI Team</p>
        </div>
        """
        _send_mail(to_email, subject, body)
    except Exception as e:
        print(f"❌ Error sending welcome email: {e}")

# --- دالة تنبيه الأدمن ---
def send_admin_alert(new_user_email: str, new_user_name: str):
    try:
        subject = f"🔔 عميل جديد سجل: {new_user_name}"
        body = f"""
        <div style="direction: rtl; text-align: right; font-family: Arial, sans-serif;">
            <h2>عميل جديد انضم للمنصة 💰</h2>
            <p><b>الاسم:</b> {new_user_name}</p>
            <p><b>الإيميل:</b> {new_user_email}</p>
        </div>
        """
        # نرسل التنبيه لنفس إيميل المرسل (لك أنت)
        _send_mail(SENDER_EMAIL, subject, body)
    except Exception as e:
        print(f"❌ Error sending admin alert: {e}")

# --- دالة الإرسال الداخلية (Core) ---
def _send_mail(to, subject, body):
    msg = MIMEMultipart()
    
    # تنسيق اسم الراسل ليظهر بشكل احترافي
    msg["From"] = formataddr((SENDER_NAME, SENDER_EMAIL))
    
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to, msg.as_string())
        server.quit()
        print(f"✅ Email sent successfully to {to}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")