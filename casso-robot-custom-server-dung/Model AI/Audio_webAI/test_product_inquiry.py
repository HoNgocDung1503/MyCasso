"""
Test product inquiry - Kiểm tra bot có search database đúng không
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

async def test_product_inquiry():
    print("\n" + "="*70)
    print("🧪 TESTING: Product Inquiry with Database Search")
    print("="*70)
    
    from server import handle_normal_chat
    
    mac = "TEST:INQUIRY"
    
    test_cases = [
        {
            "query": "Cửa hàng có phở không?",
            "expect": "Dạ có ạ",
            "product": "Phở"
        },
        {
            "query": "Có bán bánh mì không?",
            "expect": "Dạ có ạ",
            "product": "Bánh mì"
        },
        {
            "query": "Có cà phê không?",
            "expect": "Dạ có ạ",
            "product": "Cà phê"
        },
        {
            "query": "Giá trà sữa bao nhiêu?",
            "expect": "Dạ có ạ",
            "product": "Trà sữa"
        },
        {
            "query": "Bún bò giá bao nhiêu?",
            "expect": "Dạ có ạ",
            "product": "Bún bò"
        },
        {
            "query": "Có bán pizza không?",
            "expect": "không có",
            "product": None
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n📌 Test {i}: {test['query']}")
        print("-"*70)
        
        response = await handle_normal_chat(test['query'], mac, [])
        
        print(f"👤 User: {test['query']}")
        print(f"🤖 Bot:  {response}")
        
        # Check if response is correct
        if test['product']:
            # Expect to find the product
            if test['expect'].lower() in response.lower():
                print(f"✅ PASS - Bot found product!")
            else:
                print(f"❌ FAIL - Bot should say 'Dạ có ạ' but said: {response}")
        else:
            # Expect NOT to find (pizza not in database)
            if test['expect'].lower() in response.lower() or "không" in response.lower():
                print(f"✅ PASS - Bot correctly said not available")
            else:
                print(f"⚠️  Bot response: {response}")
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETED")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_product_inquiry())
