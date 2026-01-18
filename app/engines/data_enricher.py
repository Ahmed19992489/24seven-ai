import time
import re
import os
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

class DataEnricher:
    def __init__(self):
        self.driver = None

    def _setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless=new") 
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        
        # User-Agent ليبدو كمتصفح حقيقي
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

    def _search_ddg(self, query):
        """ محاولة البحث عبر DuckDuckGo """
        print("🦆 Trying DuckDuckGo...")
        try:
            self.driver.get(f"https://html.duckduckgo.com/html/?q={query}")
            time.sleep(2)
            # استخدام XPath عام للبحث عن أي رابط نتيجة
            results = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'result')]//a[@class='result__a']")
            
            for res in results[:3]:
                url = res.get_attribute("href")
                if url and "duckduckgo" not in url:
                    if "uddg=" in url: # فك تشفير روابط DDG
                        try: url = unquote(url.split("uddg=")[1].split("&")[0])
                        except: pass
                    print(f"🔗 Found via DDG: {url}")
                    return url
        except Exception as e:
            print(f"⚠️ DDG Error: {e}")
        return None

    def _search_bing(self, query):
        """ محاولة البحث عبر Bing (الخطة البديلة) """
        print("🔎 Trying Bing...")
        try:
            self.driver.get(f"https://www.bing.com/search?q={query}")
            time.sleep(2)
            # Bing عادة يضع النتائج داخل h2 > a
            results = self.driver.find_elements(By.CSS_SELECTOR, "li.b_algo h2 a")
            
            for res in results[:3]:
                url = res.get_attribute("href")
                if url and "microsoft" not in url and "bing" not in url:
                    print(f"🔗 Found via Bing: {url}")
                    return url
        except Exception as e:
            print(f"⚠️ Bing Error: {e}")
        return None

    def _smart_search_fallback(self, company_name):
        """
        Flow 2: استراتيجية البحث المتعدد
        """
        query = f"{company_name} Egypt official website facebook"
        
        # 1. المحاولة الأولى: DuckDuckGo
        url = self._search_ddg(query)
        if url: return url
        
        # 2. المحاولة الثانية: Bing
        url = self._search_bing(query)
        if url: return url
        
        return None

    def find_emails_and_people(self, company_name, website):
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

            if not target_website or "غير" in target_website or "google" in target_website:
                # تفعيل البحث الذكي (Flow 2)
                target_website = self._smart_search_fallback(company_name)
            
            if not target_website:
                print(f"❌ Flow 2 Failed: Could not find website anywhere for {company_name}")
                return data 

            # ---------------------------------------------------------
            # Flow 3: زيارة الرابط
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
            bad_ext = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js', '.webp')
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
                    contact_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'contact') or contains(@href, 'Contact') or contains(text(), 'Contact') or contains(text(), 'اتصل')]")
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