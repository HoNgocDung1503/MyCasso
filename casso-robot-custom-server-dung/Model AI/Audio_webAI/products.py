"""
Module quản lý thông tin sản phẩm và giá
"""
from typing import Dict, List, Optional
from pydantic import BaseModel

# ============ PYDANTIC MODELS ============

class Product(BaseModel):
    """Model cho một sản phẩm"""
    id: str
    name: str
    price: float
    unit: str  # đơn vị: cái, hộp, chai, kg, etc.
    category: str
    available: bool = True

class OrderItem(BaseModel):
    """Model cho một item trong đơn hàng"""
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    unit: str
    subtotal: float

class PaymentResponse(BaseModel):
    """Structured response cho thanh toán"""
    items: List[OrderItem]
    total_amount: float
    currency: str = "VND"
    success: bool
    message: str
    unavailable_items: List[str] = []

# ============ DATABASE SẢN PHẨM ============

PRODUCTS_DB: Dict[str, Product] = {
    # Bánh mì & Thức ăn nhanh
    "banh_mi": Product(
        id="banh_mi",
        name="Bánh mì",
        price=15000,
        unit="cái",
        category="Thức ăn"
    ),
    "banh_mi_thit": Product(
        id="banh_mi_thit",
        name="Bánh mì thịt",
        price=20000,
        unit="cái",
        category="Thức ăn"
    ),
    "banh_mi_trung": Product(
        id="banh_mi_trung",
        name="Bánh mì trứng",
        price=18000,
        unit="cái",
        category="Thức ăn"
    ),
    "pho": Product(
        id="pho",
        name="Phở",
        price=45000,
        unit="tô",
        category="Thức ăn"
    ),
    "bun_bo": Product(
        id="bun_bo",
        name="Bún bò",
        price=40000,
        unit="tô",
        category="Thức ăn"
    ),
    
    # Đồ uống
    "sua": Product(
        id="sua",
        name="Sữa",
        price=12000,
        unit="hộp",
        category="Đồ uống"
    ),
    "sua_dau_nanh": Product(
        id="sua_dau_nanh",
        name="Sữa đậu nành",
        price=10000,
        unit="hộp",
        category="Đồ uống"
    ),
    "nuoc_ngot": Product(
        id="nuoc_ngot",
        name="Nước ngọt",
        price=15000,
        unit="chai",
        category="Đồ uống"
    ),
    "tra_sua": Product(
        id="tra_sua",
        name="Trà sữa",
        price=30000,
        unit="ly",
        category="Đồ uống"
    ),
    "ca_phe": Product(
        id="ca_phe",
        name="Cà phê",
        price=25000,
        unit="ly",
        category="Đồ uống"
    ),
    "nuoc_suoi": Product(
        id="nuoc_suoi",
        name="Nước suối",
        price=8000,
        unit="chai",
        category="Đồ uống"
    ),
    
    # Snack & Bánh kẹo
    "snack": Product(
        id="snack",
        name="Snack",
        price=10000,
        unit="gói",
        category="Snack"
    ),
    "keo": Product(
        id="keo",
        name="Kẹo",
        price=5000,
        unit="gói",
        category="Snack"
    ),
    "banh_quy": Product(
        id="banh_quy",
        name="Bánh quy",
        price=20000,
        unit="hộp",
        category="Snack"
    ),
    
    # Trái cây
    "tao": Product(
        id="tao",
        name="Táo",
        price=30000,
        unit="kg",
        category="Trái cây"
    ),
    "chuoi": Product(
        id="chuoi",
        name="Chuối",
        price=15000,
        unit="kg",
        category="Trái cây"
    ),
    "cam": Product(
        id="cam",
        name="Cam",
        price=40000,
        unit="kg",
        category="Trái cây"
    ),
    
    # Rau củ
    "rau": Product(
        id="rau",
        name="Rau",
        price=10000,
        unit="bó",
        category="Rau củ"
    ),
    "khoai_tay": Product(
        id="khoai_tay",
        name="Khoai tây",
        price=20000,
        unit="kg",
        category="Rau củ"
    ),
}

# ============ MAPPING TỪ KHÓA ============

