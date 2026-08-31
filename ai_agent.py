import anthropic
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import json
import time
import re
import requests
import threading

import os
from dotenv import load_dotenv

# Load env variables
_cur_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(_cur_dir, '.env')):
    load_dotenv(os.path.join(_cur_dir, '.env'))
else:
    load_dotenv()

# ==========================================
# 🔑 إعدادات المفاتيح
# ==========================================
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")
client_anthropic = anthropic.Anthropic(api_key=CLAUDE_API_KEY) if CLAUDE_API_KEY else None
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit'

# ==========================================
# 📊 إعدادات جوجل شيت
# ==========================================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_path = os.path.join(_cur_dir, 'credentials.json')
if not os.path.exists(creds_path):
    creds_path = os.path.join(r"c:\Users\pc2\Downloads\New folder (2)", 'credentials.json')
if not os.path.exists(creds_path):
    creds_path = 'credentials.json'

creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
client_sheet = gspread.authorize(creds)


def get_client():
    global client_sheet, creds
    try:
        client_sheet.open_by_url(SHEET_URL)
    except gspread.exceptions.APIError:
        client_sheet = gspread.authorize(creds)
    except Exception:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client_sheet = gspread.authorize(creds)
    return client_sheet


# ==========================================
# 🧠 ذاكرة المحادثات والحالات
# ==========================================
conversation_history = {}
user_names_cache = {}
user_state = {}


SHARED_TRIP_DATA = {
    'price': 500,
    'schedule': [
        "من الاسكندرية: 5:00 ص - 7:30 ص - 10:00 ص - 1:00 م - 4:30 م",
        "من القاهرة: 7:30 ص - 10:00 ص - 1:00 م - 4:00 م - 6:30 م"
    ],
    'pickup_alex': "الموقف الجديد او كارفور محرم بك",
    'pickup_cairo': "ميدان عبد المنعم رياض - رمسيس - عباسية - نادي السكة - اول شارع التسعين"
}

def normalize_city(city_name):
    if not city_name: return ""
    c = city_name.lower().strip()
    if 'cairo' in c or 'قاهرة' in c or 'قاهره' in c: return 'cairo'
    if 'alex' in c or 'إسكندرية' in c or 'اسكندرية' in c or 'اسكندريه' in c: return 'alexandria'
    if 'sahel' in c or 'ساحل' in c: return 'sahel'
    if 'borg' in c or 'برج' in c: return 'borg'
    if 'airport' in c or 'مطار' in c: return 'airport'
    return c


def get_user_state(sender_id):
    if sender_id not in user_state:
        user_state[sender_id] = {"step": "idle", "data": {}, "booking_code": None, "booking_info": None}
    return user_state[sender_id]


def reset_user_state(sender_id):
    user_state[sender_id] = {"step": "idle", "data": {}, "booking_code": None, "booking_info": None}
    conversation_history[sender_id] = []


def _clear_route_keep_personal(state, sender_id):
    """مسح بيانات المسار والسعر — الاسم والموبايل فقط يفضلوا"""
    saved_name = state['data'].get('name', '')
    saved_phone = state['data'].get('phone', '')
    state['data'] = {}
    state['step'] = 'idle'
    if saved_name and saved_name not in ["العميل", "..."]: state['data']['name'] = saved_name
    if saved_phone: state['data']['phone'] = saved_phone
    conversation_history.get(sender_id, []).clear()


# ==========================================
# ⚡ كاش الأسعار
# ==========================================
pricing_cache = {'data': None, 'last_fetch': None, 'ttl_minutes': 10}

# ==========================================
# 🛑 إدارة حالة البوت
# ==========================================
bot_paused = {}
employee_name = {}
user_locks = {}


def get_user_lock(sender_id):
    if sender_id not in user_locks:
        user_locks[sender_id] = threading.Lock()
    return user_locks[sender_id]


# ==========================================
# 🛡️ نظام الحماية ضد الهلوسة
# ==========================================
ALLOWED_STATE_KEYS = {
    'pickup', 'dropoff', 'date', 'time', 'pax', 'bags',
    'car', 'phone', 'whatsapp', 'name', 'price', 'price_round',
    'trip_type', 'notes'
}

KEY_NORMALIZE = {
    'from': 'pickup', 'origin': 'pickup', 'departure': 'pickup',
    'departure_city': 'pickup', 'from_city': 'pickup',
    'pickup_location': 'pickup', 'travel_from': 'pickup',
    'التحرك': 'pickup', 'مكان التحرك': 'pickup',
    'to': 'dropoff', 'destination': 'dropoff', 'arrival': 'dropoff',
    'arrival_city': 'dropoff', 'to_city': 'dropoff',
    'dropoff_location': 'dropoff', 'travel_to': 'dropoff',
    'الوصول': 'dropoff', 'مكان الوصول': 'dropoff',
    'day': 'date', 'passengers': 'pax', 'luggage': 'bags',
    'hour': 'time', 'phone_number': 'phone',
    'vehicle_type': 'car', 'car_type': 'car', 'vehicle': 'car',
    'السيارة': 'car', 'نوع السيارة': 'car',
}

GARBAGE_WORDS = [
    'أستنتج', 'أستطيع', 'المساعدة', 'كيف', 'تحتاج',
    'أحتاج', 'لم يتم', 'غير محدد', 'not specified',
    'تريد', 'هناك', 'أقوم', 'limousine', '24seven',
    'لأتمكن', 'إعداد', 'عرض سعر', 'مناسب لك',
    'التي قدمتها', 'هل هناك', 'تفاصيل أخرى',
    'help', 'assist', 'booking', 'information',
    'يمكنني', 'سأقوم', 'بالحجز',
    'حاضر', 'يا فندم', 'لحظة',
    'km', 'hour', 'minute', 'كيلو', 'ساعة', 'دقيقة',
]

GREETING_ONLY_WORDS = [
    'السلام عليكم', 'مساء الخير', 'صباح الخير', 'ازيك', 'أزيك',
    'ازايك', 'مرحبا', 'هاي', 'hello', 'hi', 'hey',
    'اهلا', 'أهلاً', 'يا جماعة', 'شكرا', 'شكراً',
    'عامل ايه', 'عامل إيه', 'كيف حالك',
]

# ==========================================
# 🗺️ نظام المدن والأسماء البديلة
# ==========================================
ALL_KNOWN_CITIES = [
    'القاهرة', 'القاهره', 'قاهرة', 'cairo',
    'الإسكندرية', 'اسكندرية', 'اسكندريه', 'الاسكندرية', 'الاسكندريه', 'alex', 'alexandria',
    'مطار القاهرة', 'مطار القاهره', 'المطار',
    'مطار برج العرب', 'برج العرب', 'مطار البرج', 'البرج', 'borg el arab',
    'مطار سفينكس', 'سفينكس',
    'الغردقة', 'غردقة', 'غردقه', 'hurghada',
    'شرم الشيخ', 'شرم', 'sharm',
    'الساحل الشمالي', 'ساحل', 'مارينا', 'العلمين', 'الساحل',
    'العين السخنة', 'عين السخنة', 'السخنة', 'سخنة', 'بورتو السخنه', 'بورتو السخنة',
    'مرسى مطروح', 'مطروح', 'بورسعيد', 'الاسماعيلية', 'اسماعيلية',
    'السويس', 'سويس', 'الأقصر', 'اقصر', 'أسوان', 'اسوان',
    'طنطا', 'المنصورة', 'منصورة', 'دمنهور', 'الرحاب', 'رحاب',
    'أسيوط', 'اسيوط', 'المنيا', 'منيا', 'الفيوم', 'فيوم',
    'كفر الدوار', 'دمياط', 'الزقازيق', 'بنها', 'بني سويف',
    'مدينة نصر', 'التجمع', 'اكتوبر', 'الشيخ زايد', 'المعادي',
]

CITY_CANONICAL = {
    'البرج': 'مطار برج العرب', 'مطار البرج': 'مطار برج العرب', 'برج العرب': 'مطار برج العرب',
    'مطار اسكندرية': 'مطار برج العرب', 'المطار': 'مطار القاهرة', 'مطار': 'مطار القاهرة',
    'اسكندرية': 'الإسكندرية', 'اسكندريه': 'الإسكندرية', 'الاسكندرية': 'الإسكندرية',
    'الاسكندريه': 'الإسكندرية', 'القاهره': 'القاهرة', 'قاهرة': 'القاهرة',
    'cairo': 'القاهرة', 'alex': 'الإسكندرية', 'alexandria': 'الإسكندرية',
    'غردقة': 'الغردقة', 'غردقه': 'الغردقة', 'hurghada': 'الغردقة',
    'شرم': 'شرم الشيخ', 'ساحل': 'الساحل الشمالي', 'السخنة': 'العين السخنة',
    'سخنة': 'العين السخنة', 'بورتو السخنه': 'العين السخنة', 'بورتو السخنة': 'العين السخنة',
    'مطروح': 'مرسى مطروح', 'اسماعيلية': 'الاسماعيلية', 'سويس': 'السويس',
    'اقصر': 'الأقصر', 'اسوان': 'أسوان', 'منصورة': 'المنصورة', 'رحاب': 'الرحاب',
    'سفينكس': 'مطار سفينكس',
}

# 🚗 تفاصيل أنواع السيارات
CAR_MODELS = {
    'سيدان': {'models': 'كورولا / سيراتو / النترا / تيبو', 'max_pax': 3, 'max_bags': 3},
    'مينى فان': {'models': 'اكسبندر / راش', 'max_pax': 5, 'max_bags': 5},
    'فان': {'models': 'تويوتا هاى اس / اتش ون', 'max_pax': 12, 'max_bags': 9},
}


def _extract_city_from_text(text):
    text_lower = text.strip().lower()
    for city in sorted(ALL_KNOWN_CITIES, key=len, reverse=True):
        if city.lower() in text_lower:
            return city
    return None


def _normalize_city_name(raw_name):
    raw_lower = raw_name.strip().lower()
    for alias, canonical in CITY_CANONICAL.items():
        if raw_lower == alias.lower():
            return canonical
    return raw_name.strip()


def _is_greeting_only(msg):
    msg_lower = msg.strip().lower()
    if _extract_city_from_text(msg_lower):
        return False
    if any(g in msg_lower for g in GREETING_ONLY_WORDS):
        return True
    if len(msg.split()) <= 3 and not re.search(r'\d', msg):
        return True
    return False


def _is_vague_route_request(msg):
    msg_lower = msg.strip().lower()
    vague_kw = ['رحلة اخرى', 'رحله اخرى', 'رحلة مختلفة', 'رحله مختلفه',
                'خط تاني', 'مسار تاني', 'اسأل عن رحلة', 'اسأل عن رحله',
                'اسئل عن رحله', 'اسئل عن رحلة', 'استفسر عن رحله', 'استفسر عن رحلة',
                'رحلة تانية', 'رحله تانيه', 'حاجة تانية', 'حاجه تانيه']
    return any(w in msg_lower for w in vague_kw)


