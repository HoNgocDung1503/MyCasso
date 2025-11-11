"""
Test script cho payment flow với conversation context
"""
import sys
import asyncio

# Mock các dependencies
class MockClient:
    class chat:
        class completions:
            @staticmethod
            def create(**kwargs):
                class Response:
                    class Choice:
                        class Message:
                            content = "Dạ, cho em xác nhận đơn hàng:\n- 1 cái Bánh mì: 15.000đ\n- 2 hộp Sữa: 24.000đ\n\nTổng cộng: 39.000đ\n\nAnh/chị xác nhận đơn hàng này nhé?"
                        message = Message()
                    choices = [Choice()]
                return Response()

# Import server module với mock
import importlib.util
spec = importlib.util.spec_from_file_location("server", "server.py")
server = importlib.util.module_from_spec(spec)

# Mock OpenAI client
server.client = MockClient()

# Load module
spec.loader.exec_module(server)

async def test_payment_flow():
    """Test payment flow với conversation context"""
    
    print("=" * 60)
    print("TEST: PAYMENT FLOW VỚI CONVERSATION CONTEXT")
    print("=" * 60)
    
    mac_address = "AA:BB:CC:DD:EE:FF"
    
    # Step 1: User đặt hàng
    print("\n📝 BƯỚC 1: User đặt hàng")
    print("-" * 60)
    user_msg_1 = "Cho tôi 1 bánh mì và 2 hộp sữa"
    print(f"User: {user_msg_1}")
    
    response_1 = await server.get_ai_response(user_msg_1, mac_address)
    print(f"\nBot: {response_1}")
    
    # Kiểm tra context
    context = server.get_or_create_context(mac_address)
    print(f"\n✅ Context state:")
    print(f"   - Conversation history: {len(context.conversation_history)} messages")
    print(f"   - Pending payment: {'YES' if context.pending_payment else 'NO'}")
    
    if context.pending_payment:
        print(f"   - Order total: {server.format_price(context.pending_payment['total_amount'])}")
        print(f"   - Order items: {len(context.pending_payment['items'])} items")
    
    # Step 2: User xác nhận
    print("\n\n📝 BƯỚC 2: User xác nhận")
    print("-" * 60)
    user_msg_2 = "oke"
    print(f"User: {user_msg_2}")
    
    response_2 = await server.get_ai_response(user_msg_2, mac_address)
    print(f"\nBot: {response_2}")
    
    # Kiểm tra context sau khi confirm
    print(f"\n✅ Context state after confirmation:")
    print(f"   - Conversation history: {len(context.conversation_history)} messages")
    print(f"   - Pending payment: {'YES' if context.pending_payment else 'NO'}")
    
    # Step 3: User hủy đơn hàng mới
    print("\n\n📝 BƯỚC 3: User đặt đơn mới và hủy")
    print("-" * 60)
    user_msg_3 = "Cho tôi 3 chai nước ngọt"
    print(f"User: {user_msg_3}")
    
    response_3 = await server.get_ai_response(user_msg_3, mac_address)
    print(f"\nBot: {response_3}")
    
    print(f"\n✅ Context state:")
    print(f"   - Pending payment: {'YES' if context.pending_payment else 'NO'}")
    
    user_msg_4 = "thôi không lấy"
    print(f"\nUser: {user_msg_4}")
    
    response_4 = await server.get_ai_response(user_msg_4, mac_address)
    print(f"\nBot: {response_4}")
    
    print(f"\n✅ Context state after cancellation:")
    print(f"   - Pending payment: {'YES' if context.pending_payment else 'NO'}")
    
    # Print full conversation history
    print("\n\n📜 CONVERSATION HISTORY:")
    print("-" * 60)
    for i, msg in enumerate(context.conversation_history):
        role = "🧑 User" if msg['role'] == 'user' else "🤖 Bot"
        content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
        print(f"{i+1}. {role}: {content}")
    
    print("\n" + "=" * 60)
    print("✅ TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_payment_flow())
