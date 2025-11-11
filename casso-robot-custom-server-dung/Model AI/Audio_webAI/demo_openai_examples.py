"""
Demo và test các tính năng OpenAI Response Structure và System Prompt
"""

from openai import OpenAI
from pydantic import BaseModel
from typing import List
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

# ============================================
# VÍ DỤ 1: SIMPLE TEXT RESPONSE
# ============================================
def example_1_simple_response():
    """
    Ví dụ cơ bản: Response đơn giản
    Giống như các response cũ nhưng với cấu trúc mới
    """
    print("\n" + "="*60)
    print("VÍ DỤ 1: SIMPLE RESPONSE")
    print("="*60)
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": "Write a one-sentence bedtime story about a unicorn."
            }
        ]
    )
    
    print(f"Response: {response.choices[0].message.content}")
    print(f"Role: {response.choices[0].message.role}")

# ============================================
# VÍ DỤ 2: SYSTEM PROMPT (DEVELOPER ROLE)
# ============================================
def example_2_system_prompt():
    """
    Ví dụ về System Prompt (developer role)
    Dùng để định hướng cách AI trả lời
    """
    print("\n" + "="*60)
    print("VÍ DỤ 2: SYSTEM PROMPT - Talk like a pirate")
    print("="*60)
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",  # hoặc "developer" trong API mới
                "content": "Talk like a pirate."
            },
            {
                "role": "user",
                "content": "Are semicolons optional in JavaScript?",
            },
        ],
    )
    
    print(f"Response: {response.choices[0].message.content}")

# ============================================
# VÍ DỤ 3: STRUCTURED OUTPUT với Pydantic
# ============================================
class CalendarEvent(BaseModel):
    """Model cho event"""
    name: str
    date: str
    participants: list[str]

def example_3_structured_output():
    """
    Ví dụ về Structured Output
    Parse response thành Python object (Pydantic model)
    """
    print("\n" + "="*60)
    print("VÍ DỤ 3: STRUCTURED OUTPUT - Calendar Event")
    print("="*60)
    
    # Note: responses.parse() là API mới, nếu không support thì dùng cách cũ
    # Cách mới (nếu SDK support):
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Extract the event information."},
                {
                    "role": "user",
                    "content": "Alice and Bob are going to a science fair on Friday.",
                },
            ],
            response_format=CalendarEvent,
        )
        
        event = response.choices[0].message.parsed
        print(f"Event Name: {event.name}")
        print(f"Date: {event.date}")
        print(f"Participants: {', '.join(event.participants)}")
        
    except Exception as e:
        print(f"⚠️  Structured output không support: {e}")
        print("   → Dùng function calling hoặc JSON mode thay thế")
        
        # Cách thay thế: JSON mode
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Extract the event information as JSON with fields: name, date, participants (array)."},
                {
                    "role": "user",
                    "content": "Alice and Bob are going to a science fair on Friday.",
                },
            ],
            response_format={"type": "json_object"}
        )
        
        import json
        event_data = json.loads(response.choices[0].message.content)
        print(f"Event (JSON): {json.dumps(event_data, indent=2, ensure_ascii=False)}")

# ============================================
# VÍ DỤ 4: COMPLEX STRUCTURED OUTPUT
# ============================================
class Step(BaseModel):
    explanation: str
    output: str

class MathReasoning(BaseModel):
    steps: list[Step]
    final_answer: str

def example_4_complex_structured():
    """
    Ví dụ về Structured Output phức tạp
    Parse response thành nested Pydantic models
    """
    print("\n" + "="*60)
    print("VÍ DỤ 4: COMPLEX STRUCTURED OUTPUT - Math Reasoning")
    print("="*60)
    
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful math tutor. Guide the user through the solution step by step.",
                },
                {"role": "user", "content": "how can I solve 8x + 7 = -23"},
            ],
            response_format=MathReasoning,
        )
        
        math_reasoning = response.choices[0].message.parsed
        
        print("Steps:")
        for i, step in enumerate(math_reasoning.steps, 1):
            print(f"  {i}. {step.explanation}")
            print(f"     → {step.output}")
        
        print(f"\nFinal Answer: {math_reasoning.final_answer}")
        
    except Exception as e:
        print(f"⚠️  Structured output không support: {e}")
        print("   → Dùng JSON mode thay thế")
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """You are a helpful math tutor. 
Return JSON with:
- steps: array of {explanation: string, output: string}
- final_answer: string""",
                },
                {"role": "user", "content": "how can I solve 8x + 7 = -23"},
            ],
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        print(f"Math Reasoning (JSON): {json.dumps(result, indent=2, ensure_ascii=False)}")