# Mapping từ các từ khóa tiếng Việt -> product_id
PRODUCT_KEYWORDS = {
    # Bánh mì (bao gồm các biến thể phát âm Whisper hay nhầm)
    "bánh mì": "banh_mi",
    "banh mi": "banh_mi",
    "bánh mỳ": "banh_mi",
    "bánh bì": "banh_mi",  # Whisper transcribe sai
    "banh bi": "banh_mi",
    "bánh mỳ": "banh_mi",
    "bánh mì thịt": "banh_mi_thit",
    "banh mi thit": "banh_mi_thit",
    "bánh bì thịt": "banh_mi_thit",  # Biến thể
    "bánh mì trứng": "banh_mi_trung",
    "banh mi trung": "banh_mi_trung",
    "bánh bì trứng": "banh_mi_trung",  # Biến thể
    
    # Món ăn
    "phở": "pho",
    "pho": "pho",
    "phở bò": "pho",  # Biến thể
    "fo": "pho",  # Whisper có thể transcribe sai
    "bún bò": "bun_bo",
    "bun bo": "bun_bo",
    "bún": "bun_bo",
    
    # Đồ uống
    "sữa": "sua",
    "sua": "sua",
    "sửa": "sua",  # Biến thể
    "sữa đậu nành": "sua_dau_nanh",
    "sua dau nanh": "sua_dau_nanh",
    "sữa đậu": "sua_dau_nanh",
    "nước ngọt": "nuoc_ngot",
    "nuoc ngot": "nuoc_ngot",
    "nước": "nuoc_ngot",  # Ngắn gọn
    "coca": "nuoc_ngot",
    "pepsi": "nuoc_ngot",
    "sting": "nuoc_ngot",
    "trà sữa": "tra_sua",
    "tra sua": "tra_sua",
    "trà": "tra_sua",
    "cà phê": "ca_phe",
    "ca phe": "ca_phe",
    "cafe": "ca_phe",
    "coffee": "ca_phe",
    "cà phê đá": "ca_phe",
    "cà phê sữa": "ca_phe",
    "nước suối": "nuoc_suoi",
    "nuoc suoi": "nuoc_suoi",
    "nước khoáng": "nuoc_suoi",
    
    # Snack
    "snack": "snack",
    "kẹo": "keo",
    "keo": "keo",
    "bánh quy": "banh_quy",
    "banh quy": "banh_quy",
    
    # Trái cây
    "táo": "tao",
    "tao": "tao",
    "chuối": "chuoi",
    "chuoi": "chuoi",
    "cam": "cam",
    
    # Rau củ
    "rau": "rau",
    "khoai tây": "khoai_tay",
    "khoai tay": "khoai_tay",
}

# ============ HELPER FUNCTIONS ============

def get_product_by_id(product_id: str) -> Optional[Product]:
    """Lấy sản phẩm theo ID"""
    return PRODUCTS_DB.get(product_id)

def get_product_by_keyword(keyword: str) -> Optional[Product]:
    """Tìm sản phẩm theo từ khóa"""
    keyword_lower = keyword.lower().strip()
    product_id = PRODUCT_KEYWORDS.get(keyword_lower)
    if product_id:
        return PRODUCTS_DB.get(product_id)
    return None

def search_products(query: str) -> List[Product]:
    """Tìm kiếm sản phẩm theo query (fuzzy search)"""
    query_lower = query.lower()
    results = []
    
    # Tìm trong keywords
    for keyword, product_id in PRODUCT_KEYWORDS.items():
        if query_lower in keyword:
            product = PRODUCTS_DB.get(product_id)
            if product and product not in results:
                results.append(product)
    
    # Tìm trong tên sản phẩm
    for product in PRODUCTS_DB.values():
        if query_lower in product.name.lower() and product not in results:
            results.append(product)
    
    return results

def get_all_products() -> List[Product]:
    """Lấy tất cả sản phẩm"""
    return list(PRODUCTS_DB.values())

def get_products_by_category(category: str) -> List[Product]:
    """Lấy sản phẩm theo danh mục"""
    return [p for p in PRODUCTS_DB.values() if p.category == category]

def format_price(price: float) -> str:
    """Format giá tiền VND"""
    return f"{int(price):,}đ".replace(",", ".")

def calculate_total(items: List[OrderItem]) -> float:
    """Tính tổng tiền đơn hàng"""
    return sum(item.subtotal for item in items)

# ============ MAIN PAYMENT FUNCTION ============