def _is_cancel_request(msg):
    msg_lower = msg.strip().lower()
    cancel_kw_strict = [r'\bالغي\b', r'\bالغى\b', r'\bإلغاء\b', r'\bcancel\b', r'\bلأ\b']
    cancel_kw_loose = ['لا شكرا', 'لا شكراً', 'لا مش عايز',
                 'مش محتاج', 'لا خلاص', 'مش عايز احجز', 'كنسل'] # كنسل is fine as loose
    
    if any(phrase in msg_lower for phrase in cancel_kw_loose): return True
    if any(re.search(pat, msg_lower) for pat in cancel_kw_strict): return True
    
    return False


def _wants_new_inquiry(msg):
    """هل العميل عايز يسأل عن حاجة جديدة وهو في collecting_contact"""
    msg_lower = msg.strip().lower()
    indicators = ['بكام', 'سعر', 'من ', 'إلى', 'الى', 'رحلة', 'رحله', 'محتاج اعرف',
                  'عايز اعرف', 'اسأل', 'اسئل', 'استفسر', 'خط تاني', 'رحلة اخرى']
    return any(w in msg_lower for w in indicators)


def _validate_and_store(state_data, raw_key, raw_value):
    if not raw_value or not str(raw_value).strip():
        return False
    val = str(raw_value).strip()
    key = str(raw_key).strip().lower()
    nk = KEY_NORMALIZE.get(key, key)
    if nk not in ALLOWED_STATE_KEYS:
        print(f"  🚫 مفتاح مرفوض: '{raw_key}'")
        return False
    if nk in ('price', 'price_round'):
        print(f"  🚫 AI حاول يحدد سعر: {val}")
        return False
    if len(val) > 40:
        return False
    val_lower = val.lower()
    for g in GARBAGE_WORDS:
        if g in val_lower:
            print(f"  🚫 هلوسة ('{g}'): '{val[:30]}'")
            return False
    if sum(1 for c in val if c in '.,،!؟?:;') >= 2:
        return False
    if len(val.split()) > 4:
        return False
    if nk == 'car':
        if val_lower in ('true', 'false', 'yes', 'no', 'none', 'null', '1', '0'):
            return False
        val = normalize_car_type(val)
    if nk == 'phone':
        if not re.search(r'01[0-9]{9}', val): return False
    elif nk == 'pax':
        if not val.isdigit() or not (0 < int(val) <= 50): return False
    elif nk == 'bags':
        if not val.isdigit() or int(val) > 50: return False
    elif nk in ('pickup', 'dropoff'):
        if len(val) < 2: return False
        val = _normalize_city_name(val)

    state_data[nk] = val
    print(f"  ✅ تم تخزين: {nk} = '{val}'")
    return True


# ==========================================
# 🛠️ أدوات المعالجة
# ==========================================

def clean_price(price_input):
    if not price_input: return 0.0
    try: return float(re.sub(r'[^\d.]', '', str(price_input)) or '0')
    except: return 0.0


def fix_date_logic(date_str):
    try:
        if not date_str or "..." in str(date_str): return ""
        cd = datetime.now()
        cy = cd.year
        ds = str(date_str).strip()
        if any(w in ds for w in ["بعد بكره", "بعد بكرة", "بعد غد"]):
            return (cd + timedelta(days=2)).strftime("%Y/%m/%d")
        if any(w in ds for w in ["غدا", "بكره", "بكرة", "غدًا", "غداً"]):
            return (cd + timedelta(days=1)).strftime("%Y/%m/%d")
        if any(w in ds for w in ["اليوم", "نهاردة", "نفس اليوم", "النهارده", "النهاردة"]):
            return cd.strftime("%Y/%m/%d")
        ds = ds.replace("-", "/").replace("،", "")
        if "2023" in ds: ds = ds.replace("2023", str(cy))
        if "/" in ds:
            parts = ds.split("/")
            if len(parts) == 2:
                try:
                    a, b = int(parts[0]), int(parts[1])
                    if a > 12: day, month = a, b
                    elif b > 12: day, month = b, a
                    else: month, day = a, b
                    td = datetime(cy, month, day)
                    y = cy + 1 if td.date() < cd.date() else cy
                    return f"{y}/{month:02d}/{day:02d}"
                except: pass
            elif len(parts) == 3:
                if len(parts[0]) == 4: return ds
                if len(parts[2]) == 4: return f"{parts[2]}/{parts[1].zfill(2)}/{parts[0].zfill(2)}"
                try:
                    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    if m > 12: d, m = m, d
                    if y < 100: y += 2000
                    return f"{y}/{m:02d}/{d:02d}"
                except: pass
        return ds
    except: return date_str


def fix_time_logic(time_str):
    if not time_str or "..." in str(time_str) or len(str(time_str)) < 1: return ""
    t = str(time_str).strip()
    t = t.replace("الساعه", "").replace("الساعة", "").strip()
    t = t.replace("صباحا", "AM").replace("صباحاً", "AM").replace("صباخا", "AM")
    t = t.replace("مساء", "PM").replace("مساءً", "PM").replace("ظهرا", "PM")
    t = t.replace("عصرا", "PM").replace("ليلا", "PM").replace("فجرا", "AM")
    if "AM" not in t and "PM" not in t:
        t = re.sub(r'\s+ص$', ' AM', t)
        t = re.sub(r'\s+م$', ' PM', t)
        t = re.sub(r'(\d+)\s*ص', r'\1 AM', t)
        t = re.sub(r'(\d+)\s*م', r'\1 PM', t)
    for fmt in ['%I:%M:%S %p', '%I:%M %p', '%I %p', '%H:%M:%S', '%H:%M', '%H', '%I%p', '%I:%M%p']:
        try:
            p = datetime.strptime(t.strip(), fmt)
            h, m = p.hour, p.minute
            if h == 0: return f"ص 12:{m:02d}:00"
            elif h < 12: return f"ص {h}:{m:02d}:00"
            elif h == 12: return f"م 12:{m:02d}:00"
            else: return f"م {h-12}:{m:02d}:00"
        except: continue
    return time_str


def normalize_car_type(car_input):
    if not car_input: return "سيدان"
    v = str(car_input).strip().lower()
    if any(k in v for k in ["mini", "ميني", "مينى", "منى", "xpander", "اكسبندر", "rush", "راش", "عائلية", "minivan", "mini van"]):
        return "مينى فان"
    if any(k in v for k in ["van", "فان", "hiace", "هاي اس", "هاى اس", "h1", "باص"]):
        return "فان"
    return "سيدان"


def _recommend_car(pax, bags):
    """اختيار السيارة المناسبة بناءً على عدد الأفراد والشنط"""
    p, b = int(pax or 1), int(bags or 0)
    if p <= 3 and b <= 3:
        return "سيدان"
    elif p <= 5 and b <= 5:
        return "مينى فان"
    else:
        return "فان"


def check_car_capacity(car_type, pax_count, bags_count):
    try:
        pax = int(pax_count) if pax_count else 0
        bags = int(bags_count) if bags_count else 0
        car = normalize_car_type(car_type)
        info = CAR_MODELS.get(car, CAR_MODELS['سيدان'])
        if pax > info['max_pax']:
            return False, f"⚠️ {car} ({info['models']}) أقصى {info['max_pax']} أفراد (حضرتك {pax})."
        if bags > info['max_bags']:
            return False, f"⚠️ {car} ({info['models']}) أقصى {info['max_bags']} شنط (حضرتك {bags})."
        return True, ""
    except: return True, ""


def calculate_same_day_surcharge(date_str, base_price):
    try:
        today = datetime.now().date()
        trip_date = datetime.strptime(date_str, "%Y/%m/%d").date()
        if trip_date == today:
            s = int(base_price * 0.25)
            return {'is_same_day': True, 'surcharge': s, 'final_price': int(base_price) + s}
    except: pass
    return {'is_same_day': False, 'surcharge': 0, 'final_price': int(base_price)}


# ==========================================
# 💰 جلب الأسعار
# ==========================================

def fetch_pricing_data():
    global pricing_cache
    now = datetime.now()
    if (pricing_cache['data'] and pricing_cache['last_fetch'] and
            (now - pricing_cache['last_fetch']).total_seconds() < pricing_cache['ttl_minutes'] * 60):
        return pricing_cache['data']
    rows = []
    shared_routes = {} 

    try:
        client = get_client()
        sheet = client.open_by_url(SHEET_URL).worksheet("Pricing_Master")
        data = sheet.get_all_values()
        cur_origin = ""
        for i in range(1, min(len(data), 400)):
            if len(data[i]) >= 4:
                o = data[i][0].strip()
                if not o and cur_origin: o = cur_origin
                elif o: cur_origin = o
                
                origin = o
                dest = data[i][1].strip()
                car_type = data[i][2].strip() if len(data[i]) > 2 else ""
                price_oneway = data[i][3].strip() if len(data[i]) > 3 else "0"
                price_round = data[i][4].strip() if len(data[i]) > 4 else ""

                # Standard Car Entry
                rows.append({
                    'origin': origin, 'destination': dest,
                    'car_type': car_type,
                    'price_one_way': price_oneway,
                    'price_round_trip': price_round
                })

                # Check for Shared Trip
                # Keywords: مشترك, مشاركة, فرد, share, seat
                if any(kw in car_type.lower() for kw in ['مشترك', 'مشاركة', 'فرد', 'share', 'seat']):
                     # Extract numeric price
                     try:
                         p = int(clean_price(price_oneway))
                         if p > 0:
                             # 🟢 FIX: Normalize keys to ensure matching with user input
                             norm_o = _normalize_city_name(origin)
                             norm_d = _normalize_city_name(dest)
                             
                             shared_routes[(norm_o.lower(), norm_d.lower())] = p
                             # Also bidirectional? Usually yes for shared.
                             shared_routes[(norm_d.lower(), norm_o.lower())] = p
                     except: pass

        pricing_cache['data'] = rows
        pricing_cache['shared'] = shared_routes
        pricing_cache['last_fetch'] = now
        print("🔄 تم تحديث كاش الأسعار (بما في ذلك الرحلات المشتركة)")
        print(f"📊 Shared Routes Found: {len(shared_routes)}")
    except Exception as e:
        print(f"❌ Pricing Error: {e}")
    
    return pricing_cache['data'] or []


def lookup_shared_price(origin, destination):
    """البحث عن سعر الرحلة المشتركة للمسار المحدد"""
    if not pricing_cache.get('shared'):
        fetch_pricing_data()
    
    shared_routes = pricing_cache.get('shared', {})
    if not shared_routes:
        return None

    oc = _normalize_city_name(origin).lower()
    dc = _normalize_city_name(destination).lower()
    oa, da = _get_city_aliases(oc), _get_city_aliases(dc)

    # 1. Direct Lookup (Exact match)
    if (oc, dc) in shared_routes: return shared_routes[(oc, dc)]

    # 2. Fuzzy / Aliases Lookup
    best_match = None
    best_score = 0
    
    for (ro, rd), price in shared_routes.items():
        # Match Score
        om = _fuzzy_match(oc, ro, oa)
        dm = _fuzzy_match(dc, rd, da)
        
        score = om + dm
        if om and dm and score > best_score:
            best_score = score
            best_match = price
            
    return best_match