# ============================================
# VÍ DỤ 5: PAYMENT USE CASE (Áp dụng cho project)
# ============================================
class OrderItem(BaseModel):
    product_name: str
    quantity: int
    unit_price: float
    unit: str
    subtotal: float

class PaymentResponse(BaseModel):
    items: list[OrderItem]
    total_amount: float
    currency: str = "VND"
    success: bool
    message: str

def example_5_payment_use_case():
    """
    Ví dụ áp dụng vào use case thanh toán
    """
    print("\n" + "="*60)
    print("VÍ DỤ 5: PAYMENT USE CASE - Structured Payment Response")
    print("="*60)
    
    user_request = "Tôi muốn mua 2 cái bánh mì và 3 hộp sữa"
    
    # Giả sử đã parse được thông tin sản phẩm
    order_info = """
Đơn hàng:
- 2 cái bánh mì: 15,000đ/cái = 30,000đ
- 3 hộp sữa: 12,000đ/hộp = 36,000đ
Tổng: 66,000đ
"""
    
    try:
        # Dùng structured output
        response = client.beta.chat.completions.parse(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Xác nhận đơn hàng một cách rõ ràng, lịch sự."
                },
                {
                    "role": "user",
                    "content": f"Khách đặt: {user_request}\n\n{order_info}\n\nXác nhận đơn hàng."
                },
            ],
            response_format=PaymentResponse,
        )
        
        payment = response.choices[0].message.parsed
        print(f"Success: {payment.success}")
        print(f"Message: {payment.message}")
        print(f"Total: {payment.total_amount:,.0f} {payment.currency}")
        
    except Exception as e:
        print(f"⚠️  Structured output không support: {e}")
        print("   → Dùng cách thông thường với system prompt")
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """Bạn là nhân viên thanh toán.
Xác nhận đơn hàng rõ ràng, lịch sự.
Format:
- Liệt kê từng món
- Tổng tiền
- Hỏi xác nhận"""
                },
                {
                    "role": "user",
                    "content": f"Khách đặt: {user_request}\n\n{order_info}"
                },
            ],
        )
        
        print(f"Response:\n{response.choices[0].message.content}")

# ============================================
# VÍ DỤ 6: MULTIPLE SYSTEM PROMPTS
# ============================================
def example_6_multiple_contexts():
    """
    Ví dụ về nhiều system prompts cho các ngữ cảnh khác nhau
    """
    print("\n" + "="*60)
    print("VÍ DỤ 6: MULTIPLE SYSTEM PROMPTS")
    print("="*60)
    
    contexts = [
        {
            "name": "Formal Assistant",
            "system": "Bạn là trợ lý chuyên nghiệp, lịch sự. Trả lời ngắn gọn, trang trọng.",
            "user": "Hôm nay trời thế nào?"
        },
        {
            "name": "Casual Friend",
            "system": "Bạn là người bạn thân thiết, hay nói đùa. Trả lời thoải mái, vui vẻ.",
            "user": "Hôm nay trời thế nào?"
        },
        {
            "name": "Technical Expert",
            "system": "Bạn là chuyên gia kỹ thuật. Trả lời chi tiết, chính xác với thuật ngữ.",
            "user": "WebSocket hoạt động như thế nào?"
        }
    ]
    
    for ctx in contexts:
        print(f"\n--- {ctx['name']} ---")
        print(f"System: {ctx['system'][:50]}...")
        print(f"User: {ctx['user']}")
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": ctx['system']},
                {"role": "user", "content": ctx['user']}
            ],
            max_tokens=100
        )
        
        print(f"Response: {response.choices[0].message.content}")

# ============================================
# MAIN - RUN ALL EXAMPLES
# ============================================
def main():
    print("\n" + "🌟"*30)
    print("OPENAI RESPONSE STRUCTURE & SYSTEM PROMPT EXAMPLES")
    print("🌟"*30)
    
    try:
        # Chạy các ví dụ
        example_1_simple_response()
        example_2_system_prompt()
        example_3_structured_output()
        example_4_complex_structured()
        example_5_payment_use_case()
        example_6_multiple_contexts()
        
        print("\n" + "✅"*30)
        print("HOÀN THÀNH TẤT CẢ VÍ DỤ!")
        print("✅"*30 + "\n")
        
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
