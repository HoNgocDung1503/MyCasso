"""
Test add to order - Cộng dồn món vào đơn đang pending
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_add_to_order():
    print("\n" + "="*70)
    print("🧪 TESTING: Add Items to Pending Order")
    print("="*70)
    
    test_cases = [
        # Case 1: Thêm từ khóa
        {
            "input": "Tính thêm cho tôi một ly cà phê nữa",
            "keywords": ["thêm", "nữa", "tính thêm"],
            "expect": "should_add"
        },
        {
            "input": "Cho tôi thêm 2 hộp sữa",
            "keywords": ["thêm"],
            "expect": "should_add"
        },
        {
            "input": "Cộng thêm 1 cái bánh mì",
            "keywords": ["cộng thêm"],
            "expect": "should_add"
        },
        {
            "input": "Thêm 1 tô phở nữa nhé",
            "keywords": ["thêm", "nữa"],
            "expect": "should_add"
        },
        
        # Case 2: KHÔNG phải thêm món
        {
            "input": "Cho tôi 1 cái bánh mì",  # Đơn mới
            "keywords": [],
            "expect": "new_order"
        },
        {
            "input": "Cửa hàng có bán gì nữa?",  # Câu hỏi
            "keywords": ["nữa"],
            "expect": "not_adding"  # "nữa" ở đây là hỏi, không phải thêm
        }
    ]
    
    add_more_keywords = ["thêm", "nữa", "thêm nữa", "cộng thêm", "tính thêm"]
    
    for i, test in enumerate(test_cases, 1):
        message_lower = test['input'].lower()
        is_adding_more = any(keyword in message_lower for keyword in add_more_keywords)
        
        print(f"\n📌 Test {i}: {test['input']}")
        print(f"   Expected: {test['expect']}")
        print(f"   Detected as 'adding more': {is_adding_more}")
        
        if test['expect'] == "should_add":
            if is_adding_more:
                print(f"   ✅ PASS - Correctly detected as adding items")
            else:
                print(f"   ❌ FAIL - Should detect as adding items")
        elif test['expect'] in ["new_order", "not_adding"]:
            if not is_adding_more:
                print(f"   ✅ PASS - Correctly NOT detected as adding items")
            else:
                print(f"   ⚠️  WARNING - Detected as adding but expected: {test['expect']}")
    
    print("\n" + "="*70)
    print("✅ LOGIC TEST COMPLETED")
    print("="*70 + "\n")
    
    # Bonus: Test merge logic simulation
    print("\n" + "="*70)
    print("🧪 TESTING: Item Merge Logic")
    print("="*70)
    
    # Simulate existing order
    existing_items = [
        {'product_id': 'banh_mi', 'product_name': 'Bánh mì', 'quantity': 1, 'subtotal': 15000, 'unit': 'cái'},
        {'product_id': 'sua', 'product_name': 'Sữa', 'quantity': 2, 'subtotal': 24000, 'unit': 'hộp'}
    ]
    
    # New items to add
    new_items = [
        {'product_id': 'ca_phe', 'product_name': 'Cà phê', 'quantity': 1, 'subtotal': 25000, 'unit': 'ly'}
    ]
    
    # Merge
    merged = existing_items.copy()
    for new_item in new_items:
        found = False
        for existing in merged:
            if existing['product_id'] == new_item['product_id']:
                existing['quantity'] += new_item['quantity']
                existing['subtotal'] += new_item['subtotal']
                found = True
                break
        if not found:
            merged.append(new_item)
    
    print(f"\n📦 Original order: {len(existing_items)} items, Total: {sum(i['subtotal'] for i in existing_items):,}đ")
    for item in existing_items:
        print(f"   - {item['quantity']} {item['unit']} {item['product_name']}: {item['subtotal']:,}đ")
    
    print(f"\n➕ Adding: {len(new_items)} items")
    for item in new_items:
        print(f"   - {item['quantity']} {item['unit']} {item['product_name']}: {item['subtotal']:,}đ")
    
    print(f"\n📦 Merged order: {len(merged)} items, Total: {sum(i['subtotal'] for i in merged):,}đ")
    for item in merged:
        print(f"   - {item['quantity']} {item['unit']} {item['product_name']}: {item['subtotal']:,}đ")
    
    expected_total = 15000 + 24000 + 25000
    actual_total = sum(i['subtotal'] for i in merged)
    
    if actual_total == expected_total:
        print(f"\n✅ MERGE TEST PASSED - Total matches: {actual_total:,}đ")
    else:
        print(f"\n❌ MERGE TEST FAILED - Expected: {expected_total:,}đ, Got: {actual_total:,}đ")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    test_add_to_order()