def _get_city_aliases(city_name):
    am = {
        'القاهرة': ['القاهره', 'قاهرة', 'cairo', 'مصر الجديدة', 'المعادي', 'مدينة نصر', 'التجمع', 'اكتوبر', '6 اكتوبر', 'الشيخ زايد', 'المهندسين', 'الدقي', 'وسط البلد', 'الجيزة', 'الجيزه', 'شبرا', 'رمسيس'],
        'الإسكندرية': ['اسكندرية', 'اسكندريه', 'الاسكندرية', 'الاسكندريه', 'إسكندرية', 'alex', 'alexandria'],
        'مطار القاهرة': ['مطار القاهره', 'المطار', 'cairo airport'],
        'مطار برج العرب': ['مطار برج العرب', 'برج العرب', 'borg el arab', 'مطار اسكندرية', 'مطار البرج', 'البرج'],
        'مطار سفينكس': ['سفينكس', 'sphinx'],
        'الغردقة': ['غردقة', 'غردقه', 'hurghada'],
        'شرم الشيخ': ['شرم', 'sharm'],
        'الساحل الشمالي': ['ساحل', 'north coast', 'مارينا', 'العلمين', 'الساحل'],
        'العين السخنة': ['عين السخنة', 'السخنة', 'سخنة', 'sokhna', 'بورتو السخنه', 'بورتو السخنة'],
        'مرسى مطروح': ['مطروح', 'marsa matrouh'],
        'بورسعيد': ['بورسعيد', 'port said'],
        'الاسماعيلية': ['اسماعيلية', 'ismailia'],
        'السويس': ['سويس', 'suez'],
        'الأقصر': ['اقصر', 'luxor'],
        'أسوان': ['اسوان', 'aswan'],
        'طنطا': ['طنطا', 'tanta'],
        'المنصورة': ['منصورة', 'mansoura'],
        'دمنهور': ['دمنهور', 'damanhour'],
        'الرحاب': ['رحاب', 'rehab'],
    }
    result = [city_name.lower()]
    for key, aliases in am.items():
        all_n = [key.lower()] + [a.lower() for a in aliases]
        if city_name.lower() in all_n:
            result.extend(all_n)
            break
    return list(set(result))


def _fuzzy_match(query, target, aliases=None):
    q, t = query.strip().lower(), target.strip().lower()
    if not q or not t: return 0
    if q == t: return 3
    if q in t or t in q: return 2
    if aliases:
        for a in aliases:
            if a.lower() == t or a.lower() in t or t in a.lower(): return 2
    if set(q.split()) & set(t.split()): return 1
    return 0



def _is_city_known(city_text):
    """Check if the text contains any known city/location"""
    if not city_text: return False
    return _extract_city_from_text(city_text) is not None


def lookup_price(origin, destination, car_type="سيدان"):
    """🔒 البحث عن السعر مع عكس الاتجاه تلقائياً"""
    rows = fetch_pricing_data()
    if not rows: return None, None
    # 🟢 FIX: Normalize inputs
    oc = _normalize_city_name(origin).lower()
    dc = _normalize_city_name(destination).lower()
    cc = normalize_car_type(car_type)
    oa, da = _get_city_aliases(oc), _get_city_aliases(dc)
    best, best_s = None, 0
    for r in rows:
        ro, rd = r['origin'].strip().lower(), r['destination'].strip().lower()
        # محاولة أولى: origin→destination
        om = _fuzzy_match(oc, ro, oa)
        dm = _fuzzy_match(dc, rd, da)
        # محاولة ثانية: عكس الاتجاه (مطروح→قاهرة = قاهرة→مطروح)
        if not om or not dm:
            om = _fuzzy_match(oc, rd, oa)
            dm = _fuzzy_match(dc, ro, da)
        if not om or not dm: continue
        
        # Priority:
        # 1. Exact car match (score + 10)
        # 2. Origin/Dest match score (om + dm)
        
        car_score = 0
        row_car = normalize_car_type(r['car_type'])
        if row_car == cc:
            car_score = 10
        elif cc == "سيدان" and row_car == "": # Default empty car kind of matches sedan?
             car_score = 5
        else:
             # Mismatch car type -> Skip! 
             # We want STRICT car matching if possible.
             # If user asks for "Mini Van", we should NOT return "Sedan" price.
             continue

        s = om + dm + car_score
        
        # Tie-breaker: prefer rows with round-trip price if round-trip requested? 
        # But here we just want the BEST row for this car.
        
        if s > best_s: best_s, best = s, r
        
    if best:
        return clean_price(best['price_one_way']), clean_price(best.get('price_round_trip', '0'))
    return None, None


def lookup_all_car_prices(origin, destination):
    """جلب أسعار كل أنواع السيارات لنفس المسار"""
    results = {}
    for car_type in ['سيدان', 'مينى فان', 'فان']:
        p1, pr = lookup_price(origin, destination, car_type)
        if p1 and p1 > 0:
            results[car_type] = {'one_way': int(p1), 'round_trip': int(pr) if pr and pr > 0 else 0}
    return results


# ==========================================
# 📡 استخراج بيانات من رسائل العميل
# ==========================================

NOT_NAME_WORDS = [
    'سعر', 'بكام', 'احجز', 'حجز', 'اكد', 'أكد', 'تمام', 'اوك', 'ok', 'yes',
    'لا', 'نعم', 'شكرا', 'مساء', 'صباح', 'السلام', 'ازيك', 'عايز', 'محتاج',
    'رحلة', 'رحله', 'سيارة', 'سيدان', 'فان', 'ميني', 'مينى', 'اتجاه',
    'ذهاب', 'عودة', 'واحد', 'فرد', 'شخص', 'شنطة', 'شنطه', 'شنط',
    'من', 'إلى', 'الى', 'ل', 'في', 'على', 'مع', 'فين', 'ايه', 'ليه',
    'كام', 'هل', 'متى', 'امتى', 'غالي', 'رخيص', 'تعديل', 'الغاء',
    'البيانات', 'صحيحة', 'صحيحه', 'الحجز', 'الغي', 'عدل', 'غير',
    'اه', 'ايوه', 'أيوه', 'ماشي', 'خلاص', 'يلا', 'طيب', 'اى',
    'فاهم', 'فهمت', 'فهمتو', 'اللى', 'الاسم', 'اسم', 'اكتب',
    'بعتلك', 'متكتبش', 'كده', 'صح', 'غلط', 'مظبوط', 'الغي', 'الغى',
]



def _try_extract_name(msg, state_data):
    prefixes = ['الاسم', 'اسم', 'اسمي', 'أنا', 'انا', 'name', 'الأسم']
    msg_clean = msg.strip()

    # Try processing line by line in case of pasted info
    for line in msg_clean.split('\\n'):
        line = line.strip()
        if not line: continue
        
        # 1. Check for specific prefix
        words = line.split()
        if not words: continue
        
        first_word = words[0]
        # Normalize (remove :)
        first_word_norm = first_word.replace(':', '')
        
        candidate = line
        # If matches a prefix, strip it
        if first_word_norm in prefixes:
             # Remove first word
             candidate = line[len(first_word):].strip()
             # Remove starting : if present "الاسم: احمد"
             if candidate.startswith(":"): candidate = candidate[1:].strip()
        
        if not candidate: continue

        # now validate 'candidate'
        # 1. No digits (unless rare cases, but let's stick to no digits for safety)
        if re.search(r'\d', candidate): continue
        if "/" in candidate or "-" in candidate: continue
        
        c_words = candidate.split()
        if len(c_words) < 1 or len(c_words) > 5: continue
        
        is_bad = False
        for w in c_words:
            if w.lower() in NOT_NAME_WORDS: 
                is_bad = True
                break
        if is_bad: continue
        
        # Length check
        if any(len(w) < 2 for w in c_words): continue
        
        # Success
        state_data['name'] = candidate
        print(f"  👤 اسم: {candidate}")
        return True
        
    return False

def _text_to_digit(text):
    """تحويل الأرقام النصية والمثنى إلى أرقام حسابية"""
    if not text: return None
    mapping = {
        'واحد': '1', 'واحده': '1', 'واحدة': '1',
        'اتنين': '2', 'اثنين': '2', 'تلاته': '3', 'ثلاثه': '3', 'ثلاثة': '3',
        'اربع': '4', 'أربع': '4', 'اربعة': '4', 'أربعة': '4',
        'خمس': '5', 'خمسة': '5', 'ست': '6', 'ستة': '6',
        'سبع': '7', 'سبعة': '7', 'تمان': '8', 'ثمان': '8', 'ثمانية': '8',
        'تسع': '9', 'تسعة': '9', 'عشر': '10', 'عشرة': '10',
        'فردين': '2 فرد', 'شخصين': '2 شخص', 'راكبين': '2 راكب',
        'شنطتين': '2 شنطة', 'حقيبتين': '2 حقيبة'
    }
    for word, digit in mapping.items():
        if word in text: return digit
    return None


