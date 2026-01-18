import time
import re
import os
import platform
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class DataEnricher:
    def __init__(self):
        self.driver = None

    def _setup_driver(self):
        """
        نفس إعدادات المتصفح المتوافقة مع Render
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless=new") 
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")

        # --- تحديد المسارات يدوياً (نفس منطق gmaps_collector) ---
        chrome_bin = os.environ.get("CHROME_BIN")
        if chrome_bin:
            chrome_options.binary_location = chrome_bin
        
        driver_path = os.environ.get("CHROMEDRIVER_PATH")
        
        try:
            service = None
            if driver_path and os.path.exists(driver_path):
                 service = Service(executable_path=driver_path)
            else:
                 service = Service()

            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver

        except Exception as e:
            print(f"❌ Enricher Driver Error: {e}")
            raise e

    def start_session(self):
        if not self.driver:
            self.driver = self._setup_driver()

    def stop_session(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def find_emails_and_people(self, company_name, website):
        """
        محرك بحث ذكي يحاول إيجاد الإيميل وصناع القرار
        """
        data = {
            "email": "غير متوفر",
            "decision_maker_name": "",
            "decision_maker_role": "",
            "linkedin_url": ""
        }

        # إذا لم يكن هناك موقع، لا داعي لتشغيل المتصفح
        if not website or website == "غير متوفر":
            return data

        try:
            if not self.driver:
                self.start_session()

            print(f"🕵️ Enriching: {company_name} ({website})")
            
            # 1. زيارة الموقع الرسمي
            self.driver.set_page_load_timeout(15)
            try:
                self.driver.get(website)
            except:
                print(f"⚠️ Timeout accessing {website}")
                return data

            # 2. البحث عن إيميلات داخل الصفحة (Regex)
            page_source = self.driver.page_source
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_source)
            
            # فلترة الإيميلات (استبعاد الصور والملفات)
            valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.css', '.js'))]
            
            if valid_emails:
                # نفضل الإيميلات التي تحتوي على info, contact, sales
                preferred = next((e for e in valid_emails if any(x in e for x in ['info', 'contact', 'hello', 'sales'])), valid_emails[0])
                data['email'] = preferred
                print(f"✅ Email Found: {preferred}")

            # 3. محاولة بسيطة للبحث عن صفحة "Contact Us"
            try:
                contact_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, "Contact")
                if contact_link:
                    contact_url = contact_link.get_attribute("href")
                    if contact_url:
                        self.driver.get(contact_url)
                        # بحث مرة أخرى في صفحة الاتصال
                        src = self.driver.page_source
                        new_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', src)
                        if new_emails and data['email'] == "غير متوفر":
                             valid_new = [e for e in new_emails if not e.endswith(('.png', '.jpg'))]
                             if valid_new:
                                data['email'] = valid_new[0]
            except:
                pass

        except Exception as e:
            print(f"⚠️ Enrichment Error for {company_name}: {e}")
        
        return data