"""
Test menu inquiry - Phân biệt hỏi menu tổng quát vs hỏi sản phẩm cụ thể
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_menu_inquiry():
    print("\n" + "="*70)
    print("🧪 TESTING: Menu Inquiry Detection")
    print("="*70)
    
    menu_keywords = [
        "menu", "thực đơn", "món gì", "bán gì", "có gì", 
        "sản phẩm gì", "bán những gì", "những món", "danh sách"
    ]
    
    test_cases = [
        # MENU TỔNG QUÁT (should show full menu)
        ("Cửa hàng bán những sản phẩm gì?", True, "General menu question"),
        ("Shop có bán gì?", True, "What do you sell"),
        ("Menu có những món gì?", True, "What's on menu"),
        ("Cho tôi xem thực đơn", True, "Show menu"),
        ("Có những món gì?", True, "What dishes available"),
        ("Danh sách sản phẩm", True, "Product list"),
        
        # SẢN PHẨM CỤ THỂ (should search specific product)
        ("Có bán phở không?", False, "Specific product: phở"),
        ("Giá bánh mì bao nhiêu?", False, "Price of specific item"),
        ("Cà phê giá bao nhiêu?", False, "Coffee price"),
        ("Shop có trà sữa không?", False, "Do you have milk tea"),
    ]
    
    for query, expected_menu, desc in test_cases:
        is_asking_menu = any(keyword in query.lower() for keyword in menu_keywords)
        
        status = "✅ PASS" if is_asking_menu == expected_menu else "❌ FAIL"
        
        print(f"\n{status} | {desc}")
        print(f"   Query: '{query}'")
        print(f"   Detected as menu inquiry: {is_asking_menu} (expected: {expected_menu})")
        
        if is_asking_menu:
            print(f"   → Should show FULL MENU")
        else:
            print(f"   → Should SEARCH for specific product")
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETED")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_menu_inquiry()
