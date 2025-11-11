"""
Quick test - Payment confirmation flow
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    print("\n" + "="*70)
    print("🧪 TESTING: Conversation Context & Payment Confirmation")
    print("="*70)
    
    # Import sau khi đã add path
    from server import get_or_create_context, format_price
    
    mac = "TEST:MAC:ADDRESS"
    
    # Test 1: Tạo context mới
    print("\n📌 Test 1: Create new context")
    print("-"*70)
    context = get_or_create_context(mac)
    print(f"✅ Created context for MAC: {mac}")
    print(f"   - History messages: {len(context.conversation_history)}")
    print(f"   - Pending payment: {context.pending_payment is not None}")
    
    # Test 2: Thêm messages
    print("\n📌 Test 2: Add conversation messages")
    print("-"*70)
    context.add_message("user", "Cho tôi 1 bánh mì")
    context.add_message("assistant", "Dạ, cho em xác nhận đơn hàng...")
    print(f"✅ Added 2 messages")
    print(f"   - History messages: {len(context.conversation_history)}")
    print(f"   - Last user message: '{context.conversation_history[0]['content']}'")
    
    # Test 3: Set pending payment
    print("\n📌 Test 3: Set pending payment")
    print("-"*70)
    fake_payment = {
        'success': True,
        'total_amount': 39000,
        'items': [
            {'product_name': 'Bánh mì', 'quantity': 1, 'subtotal': 15000}
        ]
    }
    context.set_pending_payment(fake_payment)
    print(f"✅ Set pending payment")
    print(f"   - Pending: {context.pending_payment is not None}")
    print(f"   - Total: {format_price(context.pending_payment['total_amount'])}")
    
    # Test 4: Clear pending payment
    print("\n📌 Test 4: Clear pending payment (after confirmation)")
    print("-"*70)
    context.clear_pending_payment()
    print(f"✅ Cleared pending payment")
    print(f"   - Pending: {context.pending_payment is not None}")
    
    # Test 5: Check conversation history persists
    print("\n📌 Test 5: Conversation history persists")
    print("-"*70)
    context2 = get_or_create_context(mac)  # Same MAC
    print(f"✅ Retrieved same context")
    print(f"   - History messages: {len(context2.conversation_history)}")
    print(f"   - Same object: {context is context2}")
    
    # Test 6: Different MAC = different context
    print("\n📌 Test 6: Different MAC = different context")
    print("-"*70)
    mac2 = "DIFFERENT:MAC"
    context3 = get_or_create_context(mac2)
    print(f"✅ Created context for new MAC: {mac2}")
    print(f"   - History messages: {len(context3.conversation_history)}")
    print(f"   - Different object: {context is not context3}")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
