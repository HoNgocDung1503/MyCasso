"""
Test nhanh các tính năng mới của server
KHÔNG CẦN OPENAI API KEY cho test này
"""

from products import (
    process_payment_request,
    get_product_by_keyword,
    search_products,
    format_price
)

def test_payment_parsing():
    """Test parsing payment requests"""
    print("\n" + "="*60)
    print("TEST 1: PAYMENT PARSING")
    print("="*60)
    
    test_cases = [
        "tôi muốn mua 1 cái bánh mì và 2 hộp sữa",
        "cho tôi 3 chai nước ngọt và 1 ly cà phê",
        "đặt 2 cái bánh mì thịt",
        "mua 1 tô phở và 1 chai nước suối",
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. User: '{test}'")
        result = process_payment_request(test)
        
        if result['success']:
            print(f"   ✓ Success!")
            print(f"   Items: {len(result['items'])}")
            for item in result['items']:
                print(f"     - {item['quantity']} {item['unit']} {item['product_name']}: {format_price(item['subtotal'])}")
            print(f"   Total: {format_price(result['total_amount'])}")
        else:
            print(f"   ✗ Failed: {result['message']}")

def test_product_search():
    """Test product search"""
    print("\n" + "="*60)
    print("TEST 2: PRODUCT SEARCH")
    print("="*60)
    
    queries = ["bánh", "sữa", "nước", "trà"]
    
    for query in queries:
        print(f"\nSearch: '{query}'")
        results = search_products(query)
        print(f"Found {len(results)} products:")
        for p in results[:3]:  # Top 3
            print(f"  - {p.name}: {format_price(p.price)}/{p.unit}")

def test_system_prompt_scenarios():
    """Test các scenario system prompt (MOCK - không call OpenAI)"""
    print("\n" + "="*60)
    print("TEST 3: SYSTEM PROMPT SCENARIOS (MOCK)")
    print("="*60)
    
    scenarios = [
        {
            "type": "payment",
            "user_input": "tôi muốn mua 1 cái bánh mì",
            "system_prompt": "Bạn là nhân viên thanh toán chuyên nghiệp...",
            "expected_response": "Xác nhận đơn hàng với giá tiền"
        },
        {
            "type": "chat",
            "user_input": "hôm nay trời thế nào?",
            "system_prompt": "Bạn là trợ lý thân thiện...",
            "expected_response": "Trả lời tự nhiên, ngắn gọn"
        },
        {
            "type": "product_info",
            "user_input": "bạn có bán gì?",
            "system_prompt": "Bạn là tư vấn viên sản phẩm...",
            "expected_response": "Liệt kê sản phẩm có sẵn"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. Scenario: {scenario['type']}")
        print(f"   User: {scenario['user_input']}")
        print(f"   System Prompt: {scenario['system_prompt'][:50]}...")
        print(f"   Expected: {scenario['expected_response']}")

def test_intent_detection():
    """Test phát hiện intent"""
    print("\n" + "="*60)
    print("TEST 4: INTENT DETECTION")
    print("="*60)
    
    test_messages = [
        ("tôi muốn mua 1 cái bánh mì", "payment"),
        ("cho tôi đặt 2 hộp sữa", "payment"),
        ("hôm nay trời thế nào?", "chat"),
        ("cửa hàng mở cửa mấy giờ?", "chat"),
        ("tính tiền cho tôi", "payment"),
        ("bạn có bán trà sữa không?", "product_inquiry"),
    ]
    
    payment_keywords = ["mua", "đặt", "order", "thanh toán", "tính tiền"]
    
    for msg, expected_intent in test_messages:
        detected = "payment" if any(kw in msg.lower() for kw in payment_keywords) else "chat"
        status = "✓" if detected == expected_intent else "✗"
        print(f"{status} '{msg}' → {detected} (expected: {expected_intent})")

def main():
    print("\n" + "🧪"*30)
    print("QUICK TEST - Server Features (No OpenAI API needed)")
    print("🧪"*30)
    
    try:
        test_payment_parsing()
        test_product_search()
        test_system_prompt_scenarios()
        test_intent_detection()
        
        print("\n" + "✅"*30)
        print("ALL TESTS COMPLETED!")
        print("✅"*30 + "\n")
        
        print("\n📌 NEXT STEPS:")
        print("1. Chạy server.py để test với OpenAI API")
        print("2. Test với WebSocket client hoặc web interface")
        print("3. Test voice input → transcription → payment")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
