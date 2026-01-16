import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re

class GmapsEngine:
    def scrape(self, keyword: str, location: str, max_leads: int = 10):
        options = uc.ChromeOptions()
        # options.add_argument('--headless') 
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--start-maximized')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        driver = uc.Chrome(options=options)
        results = []
        
        try:
            query = f"{keyword} in {location}"
            print(f"🚀 [Gmaps] Searching: {query} (Target: {max_leads})")
            
            driver.get(f"https://www.google.com/maps/search/{query}")
            
            wait = WebDriverWait(driver, 25)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed']")))
            except:
                print("⚠️ واجهة النتائج لم تظهر، نحاول المتابعة...")

            # --- منطق التمرير ---
            print("📜 Scrolling to load leads (Deep Mode)...")
            scrollable_div = driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
            
            last_count = 0
            retries = 0
            
            while len(driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")) < max_leads:
                driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
                time.sleep(2) 
                
                current_count = len(driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc"))
                
                if current_count == last_count:
                    retries += 1
                    if retries >= 3: 
                        print("🏁 Reached end of available leads.")
                        break
                else:
                    retries = 0
                    
                last_count = current_count
                if current_count % 20 == 0:
                    print(f"⏳ Progress: {current_count}/{max_leads} leads loaded...")

            company_links = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
            print(f"🔍 [Gmaps] Total leads found: {len(company_links)}")

            # --- بداية المعالجة ---
            for link in company_links[:max_leads]:
                try:
                    name = link.get_attribute("aria-label")
                    
                    driver.execute_script("arguments[0].click();", link)
                    time.sleep(2.5) 
                    
                    page_html = driver.page_source
                    
                    # ---------------------------------------------------------
                    # 🔥 التحديث: سحب جميع الأرقام (Multi-Number Extraction)
                    # ---------------------------------------------------------
                    phone = "غير متوفر"
                    
                    # 1. البحث عن كل الأرقام (موبايل وأرضي)
                    all_numbers = re.findall(r'(?:\+20|0)(?:1[0125]|2)\d{8}', page_html)
                    
                    # 2. إزالة التكرار
                    unique_numbers = list(set(all_numbers))
                    
                    if unique_numbers:
                        # 3. ترتيب ذكي: الموبايل أولاً، ثم الأرضي
                        # أي رقم يبدأ بـ 01 أو +201 يأخذ الأولوية (0)، والباقي (1)
                        unique_numbers.sort(key=lambda x: 0 if x.startswith(('01', '+201')) else 1)
                        
                        # 4. دمج الأرقام بفاصل واضح
                        phone = " | ".join(unique_numbers)
                    # ---------------------------------------------------------

                    website = "غير متوفر"
                    try:
                        web_link = driver.find_element(By.CSS_SELECTOR, "a[data-item-id='authority']")
                        website = web_link.get_attribute("href")
                    except:
                        pass

                    results.append({
                        "company_name": name,
                        "industry": keyword,
                        "location": location,
                        "phone": phone, # سيحوي الآن: "010xxxx | 012xxxx | 02xxxx"
                        "website": website
                    })
                    print(f"✅ Data Captured: {name} | 📞 {phone}")

                except Exception:
                    continue
        
        except Exception as e:
            print(f"❌ Critical Gmaps Error: {e}")
            
        finally:
            time.sleep(2)
            driver.quit() 
            return results