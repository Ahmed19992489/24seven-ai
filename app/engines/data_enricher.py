import time
import re
import os
import platform
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class DataEnricher:
    def __init__(self):
        self.driver = None

    def _setup_driver(self):
        """
        إعدادات المتصفح المتوافقة مع سيرفر Render
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless=new") 
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        
        # إضافة User-Agent ليبدو كمتصفح حقيقي (يقلل الحظر من جوجل)
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # --- مسارات Render ---
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

    def _google_search_fallback(self, company_name):
        """
        Flow 2 (محدث): بحث ذكي ومتعدد المحاولات في جوجل
        """
        print(f"🌍 [Flow 2] Searching Google for: {company_name}...")
        try:
            # إضافة كلمة Egypt أو الموقع لزيادة الدقة
            query = f"{company_name} Egypt official website facebook"
            self.driver.get("https://www.google.com/search?q=" + query)
            
            # انتظار ذكي لظهور أي نتيجة (عناوين h3)
            wait = WebDriverWait(self.driver, 10)
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "h3")))
            except:
                print("⚠️ Google page loaded but no H3 tags found (Possible CAPTCHA).")
                return None

            # استراتيجية 1: البحث عن الروابط التي تحتوي على عناوين (الأدق)
            # XPath: هات لي كل رابط (a) بداخله عنوان (h3)
            results = self.driver.find_elements(By.XPATH, "//a[h3]")
            
            if not results:
                # استراتيجية 2 (احتياطية): البحث عن الروابط داخل كلاسات جوجل الشهيرة
                results = self.driver.find_elements(By.CSS_SELECTOR, "div.g a")

            for res in results[:4]: # فحص أول 4 نتائج
                try:
                    url = res.get_attribute("href")
                    # استبعاد روابط جوجل ويوتيوب والخرائط
                    if url and "google" not in url and "youtube" not in url and "maps" not in url:
                        print(f"🔗 Found URL via Google: {url}")
                        return url
                except:
                    continue
                    
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
            # Flow 1 & 2 Logic
            # ---------------------------------------------------------
            target_website = website

            # تنظيف الرابط إذا كان "غير متوفر" أو فارغ
            if not target_website or "غير" in target_website:
                # تفعيل Flow 2: البحث في جوجل
                target_website = self._google_search_fallback(company_name)
            
            if not target_website:
                print(f"❌ Flow 2 Failed: Could not find website for {company_name}")
                return data 

            # ---------------------------------------------------------
            # Flow 3: الدخول للرابط واستخراج البيانات
            # ---------------------------------------------------------
            print(f"🕵️ Deep Scan: Visiting {target_website}")
            self.driver.set_page_load_timeout(25)
            
            try:
                self.driver.get(target_website)
                # انتظار بسيط لتحميل الجافاسكريبت
                time.sleep(2)
            except:
                print(f"⚠️ Timeout/Error accessing {target_website}")
                # حتى لو فشل التحميل الكامل، نحاول قراءة ما تم تحميله
                pass

            # 1. البحث عن إيميلات في الصفحة الرئيسية
            page_source = self.driver.page_source
            # Regex قوي للإيميلات
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_source)
            
            # تنظيف النتائج (استبعاد ملفات الصور التي قد تشبه الإيميلات خطأً)
            valid_emails = [e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js'))]
            # إزالة التكرار
            valid_emails = list(set(valid_emails))

            if valid_emails:
                # خوارزمية اختيار أفضل إيميل
                keywords = ['info', 'contact', 'sales', 'hello', 'support', 'admin']
                preferred = None
                
                # هل يوجد إيميل يحتوي على كلمة مفتاحية؟
                for k in keywords:
                    for e in valid_emails:
                        if k in e:
                            preferred = e
                            break
                    if preferred: break
                
                # إذا لم نجد، نأخذ الأول
                if not preferred:
                    preferred = valid_emails[0]

                data['email'] = preferred
                print(f"✅ Email Found: {preferred}")

            # 2. محاولة ذكية: البحث عن صفحة "Contact Us" إذا لم نجد إيميل
            if data['email'] == "غير متوفر":
                try:
                    # البحث عن أي رابط يحتوي على كلمة Contact أو اتصل بنا
                    # XPath case-insensitive translate trick
                    contact_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'contact') or contains(text(), 'Contact') or contains(text(), 'اتصل')]")
                    
                    if contact_links:
                        # نأخذ أول رابط صالح
                        contact_url = contact_links[0].get_attribute("href")
                        if contact_url and contact_url != target_website:
                            print(f"➡️ Moving to Contact Page: {contact_url}")
                            self.driver.get(contact_url)
                            time.sleep(2)
                            
                            src = self.driver.page_source
                            new_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', src)
                            valid_new = [e for e in new_emails if not e.lower().endswith(('.png', '.jpg'))]
                            
                            if valid_new:
                                data['email'] = valid_new[0]
                                print(f"✅ Email Found in Contact Page: {valid_new[0]}")
                except Exception as ex:
                    print(f"⚠️ Contact page scan error: {ex}")

        except Exception as e:
            print(f"⚠️ Enrichment Error for {company_name}: {e}")
        
        return data