"""
Test priority: Menu request vs Payment request
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_menu_vs_payment_priority():
    print("\n" + "="*70)
    print("🧪 TESTING: Menu Request Priority Over Payment")
    print("="*70)
    
    menu_keywords = [
        "menu", "thực đơn", "món gì", "bán gì", "có gì", 
        "sản phẩm gì", "bán những gì", "những món", "danh sách",
        "xem menu", "cho xem", "xin menu"
    ]
    
    payment_keywords = [
        "mua", "đặt", "order", 
        "thanh toán", "thành toán",
        "tính tiền", "bao nhiêu tiền", "bao nhiêu",
        "giá", "cho tôi", "lấy", "gọi"
    ]
    
    test_cases = [
        # MENU REQUESTS (should detect menu FIRST, ignore payment keywords)
        ("Cho tôi xin cái menu", "menu", "Has 'cho tôi' but asking for menu"),
        ("Cho tôi xem thực đơn", "menu", "Has 'cho tôi' but asking for menu"),
        ("Xin menu", "menu", "Asking for menu"),
        ("Có những món gì?", "menu", "What dishes"),
        
        # PAYMENT REQUESTS (should detect payment)
        ("Cho tôi 1 cái bánh mì", "payment", "Order banh mi"),
        ("Mua 2 tô phở", "payment", "Buy pho"),
        ("Lấy 1 ly cà phê", "payment", "Get coffee"),
        ("Gọi cho tôi 3 chai nước", "payment", "Order water"),
    ]
    
    for query, expected, desc in test_cases:
        is_menu = any(keyword in query.lower() for keyword in menu_keywords)
        is_payment = any(keyword in query.lower() for keyword in payment_keywords)
        
        # Menu has PRIORITY
        detected = "menu" if is_menu else ("payment" if is_payment else "chat")
        
        status = "✅ PASS" if detected == expected else "❌ FAIL"
        
        print(f"\n{status} | {desc}")
        print(f"   Query: '{query}'")
        print(f"   Menu match: {is_menu}, Payment match: {is_payment}")
        print(f"   Detected as: {detected} (expected: {expected})")
        
        if detected == "menu":
            print(f"   → Should SHOW MENU")
        elif detected == "payment":
            print(f"   → Should PROCESS PAYMENT")
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETED")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_menu_vs_payment_priority()
