import time
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

class DataEnricher:
    def __init__(self):
        self.driver = None

    def _setup_driver(self):
        """
        إعدادات المتصفح المتوافقة مع سيرفر Render (ضروري جداً لكي يعمل البوت)
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless=new") 
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")

        # --- كشف المسارات على سيرفر Render ---
        chrome_bin = os.environ.get("CHROME_BIN")
        if chrome_bin:
            chrome_options.binary_location = chrome_bin
        
        driver_path = os.environ.get("CHROMEDRIVER_PATH")
        
        try:
            service = None
            if driver_path and os.path.exists(driver_path):
                 print(f"🔌 Enricher: Using Custom Driver at {driver_path}")
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

    def _google_search_fallback(self, company_name):
        """
        Flow 2: البحث في جوجل إذا فشلت الخرائط في جلب الموقع
        """
        print(f"🌍 [Flow 2] Google Search Fallback for: {company_name}...")
        try:
            # نبحث عن الموقع الرسمي أو فيسبوك
            query = f"{company_name} official website facebook contact"
            self.driver.get("https://www.google.com/search?q=" + query)
            
            # محاولة التقاط أول نتيجة حقيقية
            results = self.driver.find_elements(By.CSS_SELECTOR, "div.g a")
            for res in results[:3]: # نفحص أول 3 نتائج
                url = res.get_attribute("href")
                if url and "google" not in url and "youtube" not in url:
                    print(f"🔗 Found URL via Google: {url}")
                    return url
        except Exception as e:
            print(f"⚠️ Google Search Error: {e}")
        return None

    def find_emails_and_people(self, company_name, website):
        """
        المحرك الذكي: يطبق الـ 3 Flows لاستخراج الداتا
        """
        data = {
            "email": "غير متوفر",
            "decision_maker_name": "",
            "decision_maker_role": "",
            "linkedin_url": ""
        }

        try:
            if not self.driver:
                self.start_session()

            # ---------------------------------------------------------
            # Flow 1 & 2 Logic: التحقق من الموقع أو البحث عنه
            # ---------------------------------------------------------
            target_website = website

            if not target_website or target_website == "غير متوفر":
                # تفعيل Flow 2: البحث في جوجل
                target_website = self._google_search_fallback(company_name)
            
            if not target_website:
                print("❌ Flow 2 Failed: No website found on Google.")
                return data # لا يمكن الإكمال لـ Flow 3 بدون رابط

            # ---------------------------------------------------------
            # Flow 3: الدخول للرابط واستخراج البيانات (Deep Scan)
            # ---------------------------------------------------------
            print(f"🕵️ Enriching via: {target_website}")
            self.driver.set_page_load_timeout(20)
            
            try:
                self.driver.get(target_website)
            except:
                print(f"⚠️ Timeout accessing {target_website}")
                return data

            # 1. البحث عن إيميلات في الصفحة الرئيسية
            page_source = self.driver.page_source
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_source)
            
            # تنظيف النتائج
            valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.js', '.css', '.svg'))]
            
            if valid_emails:
                # اختيار الإيميل الأفضل (info, contact, sales)
                preferred = next((e for e in valid_emails if any(x in e for x in ['info', 'contact', 'sales', 'hello'])), valid_emails[0])
                data['email'] = preferred
                print(f"✅ Email Found: {preferred}")

            # 2. محاولة ذكية: البحث عن صفحة "Contact Us" إذا لم نجد إيميل
            if data['email'] == "غير متوفر":
                try:
                    # البحث عن أي رابط يحتوي على كلمة Contact
                    contact_links = self.driver.find_elements(By.XPATH, "//a[contains(translate(text(), 'C', 'c'), 'contact')]")
                    if contact_links:
                        contact_url = contact_links[0].get_attribute("href")
                        if contact_url:
                            self.driver.get(contact_url)
                            # بحث مرة أخرى في صفحة الاتصال
                            src = self.driver.page_source
                            new_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', src)
                            valid_new = [e for e in new_emails if not e.endswith(('.png', '.jpg'))]
                            if valid_new:
                                data['email'] = valid_new[0]
                                print(f"✅ Email Found in Contact Page: {valid_new[0]}")
                except:
                    pass

        except Exception as e:
            print(f"⚠️ Enrichment Error for {company_name}: {e}")
        
        return data