def process_payment_request(user_message: str) -> dict:
    """
    Xử lý yêu cầu thanh toán từ user message
    
    Returns:
        dict: Thông tin đơn hàng với structured data
    """
    import re
    
    # Chuyển về lowercase để dễ xử lý
    message_lower = user_message.lower()
    
    order_items = []
    unavailable_items = []
    
    # IMPROVED PARSING LOGIC
    # Pattern 1: số + đơn vị (optional) + tên sản phẩm
    # Ví dụ: "1 cái bánh mì", "2 hộp sữa", "3 chai nước ngọt"
    # Pattern 2: số + tên sản phẩm (không có đơn vị)
    # Ví dụ: "1 bánh mì", "2 sữa"
    
    # Normalize text
    text = message_lower
    # Loại bỏ dấu câu
    text = re.sub(r'[.,!?;:]', '', text)
    # Loại bỏ các từ không cần thiết
    text = text.replace("tôi muốn", "")
    text = text.replace("cho tôi", "")
    text = text.replace("tôi cần", "")
    text = text.replace("mua", "")
    text = text.replace("đặt", "")
    text = text.replace("order", "")
    text = text.replace("thanh toán", "")
    text = text.replace("thành toán", "")  # Whisper transcribe sai
    text = text.replace("tính tiền", "")
    text = text.replace("lấy", "")
    text = text.replace("gọi", "")
    text = text.strip()
    
    # Chuyển số bằng chữ thành số
    text = convert_number_words(text)
    
    # Split by "và" hoặc ","
    items_parts = re.split(r'\s+và\s+|,', text)
    
    for part in items_parts:
        part = part.strip()
        if not part:
            continue
        
        # Tìm số đầu tiên trong part (bây giờ đã được convert từ chữ sang số)
        number_match = re.search(r'(\d+)', part)
        if number_match:
            quantity = int(number_match.group(1))
            
            # Lấy phần sau số (bỏ đơn vị)
            remaining = part[number_match.end():].strip()
            
            # Thử tìm sản phẩm với nhiều độ dài khác nhau
            words = remaining.split()
            found = False
            
            # Thử từ dài nhất đến ngắn nhất
            for length in range(len(words), 0, -1):
                phrase = " ".join(words[:length])
                
                # Bỏ các từ đơn vị phổ biến
                phrase = phrase.replace("cái", "").replace("hộp", "").replace("chai", "")
                phrase = phrase.replace("ly", "").replace("tô", "").replace("gói", "")
                phrase = phrase.replace("kg", "").replace("bó", "").strip()
                
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
            
            # Nếu không tìm thấy với đơn vị, thử tìm trực tiếp toàn bộ
            if not found:
                product = get_product_by_keyword(remaining)
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
                    else:
                        unavailable_items.append(product.name)
    
    # Tính tổng tiền
    total_amount = calculate_total(order_items)
    
    # Tạo response
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
    """Chuyển số bằng chữ thành số trong text (chỉ whole words)"""
    import re
    
    number_map = {
        "một": "1", "hai": "2", "ba": "3", "bốn": "4", "năm": "5",
        "sáu": "6", "bảy": "7", "tám": "8", "chín": "9", "mười": "10",
        "mot": "1", "bon": "4", "nam": "5", "sau": "6", "bay": "7",
        "tam": "8", "chin": "9", "muoi": "10",
        "hai mươi": "20", "ba mươi": "30", "bốn mươi": "40", "năm mươi": "50"
    }
    
    result = text
    # Thay thế từ dài đến ngắn, chỉ whole words
    for word, num in sorted(number_map.items(), key=lambda x: len(x[0]), reverse=True):
        # Dùng word boundary để tránh thay "hai" trong "chai"
        pattern = r'\b' + re.escape(word) + r'\b'
        result = re.sub(pattern, num, result)
    
    return result

# ============ HELPER FUNCTIONS ============

def is_number_word(word: str) -> bool:
    """Check if word is a number word in Vietnamese"""
    number_words = {
        "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5,
        "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "mười": 10,
        "mot": 1, "bon": 4, "nam": 5, "sau": 6, "bay": 7, 
        "tam": 8, "chin": 9, "muoi": 10
    }
    return word in number_words

def parse_number(word: str) -> int:
    """Parse number from string or number word"""
    if word.isdigit():
        return int(word)
    
    number_words = {
        "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5,
        "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "mười": 10,
        "mot": 1, "bon": 4, "nam": 5, "sau": 6, "bay": 7, 
        "tam": 8, "chin": 9, "muoi": 10
    }
    return number_words.get(word, 1)

# ============ TEST ============

if __name__ == "__main__":
    # Test cases
    print("=== TEST PRODUCTS MODULE ===\n")
    
    # Test 1: Tìm sản phẩm
    print("1. Tìm sản phẩm 'bánh mì':")
    product = get_product_by_keyword("bánh mì")
    if product:
        print(f"   ✓ {product.name}: {format_price(product.price)}/{product.unit}")
    
    # Test 2: Process payment
    print("\n2. Test payment request:")
    test_messages = [
        "tôi muốn mua 1 cái bánh mì và 2 hộp sữa",
        "cho tôi 3 chai nước ngọt",
        "tôi cần 1 ly cà phê và 1 cái bánh mì thịt"
    ]
    
    for msg in test_messages:
        print(f"\n   User: '{msg}'")
        result = process_payment_request(msg)
        print(f"   Response: {result['message']}")
        print(f"   Total: {format_price(result['total_amount'])}")