def _parse_complex_quantity(text, entity_type):
    """
    تحليل أعداد معقدة مثل: "زوج وزوجة وأربع أطفال" -> 6
    entity_type: 'pax' (أفراد) أو 'bags' (شنط)
    """
    if not text: return 0
    t = text.strip().lower()
    
    # 1. Keywords mapping (Singular/Dual)
    keywords = {}
    if entity_type == 'pax':
        keywords = {
            'عيال': 1, 'أولاد': 1, 'اولاد': 1,
            'زوج': 1, 'زوجة': 1, 'زوجه': 1, 'طفل': 1, 'أطفال': 1, 'اطفال': 1,
            'ابن': 1, 'ابنة': 1, 'بنت': 1, 'ولد': 1, 'مدام': 1, 'رجل': 1, 'ست': 1,
            'أنا': 1, 'انا': 1, 'نفر': 1, 'شخص': 1, 'فرد': 1, 'راكب': 1, 'معايا': 1,
            'مراتي': 1, 'مراتى': 1, 'ابنى': 1, 'ابني': 1, 'بنتي': 1, 'بنتى': 1, 'اختي': 1, 'أختي': 1, 'اختى': 1, 'صاحبي': 1, 'صاحبى': 1,
            'معانا': 0, 'معاكم': 0, # Prevent partial match with 'أنا' or 'كم'
            'فردين': 2, 'شخصين': 2, 'نفرين': 2, 'زوجين': 2, 'طفلين': 2, 'ولدين': 2, 'بنتين': 2
        }
    elif entity_type == 'bags':
        keywords = {
        'شنطة': 1, 'شنطه': 1, 'حقيبة': 1, 'حقيبه': 1, 'كرتونة': 1, 'كرتونه': 1,
            'شنطتين': 2, 'حقيبتين': 2, 'كرتوتنين': 2, 'حقائب': 1, 'شنط': 1
        }

    # Pre-processing
    t = re.sub(r'[+\،,]', ' ', t)
    t = re.sub(r'\s+و\s+', ' و', t) # "x و y" -> "x wy" (attach w to next word)
    t = re.sub(r'\s+(ل|الى|الي)\s+', ' ', t) # Remove "to" to bring Number closer to Keyword
    
    # Define "other" keywords to avoid processing numbers attached to them (e.g. "3 bags" when counting pax)
    # CRITICAL: Must be exhaustive to prevent "2 pax" being counted as "2" in bags because "pax" word wasn't ignored.
    other_keywords = {}
    if entity_type == 'pax':
        # Bags keywords to ignore
        other_keywords = {
            'شنطة': 1, 'شنطه': 1, 'حقيبة': 1, 'حقيبه': 1, 'كرتونة': 1, 'كرتونه': 1,
            'شنطتين': 2, 'حقيبتين': 2, 'كرتوتنين': 2, 'حقائب': 1, 'شنط': 1,
            'أمتعة': 1, 'امتعه': 1, 'شوال': 1, 'شغلات': 1, 'عدد الشنط': 1, 'الشنط': 1
        }
    elif entity_type == 'bags':
        # Pax keywords to ignore
        other_keywords = {
             'عيال': 1, 'أولاد': 1, 'اولاد': 1, 'زوج': 1, 'زوجة': 1, 'طفل': 1, 'أطفال': 1, 
             'ابن': 1, 'بنت': 1, 'ولد': 1, 'رجل': 1, 'ست': 1, 'أنا': 1, 'نفر': 1, 'شخص': 1, 'راكب': 1,
             'فرد': 1, 'مدام': 1, 'انسة': 1, 'آنسة': 1, 'كابتن': 1, 'سائق': 1, ' سواق': 1,
             'مراتي': 1, 'مراتى': 1, 'ابنى': 1, 'ابني': 1, 'بنتي': 1, 'بنتى': 1, 'اختي': 1, 'أختي': 1, 'اختى': 1, 'صاحبي': 1, 'صاحبى': 1,
             'افراد': 1, 'أفراد': 1, 'الافراد': 1, 'الأفراد': 1, 'اشخاص': 1, 'أشخاص': 1, 'الركاب': 1, 'ركاب': 1, 'عدد الافراد': 1
        }
    
    # Sort keys implies we check longest keywords first
    sorted_keys = sorted(keywords.keys(), key=len, reverse=True)
    sorted_other_keys = sorted(other_keywords.keys(), key=len, reverse=True)

    tokens = t.split()
    parsed_items = []
    
    for token in tokens:
        word = token.strip()
        if not word: continue
        
        has_w = False
        clean_word = word
        item_type = None  # Initialize to avoid UnboundLocalError
        item_val = 0
        is_ignored = False

        # Check if "w" attached (heuristic)
        if word.startswith('و') and len(word) > 1:
            stripped = word[1:]
            # Check if stripped is valid number or keyword
            if re.match(r'^\d+$', stripped) or _text_to_digit(stripped):
                clean_word = stripped
                has_w = True
            else:
                 is_target_kw = any(k in stripped for k in sorted_keys)
                 is_other_kw = any(k in stripped for k in sorted_other_keys)
                 if is_target_kw or is_other_kw:
                     clean_word = stripped
                     has_w = True

        # Check if this word belongs to the "OTHER" category (e.g. "bags" when counting pax)
        # If so, mark as ignored so we don't count it, AND we might consume preceding number
        for k in sorted_other_keys:
            if k in clean_word:
                item_type = 'other'
                break
        
        if not item_type:
            # A. Number (Digits)
            if re.match(r'^\d+$', clean_word):
                # FIX: Ignore phone numbers or years (e.g. 011..., 2026)
                if len(clean_word) > 2 or clean_word.startswith(('010', '011', '012', '015', '05', '+2')):
                     item_type = 'ignore'
                else:
                    item_type = 'num'
                    item_val = int(clean_word)
            
            # B. Keyword
            elif not item_type:
                 for k in sorted_keys:
                     if k in clean_word:
                         item_type = 'kw'
                         item_val = keywords[k]
                         break
            
            # C. Text Number
            if not item_type:
                text_digit = _text_to_digit(clean_word)
                if text_digit:
                    item_type = 'num'
                    item_val = text_digit
        
        parsed_items.append({'type': item_type, 'val': item_val, 'w': has_w})
            
    # Resolution Pass
    total = 0
    i = 0
    while i < len(parsed_items):
        curr = parsed_items[i]
        next_item = parsed_items[i+1] if i+1 < len(parsed_items) else None
        
        consumed = False
        
        # Handling "Number + Keyword"
        if next_item and not next_item['w']:
            if curr['type'] == 'num':
                if next_item['type'] == 'kw':
                    total += curr['val'] * next_item['val'] # 3 * 2 persons -> 6 (logic mostly 1 per kw but handling 'couple')
                    i += 2
                    consumed = True
                elif next_item['type'] == 'other':
                     # "3" "bags" -> Ignore both when counting pax
                     i += 2
                     consumed = True
            
            elif curr['type'] == 'kw' and next_item['type'] == 'num':
                total += next_item['val'] # "pax" "3" -> 3 (Arabic style often Num Kw, but handling reverse)
                i += 2
                consumed = True

            elif curr['type'] == 'other' and next_item['type'] == 'num':
                # "pax" "3" -> Ignore both when counting bags
                i += 2
                consumed = True
                
        if not consumed:
            if curr['type'] in ['kw', 'num']:
                 total += curr['val']
            i += 1
            
    return total




def extract_data_from_message(msg, state_data):
    mc = msg.strip()
    
    # 1. تحويل الأرقام النصية في الرسالة (أربع -> 4)
    processed_msg = mc
    for word in mc.split():
        digit = _text_to_digit(word)
        if digit: processed_msg = processed_msg.replace(word, digit)
    
    
    

    
    pm = re.search(r'(01[0-9]{9})', mc)
    if pm:
        state_data['phone'] = pm.group(1)
        if not state_data.get('whatsapp'): state_data['whatsapp'] = pm.group(1)
        print(f"  📱 موبايل: {pm.group(1)}")

    for p in [r'(\d{1,2})/(\d{1,2})/(\d{2,4})', r'(\d{1,2})/(\d{1,2})',
              r'(\d{1,2})-(\d{1,2})-(\d{2,4})', r'(\d{1,2})-(\d{1,2})']:
        m = re.search(p, mc)
        if m:
            f = fix_date_logic(m.group(0))
            if f: state_data['date'] = f; print(f"  📅 تاريخ: {f}")
            break

    for w, d in {"اليوم": 0, "نهاردة": 0, "النهارده": 0, "بكره": 1, "بكرة": 1,
                 "غدا": 1, "غداً": 1, "بعد بكره": 2, "بعد بكرة": 2}.items():
        if w in mc:
            state_data['date'] = (datetime.now() + timedelta(days=d)).strftime("%Y/%m/%d")
            print(f"  📅 تاريخ: {state_data['date']}")
            break

    for tp in [r'(\d{1,2})\s*(صباحا|صباحاً|ص)', r'(\d{1,2})\s*(مساء|مساءً|م)',
               r'(\d{1,2}):(\d{2})\s*(ص|م|AM|PM|am|pm)', r'(\d{1,2})\s*(AM|PM|am|pm)',
               r'الساع[هة]\s*(\d{1,2})']:
        m = re.search(tp, mc)
        if m:
            f = fix_time_logic(m.group(0))
            if f: state_data['time'] = f; print(f"  🕐 وقت: {f}")
            break

    # تعقيد جديد: تحليل لـ "أنا وزوجتي و3 عيال"
    # لو ما فيش أرقام صريحة، نحاول نجمع
    
    # Pax Check
    parsed_pax = _parse_complex_quantity(processed_msg, 'pax')
    if parsed_pax > 0:
         # Only override if we found something meaningful and it's better/different
         # Or if we didn't have pax before
         state_data['pax'] = str(parsed_pax)
         print(f"  👥 أفراد (معقد): {parsed_pax}")
    elif ("فرد" in mc or "شخص" in mc or "راكب" in mc) and not state_data.get('pax'):
        state_data['pax'] = '1'
        print(f"  👥 أفراد: 1 (مفرد)")

    # Bags Check
    parsed_bags = _parse_complex_quantity(processed_msg, 'bags')
    if parsed_bags > 0:
         state_data['bags'] = str(parsed_bags)
         print(f"  🧳 شنط (معقد): {parsed_bags}")
    elif ("شنطة" in mc or "شنطه" in mc or "حقيبة" in mc) and not state_data.get('bags'):
        state_data['bags'] = '1'
        print(f"  🧳 شنط: 1 (مفرد)")

    for ct, kws in {'سيدان': ['سيدان', 'كورولا', 'ملاكي', 'عادي', 'عاديه', 'sedan'],
                    'مينى فان': ['ميني فان', 'مينى فان', 'منى فان', 'اكسبندر', 'راش', 'xpander', 'mini van', 'minivan'],
                    'فان': ['فان', 'هاي اس', 'هاى اس', 'باص', 'h1', 'hiace', 'van']}.items():
        if any(kw in mc.lower() for kw in kws):
            state_data['car'] = ct; print(f"  🚗 سيارة: {ct}"); break

    return state_data


# ==========================================
# 🧪 التحقق من اكتمال البيانات
# ==========================================

def validate_booking_data(data):
    missing = []
    name = str(data.get('name', '')).strip()
    if not name or name in ["العميل", "..."]: missing.append("الاسم بالكامل")
    ph = str(data.get('phone', '')).strip()
    if not ph or len(re.sub(r'\D', '', ph)) < 10: missing.append("رقم الموبايل")
    if not data.get('pickup'): missing.append("مكان التحرك")
    if not data.get('dropoff'): missing.append("مكان الوصول")
    if not data.get('date'): missing.append("تاريخ السفر")
    if not data.get('time'): missing.append("وقت التحرك")
    pax = str(data.get('pax', '0'))
    if pax == "0" or not pax.isdigit(): missing.append("عدد الأفراد")
    bags = str(data.get('bags', ''))
    if not bags or not bags.isdigit(): missing.append("عدد الشنط")
    if clean_price(data.get('price', '0')) <= 0: missing.append("السعر")
    if not missing:
        ok, err = check_car_capacity(data.get('car', 'سيدان'), pax, bags)
        if not ok: return [err]
    return missing


# ==========================================
# 💾 حفظ الحجز
# ==========================================

