import time
import re
import os
from urllib.parse import unquote
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
        chrome_options = Options()
        # إعدادات التخفي الأساسية
        chrome_options.add_argument("--headless=new") 
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        
        # خداع المواقع بأننا مستخدم عادي
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # مسارات Render
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

    def _search_engine_fallback(self, company_name):
        """
        Flow 2 (DuckDuckGo): استخدام محرك بحث بديل لتجنب حظر جوجل
        """
        print(f"🦆 [Flow 2] Searching DuckDuckGo for: {company_name}...")
        try:
            # نستخدم النسخة HTML لأنها أخف وأسرع ولا تطلب جافاسكريبت معقد
            query = f"{company_name} Egypt official website facebook"
            self.driver.get(f"https://html.duckduckgo.com/html/?q={query}")
            
            # انتظار بسيط
            time.sleep(2)

            # سحب النتائج (Links with class 'result__a')
            results = self.driver.find_elements(By.CLASS_NAME, "result__a")
            
            for res in results[:4]: # فحص أول 4 نتائج
                try:
                    url = res.get_attribute("href")
                    # استبعاد روابط الإعلانات ومحركات البحث
                    if url and "duckduckgo" not in url and "google" not in url:
                        # فك تشفير الرابط إذا كان مشفراً من DuckDuckGo
                        if "uddg=" in url:
                            try:
                                url = unquote(url.split("uddg=")[1].split("&")[0])
                            except:
                                pass
                        
                        print(f"🔗 Found URL via DDG: {url}")
                        return url
                except:
                    continue
                    
        except Exception as e:
            print(f"⚠️ Search Engine Error: {e}")
            
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
            # Flow 1: فحص الرابط القادم من الخرائط
            # ---------------------------------------------------------
            target_website = website

            # تنظيف الرابط
            if not target_website or "غير" in target_website or target_website == "http://googleusercontent.com":
                target_website = None

            # ---------------------------------------------------------
            # Flow 2: إذا لم يوجد رابط، ابحث في DuckDuckGo
            # ---------------------------------------------------------
            if not target_website:
                target_website = self._search_engine_fallback(company_name)
            
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
                time.sleep(3) # انتظار تحميل الصفحة
            except:
                print(f"⚠️ Timeout accessing {target_website}")
                pass

            # 1. البحث عن إيميلات في الصفحة الرئيسية
            page_source = self.driver.page_source
            
            # Regex محدث يلتقط الإيميلات بدقة
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_source)
            
            # فلترة النتائج (استبعاد الصور والملفات)
            bad_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js', '.woff', '.mp4')
            valid_emails = [e for e in emails if not e.lower().endswith(bad_extensions)]
            valid_emails = list(set(valid_emails)) # إزالة التكرار

            if valid_emails:
                # ترتيب حسب الأهمية
                priority_list = ['info', 'contact', 'sales', 'support', 'hello', 'admin']
                preferred = None
                
                for p in priority_list:
                    for e in valid_emails:
                        if p in e:
                            preferred = e
                            break
                    if preferred: break
                
                if not preferred:
                    preferred = valid_emails[0]

                data['email'] = preferred
                print(f"✅ Email Found: {preferred}")

            # 2. محاولة ذكية: البحث عن صفحة "Contact Us" إذا لم نجد إيميل
            if data['email'] == "غير متوفر":
                try:
                    # البحث عن أي رابط يحتوي على Contact أو اتصل بنا
                    xpath_query = "//a[contains(@href, 'contact') or contains(@href, 'Contact') or contains(text(), 'Contact') or contains(text(), 'اتصل')]"
                    contact_links = self.driver.find_elements(By.XPATH, xpath_query)
                    
                    if contact_links:
                        contact_url = contact_links[0].get_attribute("href")
                        if contact_url and contact_url != self.driver.current_url:
                            print(f"➡️ Moving to Contact Page: {contact_url}")
                            self.driver.get(contact_url)
                            time.sleep(2)
                            
                            src = self.driver.page_source
                            new_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', src)
                            valid_new = [e for e in new_emails if not e.lower().endswith(bad_extensions)]
                            
                            if valid_new:
                                data['email'] = valid_new[0]
                                print(f"✅ Email Found in Contact Page: {valid_new[0]}")
                except:
                    pass

        except Exception as e:
            print(f"⚠️ Enrichment Error for {company_name}: {e}")
        
        return data