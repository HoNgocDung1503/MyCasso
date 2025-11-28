"""
Module quản lý thông tin sản phẩm - JSON-ONLY MODE
✅ Tất cả sản phẩm load từ JSON
✅ Xóa là xóa vĩnh viễn, không bao giờ quay lại
"""
from typing import Dict, List, Optional
from pydantic import BaseModel
import re
import json
import os

# ============ FILE LƯU TRỮ ============
CUSTOM_PRODUCTS_FILE = "custom_products.json"

# ============ THÔNG TIN QUÁN ============

STORE_INFO = {
    "name": "Quán Ăn Ngon",
    "address": "123 Đường Lê Lợi, Phường Bến Thành, Quận 1, TP. Hồ Chí Minh",
    "phone": "0862 968 980",
    "hours": {
        "monday_friday": "6:00 - 22:00",
        "saturday_sunday": "6:00 - 23:00"
    },
    "delivery": True,
    "payment_methods": ["Tiền mặt", "Chuyển khoản", "QR Code"],
    "social": {
        "facebook": "facebook.com/hodung",
        "zalo": "0862 968 980"
    }
}

def get_store_info() -> dict:
    return STORE_INFO

def get_store_address() -> str:
    return STORE_INFO["address"]

def get_store_hours() -> str:
    hours = STORE_INFO["hours"]
    return f"Thứ 2-6: {hours['monday_friday']}\nThứ 7-CN: {hours['saturday_sunday']}"

def format_store_info() -> str:
    info = STORE_INFO
    return f"""📍 {info['name']}
Địa chỉ: {info['address']}
Điện thoại: {info['phone']}

⏰ Giờ mở cửa:
{get_store_hours()}

💳 Thanh toán: {', '.join(info['payment_methods'])}
🚚 Giao hàng: {'Có' if info['delivery'] else 'Không'}"""

# ============ PYDANTIC MODELS ============

class Product(BaseModel):
    id: str
    name: str
    price: float
    unit: str
    category: str
    available: bool = True
    is_custom: bool = True

class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    unit: str
    subtotal: float

class PaymentResponse(BaseModel):
    items: List[OrderItem]
    total_amount: float
    currency: str = "VND"
    success: bool
    message: str
    unavailable_items: List[str] = []

# ============ DATABASE SẢN PHẨM ĐỘNG ============
# ✅ TẤT CẢ load từ JSON, KHÔNG CÒN hard-code
PRODUCTS_DB: Dict[str, Product] = {}

# ============ LOAD/SAVE PRODUCTS ============