def save_booking_to_sheet(data):
    try:
        client = get_client()
        ws = client.open_by_url(SHEET_URL).worksheet("امر حجز عميل")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dc = fix_date_logic(str(data.get('date', '')))
        tc = fix_time_logic(str(data.get('time', '')))
        cc = normalize_car_type(str(data.get('car', 'سيدان')))
        pc = str(data.get('phone', ''))[:50]
        wc = str(data.get('whatsapp', '')).strip() or pc
        nc = str(data.get('notes', '')).strip() or "لا يوجد"
        tt = "ذهاب وعودة" if data.get('trip_type') == "ذهاب وعودة" else "ذهاب فقط"
        bp = clean_price(data.get('price', '0'))
        si = calculate_same_day_surcharge(dc, bp)
        total = si['final_price']
        if si['is_same_day']: nc += f" | ⏰ نفس اليوم (+{si['surcharge']}ج)"
        if wc: nc += f" | واتساب: {wc}"
        row = [ts, dc, tc, str(data.get('name', ''))[:100], pc,
               "Messenger AI", str(data.get('pickup', ''))[:200], str(data.get('dropoff', ''))[:200],
               str(data.get('pax', '1')), str(data.get('bags', '0')),
               cc, "جديد", str(int(total)), "", nc[:250], tt, "0", "AI Agent (FB)", ""]
        ws.append_row(row)
        print(f"✅ تم حفظ الحجز.")
        booking_code = "تم الحجز"
        for attempt in range(3):
            time.sleep(3)
            try:
                last_row = len(ws.get_all_values())
                val = ws.cell(last_row, 21).value
                if val and str(val).strip() not in ["", "#N/A", "None", "Loading", "Pending"]:
                    booking_code = str(val).strip()
                    print(f"✅ كود الحجز (محاولة {attempt+1}): {booking_code}")
                    break
            except: pass
        return {'success': True, 'booking_code': booking_code, 'date': dc, 'time': tc,
                'pickup': str(data.get('pickup', '')), 'dropoff': str(data.get('dropoff', '')),
                'car': cc, 'name': str(data.get('name', '')), 'phone': pc, 'whatsapp': wc,
                'pax': str(data.get('pax', '1')), 'bags': str(data.get('bags', '0')),
                'price': str(int(total)), 'trip_type': tt}
    except Exception as e:
        print(f"❌ Save Error: {e}")
        return {'success': False}


# ==========================================
# 🔍 حجز / تعديل / إلغاء
# ==========================================

def find_booking_by_code(code):
    try:
        client = get_client()
        sheet = client.open_by_url(SHEET_URL).worksheet("امر حجز عميل")
        cells = sheet.findall(str(code).strip())
        t = next((c for c in cells if c.col == 21), None)
        if not t or t.row < 2: return None
        r = sheet.row_values(t.row)
        gv = lambda i: r[i] if len(r) > i else ""
        d = {"code": code, "row": t.row, "date": gv(1), "time": gv(2), "name": gv(3),
             "phone": gv(4), "pickup": gv(6), "dropoff": gv(7), "pax": gv(8), "bags": gv(9),
             "car": gv(10), "status": gv(11), "price": gv(12), "notes": gv(14)}
        if "حذف" in str(gv(19)).lower(): d["status"] = "❌ ملغي"
        return d
    except: return None


def update_booking_in_sheet(code, action, updates=None, reason=None):
    try:
        client = get_client()
        sheet = client.open_by_url(SHEET_URL).worksheet("امر حجز عميل")
        cells = sheet.findall(str(code).strip())
        t = next((c for c in cells if c.col == 21), None)
        if not t: return False, "الكود غير موجود."
        r = t.row
        if action == "cancel":
            sheet.update_cell(r, 20, "حذف")
            old = sheet.cell(r, 15).value or ""
            sheet.update_cell(r, 15, f"{old} | ❌ إلغاء" + (f": {reason}" if reason else ""))
            return True, "تم إلغاء الرحلة."
        elif action == "modify" and updates:
            cm = {"date": 2, "time": 3, "name": 4, "phone": 5, "pickup": 7,
                  "dropoff": 8, "pax": 9, "bags": 10, "car": 11, "price": 13}
            ch = False
            for k, v in updates.items():
                if k.lower() in cm and str(v).strip():
                    sheet.update_cell(r, cm[k.lower()], str(v).strip()); ch = True
            if ch: sheet.update_cell(r, 20, "تعديل"); return True, "تم التعديل."
        return False, "لم يحدث تغيير."
    except Exception as e: return False, f"خطأ: {e}"


def get_facebook_user_name(sender_id):
    if sender_id in user_names_cache: return user_names_cache[sender_id]
    try:
        r = requests.get(f"https://graph.facebook.com/{sender_id}?fields=first_name,last_name&access_token={FB_PAGE_TOKEN}", timeout=5)
        if r.status_code == 200:
            d = r.json()
            n = f"{d.get('first_name', '')} {d.get('last_name', '')}".strip()
            if n: user_names_cache[sender_id] = n; return n
    except: pass
    return "العميل"


# ==========================================
# 🤖 Claude API
# ==========================================

