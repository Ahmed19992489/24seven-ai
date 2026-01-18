import time
import re
import os
import platform
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class GmapsEngine:
    def __init__(self):
        self.driver = self._setup_driver()

    def _setup_driver(self):
        """
        إعداد المتصفح ليعمل بذكاء على السيرفر (Render) وعلى الجهاز الشخصي
        بدون استخدام undetected_chromedriver لتجنب مشاكل السيرفر
        """
        chrome_options = Options()
        
        # --- إعدادات السيرفر الأساسية ---
        chrome_options.add_argument("--headless=new") # تشغيل بدون شاشة
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false") # تسريع

        # --- كشف مسار كروم على Render ---
        chrome_bin = os.environ.get("CHROME_BIN")
        if chrome_bin:
            print(f"🖥️ Render Environment Detected. Using Chrome at: {chrome_bin}")
            chrome_options.binary_location = chrome_bin
        else:
            print("💻 Local Environment Detected.")

        try:
            # محاولة التشغيل القياسية
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver
        except Exception as e:
            print(f"⚠️ فشل التشغيل التلقائي، جاري المحاولة اليدوية... {e}")
            try:
                # محاولة احتياطية
                driver = webdriver.Chrome(options=chrome_options)
                return driver
            except Exception as final_e:
                print(f"❌ خطأ قاتل: لا يمكن تشغيل المتصفح! {final_e}")
                raise final_e

    def scrape(self, keyword: str, location: str, max_leads: int = 10):
        results = []
        try:
            query = f"{keyword} in {location}"
            print(f"🚀 [Gmaps] Searching: {query} (Target: {max_leads})")
            
            # استخدام رابط البحث المباشر
            self.driver.get(f"https://www.google.com/maps/search/{query}")
            
            wait = WebDriverWait(self.driver, 20)
            try:
                # انتظار ظهور قائمة النتائج (تغير السيلكتور حسب تحديثات جوجل)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']")))
            except:
                print("⚠️ واجهة النتائج لم تظهر، نحاول المتابعة...")

            # --- منطق التمرير (Scrolling Logic) ---
            print("📜 Scrolling to load leads...")
            
            # العثور على العنصر القابل للسكرول (غالباً هو الـ Feed)
            try:
                scrollable_div = self.driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
                
                last_count = 0
                retries = 0
                
                # حلقة السكرول
                while len(self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")) < max_leads:
                    self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
                    time.sleep(2) 
                    
                    current_count = len(self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']"))
                    
                    if current_count == last_count:
                        retries += 1
                        if retries >= 3: 
                            print("🏁 Reached end of available leads.")
                            break
                    else:
                        retries = 0
                        
                    last_count = current_count
                    print(f"⏳ Leads Loaded: {current_count}...")
                    
                    if current_count >= max_leads:
                        break
            except Exception as e:
                print(f"⚠️ Scrolling issue: {e}")

            # تجميع الروابط
            company_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")
            print(f"🔍 Total leads found: {len(company_links)}")

            # --- بداية استخراج البيانات ---
            for link in company_links[:max_leads]:
                try:
                    # النقر على العنصر لعرض التفاصيل
                    self.driver.execute_script("arguments[0].click();", link)
                    time.sleep(2) # انتظار تحميل التفاصيل
                    
                    # سحب الاسم
                    name = link.get_attribute("aria-label") or "Unknown"
                    
                    # سحب محتوى الصفحة بالكامل للبحث عن الأرقام
                    page_html = self.driver.page_source
                    
                    # ---------------------------------------------------------
                    # 🔥 منطق سحب الأرقام المتعددة (Regex)
                    # ---------------------------------------------------------
                    phone = "غير متوفر"
                    
                    # 1. البحث عن كل الأرقام (موبايل وأرضي مصري)
                    # هذا التعبير النمطي يبحث عن الأرقام التي تبدأ بـ +20 أو 0
                    all_numbers = re.findall(r'(?:\+20|0)(?:1[0125]|2)\d{8}', page_html)
                    
                    # 2. إزالة التكرار
                    unique_numbers = list(set(all_numbers))
                    
                    if unique_numbers:
                        # 3. ترتيب ذكي: الموبايل أولاً، ثم الأرضي
                        unique_numbers.sort(key=lambda x: 0 if x.startswith(('01', '+201')) else 1)
                        
                        # 4. دمج الأرقام بفاصل
                        phone = " | ".join(unique_numbers)
                    # ---------------------------------------------------------

                    # سحب الموقع الإلكتروني (محاولة)
                    website = "غير متوفر"
                    try:
                        web_elem = self.driver.find_element(By.CSS_SELECTOR, "a[data-item-id='authority']")
                        website = web_elem.get_attribute("href")
                    except:
                        pass

                    # إضافة النتيجة
                    results.append({
                        "company_name": name,
                        "industry": keyword,
                        "location": location,
                        "phone": phone, 
                        "website": website,
                        "map_link": link.get_attribute("href")
                    })
                    print(f"✅ Data Captured: {name} | 📞 {phone}")

                except Exception as inner_e:
                    print(f"⚠️ Error parsing item: {inner_e}")
                    continue
        
        except Exception as e:
            print(f"❌ Critical Gmaps Error: {e}")
            
        finally:
            # إغلاق المتصفح وتنظيف الذاكرة
            try:
                self.driver.quit()
            except:
                pass
            
        return results

# اختبار سريع عند التشغيل المباشر
if __name__ == "__main__":
    engine = GmapsEngine()
    data = engine.scrape("Gym", "Cairo", 3)
    print("Final Data:", data)