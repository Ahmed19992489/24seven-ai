import time
import re
import os
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
        إعدادات المتصفح المتوافقة مع Render (نفس إعدادات الخرائط الناجحة)
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless=new") 
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        
        # User-Agent قوي للتمويه
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

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

    def _search_bing_selenium(self, company_name):
        """
        Flow 2: البحث باستخدام Bing عبر Selenium (الأكثر استقراراً على السيرفر)
        """
        print(f"🔎 [Flow 2] Searching Bing for: {company_name}...")
        try:
            # استخدام Bing بدلاً من Google لتجنب الكابتشا
            query = f"{company_name} Egypt official website facebook"
            self.driver.get("https://www.bing.com")
            
            # انتظار صندوق البحث
            wait = WebDriverWait(self.driver, 10)
            search_box = wait.until(EC.presence_of_element_located((By.NAME, "q")))
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)
            
            time.sleep(2) # انتظار تحميل النتائج

            # Bing Results Selector (li.b_algo h2 a)
            results = self.driver.find_elements(By.CSS_SELECTOR, "li.b_algo h2 a")
            
            for res in results[:3]:
                url = res.get_attribute("href")
                # استبعاد روابط ميكروسوفت وبنج
                if url and "microsoft" not in url and "bing" not in url:
                    print(f"🔗 Found via Bing: {url}")
                    return url
                    
        except Exception as e:
            print(f"⚠️ Bing Search Error: {e}")
            
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
            # Flow 1 & 2: التحقق من الرابط أو البحث عنه
            # ---------------------------------------------------------
            target_website = website

            # إذا لم يوجد موقع، نستخدم Flow 2 (بحث Bing)
            if not target_website or "غير" in target_website or "google" in target_website:
                target_website = self._search_bing_selenium(company_name)
            
            if not target_website:
                print(f"❌ Flow 2 Failed: No website found for {company_name}")
                return data 

            # ---------------------------------------------------------
            # Flow 3: زيارة الموقع واستخراج البيانات
            # ---------------------------------------------------------
            print(f"🕵️ Deep Scan: Visiting {target_website}")
            self.driver.set_page_load_timeout(25)
            
            try:
                self.driver.get(target_website)
                time.sleep(3)
            except:
                print(f"⚠️ Timeout accessing {target_website}")
                pass

            page_source = self.driver.page_source
            
            # استخراج الإيميلات
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_source)
            bad_ext = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js', '.webp', '.mp4')
            valid_emails = list(set([e for e in emails if not e.lower().endswith(bad_ext)]))

            if valid_emails:
                priority = ['info', 'contact', 'sales', 'hello', 'admin', 'support']
                preferred = None
                for p in priority:
                    for e in valid_emails:
                        if p in e:
                            preferred = e
                            break
                    if preferred: break
                
                data['email'] = preferred if preferred else valid_emails[0]
                print(f"✅ Email Found: {data['email']}")

            # محاولة صفحة Contact Us
            if data['email'] == "غير متوفر":
                try:
                    xpath = "//a[contains(@href, 'contact') or contains(@href, 'Contact') or contains(text(), 'Contact') or contains(text(), 'اتصل')]"
                    contact_links = self.driver.find_elements(By.XPATH, xpath)
                    
                    if contact_links:
                        c_url = contact_links[0].get_attribute("href")
                        if c_url and c_url != self.driver.current_url:
                            self.driver.get(c_url)
                            time.sleep(2)
                            src = self.driver.page_source
                            new_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', src)
                            valid_new = [e for e in new_emails if not e.lower().endswith(bad_ext)]
                            if valid_new:
                                data['email'] = valid_new[0]
                                print(f"✅ Email Found in Contact Page: {valid_new[0]}")
                except: pass

        except Exception as e:
            print(f"⚠️ Enrichment Error for {company_name}: {e}")
        
        return data