def load_custom_products():
    """Load TẤT CẢ products từ file JSON"""
    global PRODUCTS_DB
    try:
        if os.path.exists(CUSTOM_PRODUCTS_FILE):
            with open(CUSTOM_PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                PRODUCTS_DB = {}
                for pid, pdata in data.items():
                    PRODUCTS_DB[pid] = Product(**pdata)
            print(f"✅ Loaded {len(PRODUCTS_DB)} products from {CUSTOM_PRODUCTS_FILE}")
        else:
            print(f"⚠️ {CUSTOM_PRODUCTS_FILE} not found, creating empty database")
            PRODUCTS_DB = {}
    except Exception as e:
        print(f"⚠️ Error loading products: {e}")
        PRODUCTS_DB = {}

def save_custom_products():
    """Save TẤT CẢ products vào file JSON"""
    try:
        data = {pid: p.model_dump() for pid, p in PRODUCTS_DB.items()}
        with open(CUSTOM_PRODUCTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved {len(data)} products to {CUSTOM_PRODUCTS_FILE}")
    except Exception as e:
        print(f"⚠️ Error saving products: {e}")

# Load products khi module được import
load_custom_products()

# ============ HELPER: GET DATABASE ============

def get_all_products_db() -> Dict[str, Product]:
    """Trả về TẤT CẢ products"""
    return PRODUCTS_DB

def get_menu_from_json() -> List[Product]:
    """Load menu từ JSON"""
    load_custom_products()
    return list(PRODUCTS_DB.values())

# ============ MAPPING TỪ KHÓA ============

BASE_PRODUCT_KEYWORDS = {
    "bánh mì sữa": "banh_mi_sua",
    "banh mi sua": "banh_mi_sua",
    "bánh mì thịt": "banh_mi_thit",
    "banh mi thit": "banh_mi_thit",
    "bánh mì trứng": "banh_mi_trung",
    "banh mi trung": "banh_mi_trung",
    "sữa đậu nành": "sua_dau_nanh",
    "sua dau nanh": "sua_dau_nanh",
    "bánh mì": "banh_mi",
    "banh mi": "banh_mi",
    "phở": "pho",
    "pho": "pho",
    "bún bò": "bun_bo",
    "bun bo": "bun_bo",
    "sữa": "sua",
    "sua": "sua",
    "nước ngọt": "nuoc_ngot",
    "nuoc ngot": "nuoc_ngot",
    "trà sữa": "tra_sua",
    "tra sua": "tra_sua",
    "cà phê": "ca_phe",
    "ca phe": "ca_phe",
    "cafe": "ca_phe",
    "coffee": "ca_phe",
    "nước suối": "nuoc_suoi",
    "nuoc suoi": "nuoc_suoi",
    "snack": "snack",
    "kẹo": "keo",
    "keo": "keo",
    "bánh quy": "banh_quy",
    "banh quy": "banh_quy",
    "táo": "tao",
    "tao": "tao",
    "chuối": "chuoi",
    "chuoi": "chuoi",
    "cam": "cam",
    "rau": "rau",
    "khoai tây": "khoai_tay",
    "khoai tay": "khoai_tay",
}

def get_all_keywords() -> Dict[str, str]:
    """Merge base + custom keywords"""
    merged = BASE_PRODUCT_KEYWORDS.copy()
    for product in PRODUCTS_DB.values():
        name_lower = product.name.lower()
        merged[name_lower] = product.id
    return merged

# ============ DYNAMIC PRODUCT MANAGEMENT ============

def add_product(name: str, price: float, unit: str = "cái", category: str = "Khác") -> dict:
    try:
        name = name.strip()
        
        all_products = get_all_products_db()
        for existing_product in all_products.values():
            if existing_product.name.lower() == name.lower():
                return {
                    "success": False,
                    "message": f"Sản phẩm '{name}' đã tồn tại!",
                    "product_id": None
                }
        
        product_id = re.sub(r'[^\w\s]', '', name.lower())
        product_id = re.sub(r'\s+', '_', product_id)
        
        counter = 1
        original_id = product_id
        while product_id in all_products:
            product_id = f"{original_id}_{counter}"
            counter += 1
        
        new_product = Product(
            id=product_id,
            name=name,
            price=price,
            unit=unit,
            category=category,
            available=True,
            is_custom=True
        )
        
        PRODUCTS_DB[product_id] = new_product
        save_custom_products()
        
        print(f"✅ Added product: {name} (ID: {product_id}, Price: {price}đ/{unit})")
        
        return {
            "success": True,
            "message": f"Đã thêm món '{name}' với giá {format_price(price)}/{unit}",
            "product_id": product_id
        }
        
    except Exception as e:
        print(f"❌ Error adding product: {e}")
        return {
            "success": False,
            "message": f"Lỗi khi thêm món: {str(e)}",
            "product_id": None
        }

def remove_product(product_name_or_id: str) -> dict:
    """XÓA SẢN PHẨM - Fuzzy matching"""
    try:
        product_name_or_id = product_name_or_id.strip()
        
        all_products = get_all_products_db()
        product = None
        product_id = None
        
        if product_name_or_id in all_products:
            product_id = product_name_or_id
            product = all_products[product_id]
        else:
            search_name = product_name_or_id.lower().strip()
            
            import unicodedata
            def remove_accents(text):
                return ''.join(
                    c for c in unicodedata.normalize('NFD', text)
                    if unicodedata.category(c) != 'Mn'
                )
            
            search_name_no_accent = remove_accents(search_name)
            
            for pid, p in all_products.items():
                product_name_lower = p.name.lower().strip()
                product_name_no_accent = remove_accents(product_name_lower)
                
                if (product_name_lower == search_name or 
                    product_name_no_accent == search_name_no_accent or
                    search_name in product_name_lower or
                    search_name_no_accent in product_name_no_accent):
                    product_id = pid
                    product = p
                    break
        
        if not product:
            return {
                "success": False,
                "message": f"Không tìm thấy món '{product_name_or_id}'"
            }
        
        # ✅ XÓA KHỎI PRODUCTS_DB
        if product_id in PRODUCTS_DB:
            del PRODUCTS_DB[product_id]
        
        # ✅ LƯU VÀO JSON
        save_custom_products()
        
        print(f"✅ Removed product: {product.name} (ID: {product_id})")
        
        return {
            "success": True,
            "message": f"Đã xóa món '{product.name}'",
            "product_name": product.name
        }
        
    except Exception as e:
        print(f"❌ Error removing product: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Lỗi khi xóa món: {str(e)}"
        }

def update_product_price(product_name_or_id: str, new_price: float) -> dict:
    """
    CẬP NHẬT GIÁ SẢN PHẨM - FUZZY MATCHING
    """
    try:
        all_products = get_all_products_db()
        product = None
        product_id = None
        
        # Tìm theo ID (chính xác)
        if product_name_or_id in all_products:
            product_id = product_name_or_id
            product = all_products[product_id]
        else:
            # ✅ FUZZY MATCHING - Tìm theo tên
            search_name = product_name_or_id.lower().strip()
            
            # Bỏ dấu để so sánh
            import unicodedata
            def remove_accents(text):
                return ''.join(
                    c for c in unicodedata.normalize('NFD', text)
                    if unicodedata.category(c) != 'Mn'
                )
            
            search_name_no_accent = remove_accents(search_name)
            
            # Bỏ đơn vị khỏi search (tô, cái, ly, hộp...)
            search_name_cleaned = search_name.replace("tô", "").replace("cái", "").replace("ly", "")
            search_name_cleaned = search_name_cleaned.replace("hộp", "").replace("chai", "")
            search_name_cleaned = search_name_cleaned.replace("gói", "").replace("kg", "").strip()
            
            search_name_cleaned_no_accent = remove_accents(search_name_cleaned)
            
            for pid, p in all_products.items():
                product_name_lower = p.name.lower().strip()
                product_name_no_accent = remove_accents(product_name_lower)
                
                # Match nhiều cách:
                # 1. Chính xác
                # 2. Không dấu
                # 3. Chứa trong tên (search in product name)
                # 4. Product name chứa trong search
                if (product_name_lower == search_name or 
                    product_name_no_accent == search_name_no_accent or
                    search_name_cleaned in product_name_lower or
                    product_name_lower in search_name_cleaned or
                    search_name_cleaned_no_accent in product_name_no_accent or
                    product_name_no_accent in search_name_cleaned_no_accent):
                    product_id = pid
                    product = p
                    break
        
        if not product:
            return {
                "success": False,
                "message": f"Không tìm thấy món '{product_name_or_id}'"
            }
        
        old_price = product.price
        product.price = new_price
        
        # Cập nhật vào DB
        PRODUCTS_DB[product_id] = product
        save_custom_products()
        
        print(f"✅ Updated price: {product.name}: {old_price}đ → {new_price}đ")
        
        return {
            "success": True,
            "message": f"Đã cập nhật giá món '{product.name}' từ {format_price(old_price)} thành {format_price(new_price)}"
        }
        
    except Exception as e:
        print(f"❌ Error updating product: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Lỗi khi cập nhật giá: {str(e)}"
        }

# ============ HELPER FUNCTIONS ============

def get_product_by_id(product_id: str) -> Optional[Product]:
    return PRODUCTS_DB.get(product_id)

def get_product_by_keyword(keyword: str) -> Optional[Product]:
    keyword_lower = keyword.lower().strip()
    all_keywords = get_all_keywords()
    product_id = all_keywords.get(keyword_lower)
    if product_id:
        return get_product_by_id(product_id)
    return None

def search_products(query: str) -> List[Product]:
    query_lower = query.lower()
    results = []
    all_products = get_all_products_db()
    
    for keyword, product_id in get_all_keywords().items():
        if query_lower in keyword:
            product = all_products.get(product_id)
            if product and product not in results:
                results.append(product)
    
    for product in all_products.values():
        if query_lower in product.name.lower() and product not in results:
            results.append(product)
    
    return results

def get_all_products() -> List[Product]:
    load_custom_products()
    return list(PRODUCTS_DB.values())

def get_products_by_category(category: str) -> List[Product]:
    return [p for p in PRODUCTS_DB.values() if p.category == category]

def format_price(price: float) -> str:
    return f"{int(price):,}đ".replace(",", ".")

def calculate_total(items: List[OrderItem]) -> float:
    return sum(item.subtotal for item in items)

# ============ PAYMENT FUNCTION ============

def process_payment_request(user_message: str) -> dict:
    message_lower = user_message.lower()
    order_items = []
    unavailable_items = []
    
    text = message_lower
    text = re.sub(r'[.,!?;:]', '', text)
    text = text.replace("tôi muốn", "").replace("cho tôi", "").replace("tôi cần", "")
    text = text.replace("mua", "").replace("đặt", "").replace("order", "")
    text = text.replace("thanh toán", "").replace("thành toán", "").replace("tính tiền", "")
    text = text.replace("lấy", "").replace("gọi", "").replace("tính thêm", "").replace("thêm", "")
    text = text.strip()
    
    text = convert_number_words(text)
    items_parts = re.split(r'\s+và\s+|,', text)
    
    for part in items_parts:
        part = part.strip()
        if not part:
            continue
        
        number_match = re.search(r'(\d+)', part)
        if number_match:
            quantity = int(number_match.group(1))
            remaining = part[number_match.end():].strip()
            remaining = remaining.replace("cái", "").replace("hộp", "").replace("chai", "")
            remaining = remaining.replace("ly", "").replace("tô", "").replace("gói", "")
            remaining = remaining.replace("kg", "").replace("bó", "").strip()
            
            found = False
            words = remaining.split()
            
            for length in range(len(words), 0, -1):
                for start_idx in range(len(words) - length + 1):
                    phrase = " ".join(words[start_idx:start_idx + length])
                    product = get_product_by_keyword(phrase)
                    
                    if product:
                        if product.available:
                            subtotal = product.price * quantity
                            order_item = OrderItem(
                                product_id=product.id,
                                product_name=product.name,
                                quantity=quantity,
                                unit_price=product.price,
                                unit=product.unit,
                                subtotal=subtotal
                            )
                            order_items.append(order_item)
                            found = True
                            break
                        else:
                            unavailable_items.append(product.name)
                            found = True
                            break
                
                if found:
                    break
    
    total_amount = calculate_total(order_items)
    
    if order_items:
        success = True
        message = f"Đơn hàng của bạn:\n"
        for item in order_items:
            message += f"- {item.quantity} {item.unit} {item.product_name}: {format_price(item.subtotal)}\n"
        message += f"\nTổng cộng: {format_price(total_amount)}"
        
        if unavailable_items:
            message += f"\n\nSản phẩm không có sẵn: {', '.join(unavailable_items)}"
    else:
        success = False
        message = "Không tìm thấy sản phẩm nào trong yêu cầu của bạn."
    
    payment_response = PaymentResponse(
        items=order_items,
        total_amount=total_amount,
        success=success,
        message=message,
        unavailable_items=unavailable_items
    )
    
    return payment_response.model_dump()

def convert_number_words(text: str) -> str:
    number_map = {
        "một": "1", "hai": "2", "ba": "3", "bốn": "4", "năm": "5",
        "sáu": "6", "bảy": "7", "tám": "8", "chín": "9", "mười": "10",
        "mot": "1", "bon": "4", "nam": "5", "sau": "6", "bay": "7",
        "tam": "8", "chin": "9", "muoi": "10",
        "hai mươi": "20", "ba mươi": "30", "bốn mươi": "40", "năm mươi": "50"
    }
    
    result = text
    for word, num in sorted(number_map.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = r'\b' + re.escape(word) + r'\b'
        result = re.sub(pattern, num, result)
    
    return result