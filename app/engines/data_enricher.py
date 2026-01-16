import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import re
import time

class DataEnricher:
    def __init__(self):
        # جلسة متصفح واحدة مستمرة لضمان الاستقرار ومنع الانهيار
        self.driver = None

    def start_session(self):
        """بدء جلسة المتصفح مع إعدادات التخفي القصوى"""
        options = uc.ChromeOptions()
        # options.add_argument('--headless') # يمكنك تفعيلها للعمل الصامت
        options.add_argument('--no-sandbox')
        options.add_argument('--start-maximized') 
        # تفعيل وضع التخفي لتجنب كشف البوت وتخطي الحماية
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        self.driver = uc.Chrome(options=options)

    def stop_session(self):
        """إغلاق الجلسة بأمان"""
        if self.driver:
            self.driver.quit()

    def find_emails_and_people(self, company_name: str, website: str = ""):
        """المحرك الرئيسي لقنص الإيميلات وفك شفرة لينكد إن + هواتف إضافية"""
        # القيمة الافتراضية للنتيجة (تم إضافة extra_phones)
        result = {
            "email": "غير متوفر",
            "decision_maker_name": None,
            "decision_maker_role": None,
            "linkedin_url": None,
            "extra_phones": [] # القائمة الجديدة للأرقام المكتشفة
        }

        if not self.driver:
            return result
        
        try:
            # --- المرحلة الأولى: قنص الإيميلات والأرقام (Deep Search) ---
            # تم تحسين البحث ليشمل contact و رقم الموبايل المحتمل
            query = f'"{company_name}" contact email phone Egypt'
            print(f"🕵️ Deep hunting for: {company_name}")
            self.driver.get(f"https://www.google.com/search?q={query}")
            time.sleep(5) # انتظار تحميل النتائج
            
            page_source = self.driver.page_source
            
            # 1. استخراج الإيميلات (منطقك الأصلي)
            found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}', page_source)
            
            if found_emails:
                clean_list = []
                for e in found_emails:
                    e_clean = e.lower().replace('%22', '').replace('at%20', '').strip('+').strip('.')
                    if not e_clean.endswith(('png', 'jpg', 'jpeg', 'gif', 'css', 'js')):
                        if len(e_clean.split('@')[0]) > 1:
                            clean_list.append(e_clean)
                
                if clean_list:
                    official = [e for e in clean_list if not any(x in e for x in ['gmail', 'hotmail', 'yahoo'])]
                    result["email"] = official[0] if official else clean_list[0]
                    print(f"🎯 Email Shot Success: {result['email']}")

            # 2. استخراج هواتف إضافية من نتائج البحث (الميزة الجديدة المدمجة) 📱
            # Regex يلتقط: 01xxxxxxxxx أو +201xxxxxxxxx أو 02xxxxxxxxx
            found_phones = re.findall(r'(?:\+20|0)(?:1[0125]|2)\d{8}', page_source)
            unique_phones = list(set(found_phones)) # إزالة التكرار
            
            if unique_phones:
                result['extra_phones'] = unique_phones
                print(f"📞 Extra Phones Found in Search: {unique_phones}")

            # --- المرحلة الثانية: فك شفرة LinkedIn ---
            if result["decision_maker_name"] is None: # نبحث فقط لو لم نجد بيانات كافية
                print(f"🔗 Decoding LinkedIn for: {company_name}")
                li_query = f'site:linkedin.com/in/ "{company_name}" Egypt (CEO OR Manager OR Director)'
                self.driver.get(f"https://www.google.com/search?q={li_query}")
                
                self.driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(4) 
                
                try:
                    search_blocks = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'g')] | //div[@data-hveid]")
                    
                    for block in search_blocks:
                        try:
                            link_el = block.find_element(By.XPATH, ".//a[contains(@href, 'linkedin.com/in/')]")
                            url = link_el.get_attribute('href').split('&')[0]
                            
                            if "google.com/search" in url: continue
                                
                            result["linkedin_url"] = url
                            
                            raw_title = block.find_element(By.TAG_NAME, "h3").text
                            result["decision_maker_name"] = re.split(r'[-|–|—|:|\|]', raw_title)[0].strip()
                            
                            snippet = block.text
                            keywords = ['Manager', 'Director', 'CEO', 'Head', 'Founder', 'Owner', 'Operations', 'مدير', 'رئيس']
                            for role in keywords:
                                if role.lower() in snippet.lower() or role in raw_title:
                                    result["decision_maker_role"] = role
                                    break
                            
                            if not result["decision_maker_role"]:
                                result["decision_maker_role"] = "صانع قرار (Executive)"
                                
                            if result["decision_maker_name"]:
                                print(f"✅ Decoded LinkedIn: {result['decision_maker_name']} | {result['decision_maker_role']}")
                                break 
                        except: continue
                except Exception:
                    print(f"ℹ️ LinkedIn decoding info not found for {company_name}")

        except Exception as e:
            print(f"⚠️ [Enricher Error] {e}")
        
        return result