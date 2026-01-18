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

class GmapsEngine:
    def __init__(self):
        self.driver = self._setup_driver()

    def _setup_driver(self):
        chrome_options = Options()
        
        # --- إعدادات السيرفر (Headless) ---
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")

        # --- تحديد المسارات يدوياً (الحل الجذري) ---
        # 1. مسار المتصفح
        chrome_bin = os.environ.get("CHROME_BIN")
        if chrome_bin:
            print(f"🖥️ Render Environment: Using Chrome at {chrome_bin}")
            chrome_options.binary_location = chrome_bin
        
        # 2. مسار الدرايفر (يتم تحديده بناءً على وجود المتغير)
        driver_path = os.environ.get("CHROMEDRIVER_PATH")
        
        try:
            service = None
            if driver_path and os.path.exists(driver_path):
                 print(f"🔌 Using Custom ChromeDriver at: {driver_path}")
                 service = Service(executable_path=driver_path)
            else:
                 print("⚠️ Driver path not found in env, trying default Service()...")
                 # محاولة التشغيل الافتراضي (للوكال هوست)
                 service = Service()

            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver

        except Exception as e:
            print(f"❌ خطأ قاتل في تشغيل المتصفح: {e}")
            raise e

    def scrape(self, keyword: str, location: str, max_leads: int = 10):
        results = []
        try:
            query = f"{keyword} in {location}"
            print(f"🚀 [Gmaps] Searching: {query}")
            
            self.driver.get(f"https://www.google.com/maps/search/{query}")
            
            wait = WebDriverWait(self.driver, 20)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']")))
            except:
                print("⚠️ واجهة النتائج لم تظهر بوضوح.")

            # --- سكرول بسيط ---
            scrollable_div = self.driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
            for _ in range(3): # عدد مرات سكرول محدود للتجربة
                self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
                time.sleep(2)

            company_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")
            print(f"🔍 Found {len(company_links)} leads.")

            for link in company_links[:max_leads]:
                try:
                    self.driver.execute_script("arguments[0].click();", link)
                    time.sleep(1.5)
                    
                    name = link.get_attribute("aria-label") or "Unknown"
                    page_html = self.driver.page_source
                    
                    # استخراج الأرقام
                    all_numbers = re.findall(r'(?:\+20|0)(?:1[0125]|2)\d{8}', page_html)
                    unique_numbers = list(set(all_numbers))
                    phone = " | ".join(unique_numbers) if unique_numbers else "غير متوفر"

                    results.append({
                        "company_name": name,
                        "industry": keyword,
                        "location": location,
                        "phone": phone,
                        "website": "غير متوفر"
                    })
                    print(f"✅ Saved: {name} | {phone}")

                except: continue
        
        except Exception as e:
            print(f"❌ Scraping Error: {e}")
        finally:
            try: self.driver.quit()
            except: pass
            
        return results