def call_claude_api(system_prompt, messages, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = client_anthropic.messages.create(
                model="claude-3-haiku-20240307", max_tokens=800, temperature=0.0,
                system=system_prompt, messages=messages)
            return resp.content[0].text
        except anthropic.APIStatusError as e:
            if e.status_code in [529, 429]: time.sleep((attempt + 1) * 2)
            else: raise
        except: raise
    return None


def get_system_prompt(user_name, instruction):
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""أنت "أحمد" موظف حجز في 24Seven Limousine.
التاريخ: {today} | العميل: {user_name}

🚫 ممنوعات:
- لا تخترع أسعار.
- لا تقول "تم الحجز" أو "تم التأكيد".
- لا تضيف price أو distance أو duration.
- لا تكتب "لم يتم تحديده" أو "true" أو "false".

✅ مهمتك:
- استخرج مدينة التحرك والوصول (كلمة أو كلمتين فقط لكل مدينة).
- ⚠️ هام: لو ذكر "مطار" (Airport) لازم تكتب "مطار ..." في الـ DETECT_DATA (مثال: "مطار القاهرة" مش "القاهرة" بس).
- DETECT_DATA: {{"pickup": "...", "dropoff": "..."}}
- لو ذكر نوع سيارة: أضف "car".
- ⚠️ لو مفيهاش مدن واضحة → لا تضع DETECT_DATA.
- أسلوبك: مصري لطيف بياع ذكي. لا تقول أنك AI.

{instruction}"""


# ==========================================
# 🔧 دوال مساعدة
# ==========================================

def _send_and_log(sender_id, text):
    conversation_history.setdefault(sender_id, []).append({"role": "assistant", "content": text})
    return text


def _extract_from_ai_reply(bot_reply, state, original_msg=""):
    if "DETECT_DATA:" not in bot_reply:
        return
    if _is_greeting_only(original_msg):
        print(f"  🚫 تجاهل DETECT_DATA — تحية: '{original_msg}'")
        return
    try:
        json_str = bot_reply.split("DETECT_DATA:")[1].strip().replace("'", '"')
        match = re.search(r'\{[^}]*\}', json_str)
        if not match: return
        extracted = json.loads(match.group(0))
        for k, v in extracted.items():
            _validate_and_store(state['data'], k, v)
    except Exception as e:
        print(f"⚠️ DETECT_DATA Error: {e}")


def _ask_ai(sender_id, user_msg, user_name, instruction):
    if not user_msg or not user_msg.strip():
        return "أهلاً يا فندم! أقدر أساعدك في إيه؟ 😊"
    conversation_history.setdefault(sender_id, []).append({"role": "user", "content": user_msg})
    if len(conversation_history[sender_id]) > 6:
        conversation_history[sender_id] = conversation_history[sender_id][-6:]
    try:
        reply = call_claude_api(get_system_prompt(user_name, instruction), conversation_history[sender_id])
    except:
        return "عذراً النظام مشغول. ممكن تحاول كمان دقيقة؟ 🙏"
    if not reply: return "ثواني يا فندم.. 🙏"
    state = get_user_state(sender_id)
    _extract_from_ai_reply(reply, state, user_msg)
    clean = reply.split("DETECT_DATA:")[0].strip()
    if not clean: clean = "تمام يا فندم!"
    for kw in ["تم الحجز", "تم التأكيد", "تم تسجيل", "booking confirmed", "كود الحجز"]:
        clean = clean.replace(kw, "").strip()
    if not clean: clean = "تمام يا فندم!"
    conversation_history[sender_id].append({"role": "assistant", "content": clean})
    return clean


def _build_missing_fields_message(sd):
    missing, has = [], []
    if sd.get('pickup'): has.append(f"📍 من: {sd['pickup']}")
    if sd.get('dropoff'): has.append(f"📍 إلى: {sd['dropoff']}")
    if sd.get('price') and clean_price(sd['price']) > 0:
        car = normalize_car_type(sd.get('car', 'سيدان'))
        models = CAR_MODELS.get(car, {}).get('models', '')
        has.append(f"💰 السعر: {int(clean_price(sd['price']))} جنيه ({car} - {models})")
    name = str(sd.get('name', '')).strip()
    if not name or name in ["العميل", "..."]: missing.append("👤 الاسم بالكامل")
    else: has.append(f"👤 الاسم: {name}")
    ph = str(sd.get('phone', '')).strip()
    if not ph or len(re.sub(r'\D', '', ph)) < 10: missing.append("📱 رقم الموبايل")
    else: has.append(f"📱 الموبايل: {ph}")
    if not sd.get('date'): missing.append("📅 تاريخ السفر (مثال: 15/2 أو بكرة)")
    else: has.append(f"📅 التاريخ: {sd['date']}")
    if not sd.get('time'): missing.append("🕐 وقت التحرك (مثال: 8 ص أو 3 م)")
    else: has.append(f"🕐 الوقت: {sd['time']}")
    if not sd.get('pax'): missing.append("👥 عدد الأفراد")
    else: has.append(f"👥 الأفراد: {sd['pax']}")
    if not sd.get('bags'): missing.append("🧳 عدد الشنط")
    else: has.append(f"🧳 الشنط: {sd['bags']}")
    if not missing: return None
    msg = "تمام يا فندم 👍 عشان أكمل الحجز محتاج:\n\n"
    if has: msg += "✅ اللي عندي:\n" + "".join(f"  {h}\n" for h in has) + "\n"
    msg += "❓ لسه محتاج:\n" + "".join(f"  {m}\n" for m in missing)
    msg += "\nابعتهم في رسالة واحدة 😊"
    return msg


def _build_price_display(pickup, dropoff, all_prices, recommended_car=None, pax=None, bags=None):
    """🔴 عرض أسعار كل السيارات المتاحة مع التوصية"""
    if not all_prices:
        return None

    msg = f"✅ تمام يا فندم!\n\n📍 من: {pickup}\n📍 إلى: {dropoff}\n"
    if pax: msg += f"👥 {pax} أفراد"
    if bags: msg += f" | 🧳 {bags} شنط"
    if pax or bags: msg += "\n"
    msg += "\n"

    for car_type in ['سيدان', 'مينى فان', 'فان']:
        if car_type not in all_prices:
            continue
        info = CAR_MODELS[car_type]
        prices = all_prices[car_type]
        is_rec = (car_type == recommended_car)
        star = " ⭐ (الأنسب لحضرتك)" if is_rec else ""

        msg += f"🚗 {car_type} ({info['models']}){star}\n"
        msg += f"   💰 اتجاه واحد: {prices['one_way']} جنيه\n"
        if prices['round_trip'] > 0:
            msg += f"   💰 ذهاب وعودة: {prices['round_trip']} جنيه\n"
        msg += f"   📏 أقصى: {info['max_pax']} أفراد / {info['max_bags']} شنط\n\n"

    msg += "أي نوع يناسب حضرتك؟ 😊"
    return msg


def _show_summary(sender_id, user_name, state):
    d = state['data']
    fb_name = get_facebook_user_name(sender_id)
    if (not d.get('name') or d['name'] in ["العميل", "..."]) and fb_name != "العميل":
        d['name'] = fb_name
    if not d.get('whatsapp'): d['whatsapp'] = d.get('phone', '')
    if not d.get('car'): d['car'] = 'سيدان'
    state['step'] = 'summary_shown'

    car = normalize_car_type(d.get('car', 'سيدان'))
    if d.get('pickup') and d.get('dropoff'):
        p, pr = lookup_price(d['pickup'], d['dropoff'], car)
        
        # Check trip_type to determine which price to show
        if d.get('trip_type') == "ذهاب وعودة" and pr and int(pr) > 0:
            d['price'] = str(int(pr))
        elif p and int(p) > 0:
            d['price'] = str(int(p))

    fp = int(clean_price(d.get('price', '0')))
    si = calculate_same_day_surcharge(str(d.get('date', '')), fp)
    pt = f"{si['final_price']} جنيه"
    if si['is_same_day']: pt += f" (شامل {si['surcharge']}ج زيادة نفس اليوم)"

    models = CAR_MODELS.get(car, {}).get('models', '')

    return _send_and_log(sender_id, f"""📋 ملخص الحجز يا فندم:

👤 الاسم: {d.get('name', '?')}
📍 من: {d.get('pickup', '?')}
📍 إلى: {d.get('dropoff', '?')}
📅 التاريخ: {d.get('date', '?')}
🕐 الوقت: {d.get('time', '?')}
👥 الأفراد: {d.get('pax', '?')}
🧳 الشنط: {d.get('bags', '?')}
🚗 السيارة: {car} ({models})
📱 الموبايل: {d.get('phone', '?')}
💰 السعر: {pt}

البيانات صحيحة؟ ابعت "أكد" عشان أحجزلك 👍
أو لو حابب تعدل حاجة قولي.""")


def _execute_save_booking(sender_id, user_name, state):
    d = state['data'].copy()
    fb_name = get_facebook_user_name(sender_id)
    if (not d.get('name') or d['name'] in ["العميل", "..."]) and fb_name != "العميل":
        d['name'] = fb_name
    if not d.get('whatsapp'): d['whatsapp'] = d.get('phone', '')
    if not d.get('car'): d['car'] = 'سيدان'

    clean_data = {k: v for k, v in d.items() if k in ALLOWED_STATE_KEYS}
    missing = validate_booking_data(clean_data)
    if missing:
        state['step'] = 'collecting_contact'
        return _send_and_log(sender_id, "⚠️ لسه ناقص:\n" + "\n".join(f"• {f}" for f in missing) +
                             "\n\nابعتلي البيانات الناقصة 😊")

    print(f"💾 حفظ: {clean_data}")
    res = save_booking_to_sheet(clean_data)
    if not res.get('success'):
        return _send_and_log(sender_id, "❌ مشكلة تقنية. ممكن نحاول تاني؟")

    car = normalize_car_type(res.get('car', 'سيدان'))
    models = CAR_MODELS.get(car, {}).get('models', '')
    final = f"""✅ تم تأكيد الحجز بنجاح يا فندم! 🎉

🔢 كود الحجز: {res['booking_code']}
📅 التاريخ: {res['date']}
🕐 الوقت: {res['time']}
📍 من: {res['pickup']}
📍 إلى: {res['dropoff']}
🚗 السيارة: {car} ({models}) - {res['trip_type']}
👤 الاسم: {res['name']}
📱 موبايل: {res['phone']}
👥 الركاب: {res['pax']}
🧳 الشنط: {res['bags']}
💰 الإجمالي: {res['price']} جنيه

📞 24Seven: 01121747555 - 01007317927
رحلة سعيدة 🌹"""

    reset_user_state(sender_id)
    conversation_history[sender_id] = [{"role": "assistant", "content": final}]
    return final


# ==========================================
# 🤖 المحرك الرئيسي
# ==========================================

def handle_messenger_chat(sender_id, user_message, *args, **kwargs):
    global conversation_history

    if not user_message or not user_message.strip():
        return _send_and_log(sender_id, "أهلاً يا فندم! أقدر أساعدك في إيه؟ 😊")

    conversation_history.setdefault(sender_id, [])
    state = get_user_state(sender_id)
    user_name = get_facebook_user_name(sender_id)
    
    # Define initial state snapshots early to avoid NameError
    initial_pickup = state['data'].get('pickup')
    initial_dropoff = state['data'].get('dropoff')

    msg = user_message.strip()

    # ─── النوايا العامة ───
    confirm_kw = ["أيوه", "ايوه", "اه", "نعم", "تمام", "موافق", "أكد", "اكد",
                  "confirm", "ok", "yes", "صح", "مظبوط", "صحيح", "صحيحة", "صحيحه",
                  "احجز", "ماشي", "اوك", "يلا", "اكيد", "طبعا", "مناسب",
                  "خلاص", "توكلنا", "جود", "تم", "صحيحه أكد", "أكد الحجز", "اكد الحجز"]
    is_confirm = any(k in msg.lower() for k in confirm_kw)
    is_cancel = _is_cancel_request(msg)
    is_vague_route = _is_vague_route_request(msg)
    has_route_words = bool(re.search(r'(من\s+\S+|إلى\s+\S+|الى\s+\S+)', msg.lower()))
    is_price_question = any(w in msg.lower() for w in ["سعر", "بكام", "تكلفة", "تكلفه", "كام"])
    wants_new = _wants_new_inquiry(msg)

    # ═══════════════════════════════════════
    # 🔴 الغاء من أي مرحلة
    # ═══════════════════════════════════════
    if is_cancel and state['step'] in ['collecting_contact', 'summary_shown', 'price_offered', 'asking_pax']:
        _clear_route_keep_personal(state, sender_id)
        return _send_and_log(sender_id,
            "تمام يا فندم، مفيش مشكلة! 😊\nلو حبيت تسأل عن رحلة تانية أنا موجود.\n📞 24Seven: 01121747555")

    # ═══════════════════════════════════════
    # 🔴 طلب استفسار جديد من collecting_contact
    # ═══════════════════════════════════════
    is_trip_change = any(w in msg for w in ["ذهاب وعودة", "رايح جاي", "ذهاب وعوده", "رايح جاى", "اتجاه واحد", "ذهاب فقط", "توصيلة بس", "ذهاب و عودة", "ذهاب و عوده"])
    
    # قائمة مدن شائعة للكشف عنها لو لم يذكر "من/إلى"
    COMMON_CITIES = ['القاهرة', 'قاهرة', 'cairo', 'الاسكندريه', 'اسكندريه', 'alex', 'alexandria', 'شرم', 'sharm',
                     'الغردقة', 'غردقة', 'hurghada', 'الساحل', 'ساحل', 'سخنة', 'السخنة', 'sokhna', 'مطروح', 'matrouh',
                     'بورسعيد', 'سويس', 'اسماعيلية', 'العاصمة', 'عاصمة', 'التجمع', 'اكتوبر', 'زايد', 'مدينتي', 'رحاب',
                     'شروق', 'عبور', 'مطار', 'airport', 'وسط البلد', 'رمسيس', 'جيزة', 'هرم', 'فيصل', 'المعادي', 'مدينة نصر',
                     'المهندسين', 'دقي', 'زمالك', 'منيل', 'طوابق', 'عشرين', 'مريوطية']

    has_new_trip_intent = False
    if has_route_words: has_new_trip_intent = True
    elif any(w in msg for w in ["تفاصيل", "رحله اخرى", "رحلة اخري", "رحلة ثانية", "تعديل", "غير", "تغيير", "مكان تاني", "حجز تاني", "عرض تاني", "مشوار تاني"]): has_new_trip_intent = True
    elif any(c in msg for c in COMMON_CITIES): has_new_trip_intent = True

    if state['step'] in ['collecting_contact', 'price_offered', 'asking_pax'] and (wants_new or has_new_trip_intent) and not is_trip_change:
        # تأكد ان دي مش مجرد تعديل بسيط في نفس السياق (لو نفس المدن)
        # بس العميل عايز يبدأ جديد، فالأفضل نصفر
        _clear_route_keep_personal(state, sender_id)
        print(f"🔄 New inquiry detected (Context Switch) from {state['step']}")
        state['step'] = 'idle'  # Ensure step is idle
        # نكمل التدفق العادي بعد التصفير

    # ─── كشف خط جديد (idle / price_offered) ───
    if state['step'] not in ['summary_shown', 'collecting_contact']:
        should_clear = False
        if has_route_words: should_clear = True
        elif is_vague_route: should_clear = True
        elif is_price_question and not state['data'].get('pickup'): should_clear = True
        elif has_new_trip_intent and state['step'] == 'price_offered': should_clear = True

        if should_clear and (state['data'].get('pickup') or state['data'].get('dropoff')):
            old_p = state['data'].get('pickup', '')
            old_d = state['data'].get('dropoff', '')
            print(f"🔄 New route! Clearing: {old_p}→{old_d}")
            _clear_route_keep_personal(state, sender_id)

    print(f"📊 State [{sender_id}]: step={state['step']}, data_keys={list(state['data'].keys())}")

    # ─── استخراج بيانات Regex ───
    state['data']['old_car_for_check'] = state['data'].get('car')
    extract_data_from_message(msg, state['data'])

    # 🔄 تحديث "ذهاب وعودة" وتحديث السعر فورا
    trip_type_changed = False
    if re.search(r'(ذهاب\s*(و|و\s+)?\s*عود[هة]|رايح\s*جا[يى])', msg):
        state['data']['trip_type'] = "ذهاب وعودة"
        trip_type_changed = True
        print(f"🔄 Global Trip Type Changed to Round Trip: {state['data']['trip_type']}")
    elif re.search(r'(اتجاه\s*واحد|ذهاب\s*فقط|توصيل[هة]\s*بس)', msg):
        state['data']['trip_type'] = "ذهاب فقط"
        trip_type_changed = True

    # Force re-calc price if trip type changed OR if car changed in this step
    if trip_type_changed or state['data'].get('car') != state['data'].get('old_car_for_check'):
        # Lookup prices for current car
        car = normalize_car_type(state['data'].get('car', 'سيدان'))
        if state['data'].get('pickup') and state['data'].get('dropoff'):
            p1, pr = lookup_price(state['data']['pickup'], state['data']['dropoff'], car)
            if p1 and int(p1) > 0: state['data']['price_one_way'] = str(int(p1))
            if pr and int(pr) > 0: state['data']['price_round'] = str(int(pr))
            
            # Now set the main price
            if state['data'].get('trip_type') == "ذهاب وعودة":
                 pr = state['data'].get('price_round')
                 if pr and int(pr) > 0: 
                     state['data']['price'] = pr
                     print(f"💰 Force update price to ROUND: {pr}")
                 else:
                     # Fallback if round price missing but user insists on round trip
                     p1 = state['data'].get('price_one_way')
                     if p1 and int(p1) > 0:
                         est = str(int(p1) * 2)
                         state['data']['price'] = est
                         print(f"💰 Force update price to ROUND (Calculated): {est}")
            else:
                 if state['data'].get('price_one_way'): 
                     state['data']['price'] = state['data']['price_one_way']
                     print(f"💰 Force update price to ONE WAY: {state['data']['price']}")




    # ═══════════════════════════════════════
    # المرحلة 0: التأكيد النهائي
    # ═══════════════════════════════════════
    if state['step'] == 'summary_shown':
        if is_confirm:
            print(f"✅✅✅ SAVING...")
            return _execute_save_booking(sender_id, user_name, state)
        else:
            extract_data_from_message(msg, state['data'])
            _try_extract_name(msg, state['data'])
            return _show_summary(sender_id, user_name, state)

    # ═══════════════════════════════════════
    # المرحلة 0.5: سؤال عن المحافظة (لو مكنش عارف المكان)
    # ═══════════════════════════════════════
    if state['step'] == 'asking_governorate':
        return _handle_governorate_answer(sender_id, msg, state)

    # ═══════════════════════════════════════
    # المرحلة 1: جمع بيانات الحجز
    # ═══════════════════════════════════════
    if state['step'] == 'collecting_contact':
        extract_data_from_message(msg, state['data'])
        _try_extract_name(msg, state['data'])
        if not state['data'].get('whatsapp') and state['data'].get('phone'):
            state['data']['whatsapp'] = state['data']['phone']
        mm = _build_missing_fields_message(state['data'])
        if mm: return _send_and_log(sender_id, mm)
        ok, err = check_car_capacity(state['data'].get('car', 'سيدان'),
                                      state['data'].get('pax', '1'), state['data'].get('bags', '0'))
        if not ok: return _send_and_log(sender_id, err)
        return _show_summary(sender_id, user_name, state)

    # ═══════════════════════════════════════
    # كود حجز
    # ═══════════════════════════════════════
    code_match = re.search(r'\b([A-Z]{2,4}[-]?\d{4,8})\b', msg.upper())
    if code_match and state['step'] in ['idle', 'lookup_pending']:
        return _handle_booking_lookup(sender_id, code_match.group(1), state)
    if state['step'] == 'booking_found':
        return _handle_booking_modification(sender_id, msg, user_name, state)
    if state['step'] == 'cancel_reason':
        return _handle_cancel_reason(sender_id, msg, state)

    # ═══════════════════════════════════════
    # المرحلة 2: سؤال عن أفراد وشنط (بعد ما عرفنا المسار)
    # ═══════════════════════════════════════
    if state['step'] == 'asking_pax':
        extract_data_from_message(msg, state['data'])

        # لو لسه مبعتش → كرر السؤال
        if not state['data'].get('pax') or not state['data'].get('bags'):
            # حاول تفهم أرقام بسيطة
            nums = re.findall(r'\d+', msg)
            if len(nums) >= 2:
                state['data']['pax'] = nums[0]
                state['data']['bags'] = nums[1]
            elif len(nums) == 1:
                if not state['data'].get('pax'):
                    state['data']['pax'] = nums[0]
                elif not state['data'].get('bags'):
                    state['data']['bags'] = nums[0]

        if state['data'].get('pax') and state['data'].get('bags'):
            # عندنا كل حاجة → نعرض الأسعار
            return _show_all_prices(sender_id, state)
        else:
            pickup = state['data'].get('pickup', '')
            dropoff = state['data'].get('dropoff', '')
            return _send_and_log(sender_id,
                f"تمام يا فندم، رحلة من {pickup} إلى {dropoff} 👍\n\n"
                f"محتاج أعرف:\n👥 كام فرد؟\n🧳 كام شنطة؟\n\n"
                f"عشان أقدر أرشحلك السيارة المناسبة وأعرض الأسعار 😊")

    # ═══════════════════════════════════════
    # المرحلة 3: جمع المسار
    # ═══════════════════════════════════════
    if state['step'] in ['idle', 'collecting_route']:
        if not state['data'].get('pickup') or not state['data'].get('dropoff'):
            # تحية أو رسالة سبونسر بدون مسار
            if _is_greeting_only(msg) or _is_vague_route_request(msg):
                return _send_and_log(sender_id,
                    "أهلاً بيك يا فندم في 24Seven Limousine! 🚗✨\n\n"
                    "عندنا أسطول سيارات مجهز لراحتك:\n"
                    "🔹 سيدان (كورولا / سيراتو / النترا / تيبو)\n"
                    "🔹 مينى فان (اكسبندر / راش)\n"
                    "🔹 فان (تويوتا هاى اس / اتش ون)\n\n"
                    "عشان أساعدك محتاج أعرف:\n📍 حتتحرك منين؟\n📍 ورايح فين?\n👥 كام فرد؟\n🧳 كام شنطة?")

            instruction = f"""العميل قال: "{msg}"
استخرج مدينة التحرك والوصول (كلمة أو كلمتين فقط).
⚠️ لو مفيهاش مدن → لا تضع DETECT_DATA.
⚠️ لو ذكر مدينتين (مثل "اسكندرية مطار البرج") → pickup=الأولى, dropoff=الثانية.
DETECT_DATA: {{"pickup": "...", "dropoff": "..."}}"""
            reply = _ask_ai(sender_id, msg, user_name, instruction)
            if not state['data'].get('pickup') or not state['data'].get('dropoff'):
                return reply

    # --- 3. Refined Location Change / Reset Logic ---
    # If user changes location AFTER we already have it, we should reset downstream data
    # to avoid "stale" state (e.g. price for old route).
    if (state['data'].get('pickup') != initial_pickup) or (state['data'].get('dropoff') != initial_dropoff):
        print("📍 Location Changed - Resetting dependent data")
        for key in ['price', 'price_one_way', 'price_round', 'car', 'car_type', 'offer_sent', 'shared_offered']:
             state['data'].pop(key, None)
             
        # Optional: if major change, maybe reset step?
        if state['step'] in ['price_offered', 'collecting_contact', 'booking_confirmed']:
             state['step'] = 'collecting_route'
             
    # Detect "Shared Trip" intent and persist it
    if any(k in msg for k in ["مشترك", "مشاركه", "مشاركة", "كرسي", "شير", "share"]):
        state['data']['prefer_shared'] = True
        print("🚙 Shared Trip Preference Detected & Stored")

    # --- 4. Shared Trip Logic (Dynamic from Sheet) ---
    has_route = state['data'].get('pickup') and state['data'].get('dropoff')
    shared_price_found = 0
    
    if has_route:
        # Check against dynamic shared routes
        shared_price_found = lookup_shared_price(state['data']['pickup'], state['data']['dropoff'])

    # 4.1 Check for Shared Quantity/Intent explicitly
    if any(k in msg for k in ["مشترك", "مشتركه", "مشاركه", "مشاركة", "كرسي", "شير", "share"]):
        state['data']['prefer_shared'] = True
        print("🚙 Shared Trip Preference Detected & Stored")
        
        # If user explicitly asks for shared but we found NO shared route
        if has_route and not shared_price_found:
             return _send_and_log(sender_id, 
                 f"عفوا يا فندم، الرحلات المشتركة غير متاحة حالياً لهذا الخط ({state['data']['pickup']} - {state['data']['dropoff']}). متاح عندنا سيارات خاصة لمشوارك! 🚗\n"
                 f"تحب نكمل حجز ملاكي؟")
        
        # If no route yet, generic info
        if not has_route:
             return _send_and_log(sender_id,
                 f"الرحلات المشتركة متاحة لبعض الخطوط (مثل القاهرة-الاسكندرية). \n"
                 f"تحب تحجز؟ حضرتك هتتحرك منين؟")

    pax_count = 0
    if state['data'].get('pax'):
        try:
            pax_count = int(state['data']['pax'])
        except:
            pass
            
    # Check explicitly for "private" intent to suppress shared offer
    is_private_intent = "خاص" in msg or "مخصوص" in msg
    
    # Offer Shared if: Shared Route Found AND (Pax=1 OR Shared Intent)
    # And NOT already chosen car type (unless it WAS shared) or explicitly private
    if shared_price_found and not is_private_intent:
        should_offer_shared = False
        
        # If user explicitly asked for shared, offer it regardless of pax (assuming they know limits)
        if state['data'].get('prefer_shared'):
            should_offer_shared = True
        # Logic for implicit offer (1 pax)
        elif pax_count == 1 and not state['data'].get('car_type'):
            should_offer_shared = True
        
        # If user specifically asked for "Shared", ensure we offer it
        if any(k in msg for k in ["مشترك", "مشاركه", "مشاركة", "كرسي", "شير", "share", "فرد"]):
             should_offer_shared = True
             
        if should_offer_shared:
            # Construct Shared Offer
            # Use specific meeting points if Alex/Cairo, else generic
            pickup_loc = state['data'].get('pickup', '').lower()
            dropoff_loc = state['data'].get('dropoff', '').lower()
            
            # Simple check for Alex/Cairo mix to show meeting points
            # We can use robust check or simple string check
            is_alex_cairo_mix = ('alex' in pickup_loc or 'alex' in dropoff_loc or 'إسكندرية' in pickup_loc or 'اسكندرية' in pickup_loc) and \
                                ('cairo' in pickup_loc or 'cairo' in dropoff_loc or 'قاهرة' in pickup_loc)

            sched_text = "\n".join(SHARED_TRIP_DATA.get('schedule', [])) if is_alex_cairo_mix else "يتم تحديد المواعيد عند الحجز"
            
            shared_msg = (
                f"ℹ️ *متوفر رحلات مشتركة*\n"
                f"السعر: {shared_price_found} جنيه للفرد\n"
                f"المواعيد: {sched_text}\n"
            )
            
            if is_alex_cairo_mix and 'pickup_alex' in SHARED_TRIP_DATA:
                shared_msg += (
                    f"التجمع في الاسكندرية: {SHARED_TRIP_DATA['pickup_alex']}\n"
                    f"التجمع في القاهرة: {SHARED_TRIP_DATA['pickup_cairo']}\n"
                )
            
            shared_msg += "\nلحجز رحلة مشتركة، يرجى تحديد الموعد المناسب.\nأو يمكننا حجز سيارة خاصة لك (اختر نوع السيارة أدناه):"

            if not state.get('shared_offered'):
                 _send_and_log(sender_id, shared_msg)
                 state['shared_offered'] = True

    # ═══════════════════════════════════════
    # المرحلة 4: عندنا المسار → نسأل عن أفراد/شنط أو نعرض السعر
    # ═══════════════════════════════════════
    if state['data'].get('pickup') and state['data'].get('dropoff') and state['step'] in ['idle', 'collecting_route']:
        pickup = state['data']['pickup']
        dropoff = state['data']['dropoff']

        # لو pickup == dropoff
        pn = _normalize_city_name(pickup)
        dn = _normalize_city_name(dropoff)
        if pn.lower() == dn.lower():
            state['data'].pop('pickup', None)
            state['data'].pop('dropoff', None)
            state['step'] = 'idle'
            return _send_and_log(sender_id,
                f"يا فندم مكان التحرك والوصول واحد ({pn})! 😅\n"
                f"ممكن توضحلي:\n📍 حتتحرك منين؟\n📍 ورايح فين؟")

        # لو عندنا pax + bags → نعرض كل الأسعار مباشرة
        if state['data'].get('pax') and state['data'].get('bags'):
            state['step'] = 'asking_pax'  # هنقفز لعرض الأسعار
            return _show_all_prices(sender_id, state)

        # محتاج نسأل عن أفراد/شنط أولاً
        state['step'] = 'asking_pax'
        return _send_and_log(sender_id,
            f"✅ تمام يا فندم!\n📍 من: {pickup}\n📍 إلى: {dropoff}\n\n"
            f"عشان أرشحلك السيارة المناسبة وأعرض الأسعار:\n"
            f"👥 كام فرد؟\n🧳 كام شنطة؟")

    # (Logic moved up)

    # ═══════════════════════════════════════
    # المرحلة 5: رد على السعر (اختيار نوع سيارة)
    # ═══════════════════════════════════════
    if state['step'] == 'price_offered':
        # لو اختار نوع سيارة
        for ct, kws in {'سيدان': ['سيدان', 'كورولا', 'سيراتو', 'النترا', 'تيبو', 'sedan', 'عادي', 'عاديه'],
                        'مينى فان': ['ميني', 'مينى', 'منى', 'اكسبندر', 'راش', 'xpander', 'mini'],
                        'فان': ['فان', 'هاي اس', 'هاى اس', 'h1', 'hiace', 'باص', 'van']}.items():
            if any(kw in msg.lower() for kw in kws):
                state['data']['car'] = ct
                p, pr = lookup_price(state['data']['pickup'], state['data']['dropoff'], ct)
                if p and int(p) > 0:
                    state['data']['price_one_way'] = str(int(p))
                    if pr and int(pr) > 0: state['data']['price_round'] = str(int(pr))

                    # Set price based on current trip_type
                    if state['data'].get('trip_type') == "ذهاب وعودة" and state['data'].get('price_round'):
                        state['data']['price'] = state['data']['price_round']
                    else:
                        state['data']['price'] = str(int(p))
                break

        if re.search(r'(اتجاه\s*واحد|ذهاب\s*فقط|توصيل[هة]\s*بس)', msg):
            state['data']['trip_type'] = "ذهاب فقط"
            is_confirm = True
        elif re.search(r'(ذهاب\s*(و|و\s+)?\s*عود[هة]|رايح\s*جا[يى])', msg):
            state['data']['trip_type'] = "ذهاب وعودة"
            print(f"🔄 Trip Type Changed via Regex: {state['data']['trip_type']}")
            if state['data'].get('price_round'):
                 state['data']['price'] = state['data']['price_round']
                 print(f"💰 Price offered round trip selected: {state['data']['price']}")
            is_confirm = True

        has_data = state['data'].get('phone') or state['data'].get('date') or state['data'].get('time')
        if is_confirm or has_data or state['data'].get('car'):
            state['step'] = 'collecting_contact'
            mm = _build_missing_fields_message(state['data'])
            if mm: return _send_and_log(sender_id, mm)
            return _show_summary(sender_id, user_name, state)
        elif any(k in msg.lower() for k in ["غالي", "كتير", "رفض", "مش عايز", "غالية"]):
            return _ask_ai(sender_id, msg, user_name,
                "العميل شايف السعر غالي. اشرح مميزات الخدمة: سيارات موديل حديث، سواق محترف، راحة وأمان، التزام بالمواعيد.")
        else:
            return _ask_ai(sender_id, msg, user_name, "جاوب العميل. لو وافق اسأله يختار نوع السيارة.")

    # Fallback
    return _ask_ai(sender_id, msg, user_name,
        "ساعد العميل. لو عايز يحجز أو يستفسر، اسأله يتحرك منين ورايح فين وكام فرد وكام شنطة.")


def _show_all_prices(sender_id, state):
    """عرض أسعار كل السيارات المتاحة للمسار"""
    pickup = state['data']['pickup']
    dropoff = state['data']['dropoff']
    pax = state['data'].get('pax', '1')
    bags = state['data'].get('bags', '0')

    all_prices = lookup_all_car_prices(pickup, dropoff)

    if not all_prices:
        # ⚠️ لم نجد سعراً -> قد يكون المكان غير معروف
        # نحاول تحديد أيهما غير معروف (pickup أو dropoff)
        if not _is_city_known(pickup):
             state['step'] = 'asking_governorate'
             state['unknown_city'] = pickup
             state['target_field'] = 'pickup'
             return _send_and_log(sender_id, f"معلش يا فندم، \"{pickup}\" تبع محافظة إيه؟ 🤔\n(مثلاً: القاهرة، الجيزة، الإسكندرية...)")
        
        if not _is_city_known(dropoff):
             state['step'] = 'asking_governorate'
             state['unknown_city'] = dropoff
             state['target_field'] = 'dropoff'
             return _send_and_log(sender_id, f"معلش يا فندم، \"{dropoff}\" تبع محافظة إيه؟ 🤔")

        _clear_route_keep_personal(state, sender_id)
        return _send_and_log(sender_id,
            f"عذراً يا فندم، الرحلة من {pickup} إلى {dropoff} مش متاحة حالياً.\n\n"
            f"📞 تواصل مع خدمة العملاء:\n01121747555 - 01007317927\n\n"
            f"أو اسأل عن خط تاني! 😊")

    recommended = _recommend_car(pax, bags)
    if recommended not in all_prices:
        recommended = list(all_prices.keys())[0]

    # حفظ السعر الافتراضي (التوصية)
    rec_prices = all_prices[recommended]
    state['data']['car'] = recommended
    state['data']['price'] = str(rec_prices['one_way'])
    if rec_prices['round_trip']: state['data']['price_round'] = str(rec_prices['round_trip'])
    state['step'] = 'price_offered'

    price_msg = _build_price_display(pickup, dropoff, all_prices, recommended, pax, bags)
    return _send_and_log(sender_id, price_msg)


def _handle_governorate_answer(sender_id, msg, state):
    """معالجة إجابة العميل عن المحافظة"""
    gov = _extract_city_from_text(msg)
    if not gov:
        return _send_and_log(sender_id, "معلش ممكن توضح اسم المحافظة؟ (القاهرة، الجيزة، الاسكندرية، الساحل...)")
    
    # Normalize to canonical
    gov_norm = _normalize_city_name(gov)

    target = state.get('target_field')
    original = state.get('unknown_city')
    
    if target and original:
        new_loc = f"{original}, {gov_norm}"
        state['data'][target] = new_loc
    
    state['step'] = 'asking_pax'
    return _show_all_prices(sender_id, state)



# ==========================================
# 🔍 حجز / تعديل / إلغاء
# ==========================================

def _handle_booking_lookup(sender_id, code, state):
    info = find_booking_by_code(code)
    if info:
        state['step'] = 'booking_found'; state['booking_code'] = code; state['booking_info'] = info
        return _send_and_log(sender_id,
            f"✅ لقيت الحجز ({code}):\n📅 {info['date']} 🕐 {info['time']}\n"
            f"📍 {info['pickup']} → {info['dropoff']}\n🚗 {info['car']} 👥 {info['pax']} 🧳 {info['bags']}\n"
            f"💰 {info['price']} ج | {info['status']}\n\nتحب تعدل ولا تلغي؟")
    return _send_and_log(sender_id, f"مفيش حجز بالكود ({code}). ممكن تتأكد؟")


def _handle_booking_modification(sender_id, msg, user_name, state):
    if any(w in msg.lower() for w in ["الغ", "لغي", "إلغاء", "حذف", "كنسل", "cancel"]):
        state['step'] = 'cancel_reason'
        return _send_and_log(sender_id, "قبل ما نلغي، ممكن السبب؟ 🙏")
    code = state.get('booking_code', '')
    info = state.get('booking_info', {})
    instruction = f"""أنت "أحمد" موظف حجز. ردك لازم يكون مصري ولطيف.
حجز كود {code}. تاريخ={info.get('date')}, وقت={info.get('time')}, من={info.get('pickup')}, إلى={info.get('dropoff')}
العميل: "{msg}"
لو تعديل: UPDATE_BOOKING: {{"code": "{code}", "action": "modify", "updates": {{"field": "value"}}}}
لو استفسار فقط: جاوب العميل بلهجة مصرية."""
    conversation_history.setdefault(sender_id, []).append({"role": "user", "content": msg})
    reply = call_claude_api(instruction, conversation_history[sender_id][-5:])
    if not reply: return _send_and_log(sender_id, "حصل خطأ. حاول تاني؟")
    if "UPDATE_BOOKING:" in reply:
        try:
            m = re.search(r'\{[^}]*\}', reply.split("UPDATE_BOOKING:")[1])
            if m:
                cmd = json.loads(m.group(0))
                ok, rm = update_booking_in_sheet(cmd.get('code', code), cmd.get('action', 'modify'), cmd.get('updates', {}))
                return _send_and_log(sender_id, f"✅ {rm}" if ok else f"❌ {rm}")
        except: pass
    clean = reply.split("UPDATE_BOOKING:")[0].strip() or "تمام!"
    return _send_and_log(sender_id, clean)


def _handle_cancel_reason(sender_id, reason, state):
    code = state.get('booking_code', '')
    if not code: return _send_and_log(sender_id, "محتاج كود الحجز.")
    ok, m = update_booking_in_sheet(code, "cancel", reason=reason)
    reset_user_state(sender_id)
    return _send_and_log(sender_id, f"✅ تم إلغاء ({code}). 🙏" if ok else f"❌ {m}")


# ==========================================
# 🎮 دوال التحكم
# ==========================================

def pause_bot(sender_id, emp_name="موظف"):
    bot_paused[sender_id] = True; employee_name[sender_id] = emp_name

def resume_bot(sender_id):
    bot_paused[sender_id] = False; employee_name.pop(sender_id, None); reset_user_state(sender_id)

def is_bot_paused(sender_id):
    return bot_paused.get(sender_id, False)

def end_conversation_by_employee(sender_id):
    resume_bot(sender_id)
    return "شكراً لتواصلك! ⭐ ممكن تقيم خدمتنا من 1 لـ 5؟"

def save_rating_to_sheet(sender_id, rating):
    try:
        client = get_client()
        try: ws = client.open_by_url(SHEET_URL).worksheet("تقييمات الموظفين")
        except: ws = client.open_by_url(SHEET_URL).get_worksheet(0)
        ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), str(sender_id), str(rating), "Messenger", ""])
    except Exception as e: print(f"❌ Rating Error: {e}")


# ==========================================
# 🔌 Compatibility Wrapper for WhatsApp
# ==========================================

def chat_with_ai(user_phone, user_message):
    """
    Wrapper to make messenger_agent logic compatible with ai_agent interface.
    Used by webhook_server.py for WhatsApp.
    """
    # handle_messenger_chat returns the response text directly
    # We pass user_phone as sender_id
    return handle_messenger_chat(user_phone, user_message)

if __name__ == "__main__": 
    print("🤖 AI Agent (Synced with Messenger Agent) Started...")