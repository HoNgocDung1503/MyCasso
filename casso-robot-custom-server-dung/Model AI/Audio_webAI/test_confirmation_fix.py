"""
Test confirmation detection - Đảm bảo không nhầm câu hỏi với xác nhận
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

async def test_confirmation_detection():
    print("\n" + "="*70)
    print("🧪 TESTING: Smart Confirmation Detection")
    print("="*70)
    
    from server import get_ai_response, get_or_create_context
    
    mac = "TEST:CONFIRM"
    
    # Setup: Tạo pending payment
    print("\n📝 SETUP: Create pending payment")
    print("-"*70)
    context = get_or_create_context(mac)
    fake_payment = {
        'success': True,
        'total_amount': 45000,
        'items': [
            {'product_name': 'Phở', 'quantity': 1, 'subtotal': 45000, 'unit': 'tô'}
        ]
    }
    context.set_pending_payment(fake_payment)
    print(f"✅ Pending payment set: 1 tô Phở - 45.000đ")
    
    # Test cases
    test_cases = [
        {
            "input": "oke",
            "expect": "confirmation",
            "desc": "Simple confirmation"
        },
        {
            "input": "được",
            "expect": "confirmation",
            "desc": "Simple confirmation (Vietnamese)"
        },
        {
            "input": "xác nhận",
            "expect": "confirmation",
            "desc": "Explicit confirmation"
        },
        {
            "input": "Cửa hàng có bán bánh mì không?",
            "expect": "question",
            "desc": "Product inquiry (should NOT confirm)"
        },
        {
            "input": "Có bán trà sữa không?",
            "expect": "question",
            "desc": "Product inquiry with 'có' (should NOT confirm)"
        },
        {
            "input": "Bao nhiêu tiền một tô phở?",
            "expect": "question",
            "desc": "Price inquiry (should NOT confirm)"
        },
        {
            "input": "không lấy nữa",
            "expect": "cancellation",
            "desc": "Cancellation"
        },
        {
            "input": "thôi",
            "expect": "cancellation",
            "desc": "Simple cancellation"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        # Reset pending payment nếu cần
        if not context.pending_payment:
            context.set_pending_payment(fake_payment)
        
        print(f"\n📌 Test {i}: {test['desc']}")
        print("-"*70)
        print(f"User: '{test['input']}'")
        
        response = await get_ai_response(test['input'], mac)
        
        print(f"Bot:  {response[:100]}...")
        
        # Check result
        if test['expect'] == "confirmation":
            if "xác nhận" in response.lower() and "qr" in response.lower():
                print(f"✅ PASS - Correctly detected as confirmation")
            else:
                print(f"❌ FAIL - Should confirm but didn't")
                print(f"   Response: {response}")
        elif test['expect'] == "cancellation":
            if "hủy" in response.lower():
                print(f"✅ PASS - Correctly detected as cancellation")
            else:
                print(f"❌ FAIL - Should cancel but didn't")
        elif test['expect'] == "question":
            if "xác nhận" not in response.lower() or "qr" not in response.lower():
                print(f"✅ PASS - Correctly treated as question, NOT confirmation")
            else:
                print(f"❌ FAIL - Wrongly detected as confirmation!")
                print(f"   Response: {response}")
        
        print(f"Pending payment after: {'YES' if context.pending_payment else 'NO'}")
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETED")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_confirmation_detection())
