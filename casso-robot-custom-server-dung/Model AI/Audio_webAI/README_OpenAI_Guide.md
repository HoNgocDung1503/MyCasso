# 📚 HƯỚNG DẪN: OpenAI Response Structure & System Prompt

## 🎯 Tổng quan

Tài liệu này giải thích cách sử dụng **System Prompt** và **Structured Response** của OpenAI để xây dựng hệ thống thanh toán thông minh.

---

## 📖 Các khái niệm cơ bản

### 1. **Response Structure** (Cấu trúc Response)

Response của OpenAI có cấu trúc cơ bản như sau:

```python
[
    {
        "id": "msg_xxx",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "output_text",
                "text": "Nội dung trả lời...",
                "annotations": []
            }
        ]
    }
]
```

**Các thành phần:**
- `id`: ID duy nhất của message
- `role`: Vai trò (assistant, user, system)
- `content`: Nội dung trả lời
- `text`: Text thực tế

---

### 2. **System Prompt** (Developer Role)

System prompt định hướng cách AI trả lời.

**Ví dụ đơn giản:**

```python
from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {
            "role": "system",  # hoặc "developer"
            "content": "Talk like a pirate."  # Định hướng cách trả lời
        },
        {
            "role": "user",
            "content": "Are semicolons optional in JavaScript?",
        },
    ],
)

print(response.choices[0].message.content)
# Output: "Ahoy! Aye, semicolons be optional in JavaScript..."
```

---

### 3. **Structured Output** (Pydantic Models)

Parse response thành Python objects với Pydantic.

**Ví dụ:**

```python
from pydantic import BaseModel

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

response = client.beta.chat.completions.parse(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "Extract the event information."},
        {
            "role": "user",
            "content": "Alice and Bob are going to a science fair on Friday.",
        },
    ],
    response_format=CalendarEvent,  # ✅ Parse thành object
)

event = response.choices[0].message.parsed
print(event.name)  # "Science Fair"
print(event.participants)  # ["Alice", "Bob"]
```

---

## 🛒 Áp dụng vào hệ thống thanh toán

### Kiến trúc hệ thống

```
User Input (voice/text)
        ↓
[Transcribe với Whisper]
        ↓
[Detect Intent] → Payment hoặc Normal Chat?
        ↓
[Payment Handler]
  ├─ Parse products (products.py)
  ├─ System Prompt cho thanh toán
  └─ Structured Response
        ↓
[TTS Response]
        ↓
Send to Client
```

---

### File Structure

```
Audio_webAI/
├── server.py                    # Main server với payment logic
├── products.py                  # Database sản phẩm & giá
├── demo_openai_examples.py      # Ví dụ OpenAI APIs
└── README_OpenAI_Guide.md       # Tài liệu này
```

---

## 🔧 Chi tiết Implementation

### 1. **products.py** - Quản lý sản phẩm

```python
from pydantic import BaseModel

class Product(BaseModel):
    id: str
    name: str
    price: float
    unit: str
    category: str
    available: bool = True

class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    unit: str
    subtotal: float

class PaymentResponse(BaseModel):
    items: List[OrderItem]
    total_amount: float
    currency: str = "VND"
    success: bool
    message: str
    unavailable_items: List[str] = []
```

**Database sản phẩm:**

```python
PRODUCTS_DB = {
    "banh_mi": Product(
        id="banh_mi",
        name="Bánh mì",
        price=15000,
        unit="cái",
        category="Thức ăn"
    ),
    "sua": Product(
        id="sua",
        name="Sữa",
        price=12000,
        unit="hộp",
        category="Đồ uống"
    ),
    # ... thêm sản phẩm khác
}
```

**Mapping keywords:**

```python
PRODUCT_KEYWORDS = {
    "bánh mì": "banh_mi",
    "banh mi": "banh_mi",
    "sữa": "sua",
    "sua": "sua",
    # ... thêm keywords
}
```

**Function xử lý:**

```python
def process_payment_request(user_message: str) -> dict:
    """
    Parse user message → Extract products → Calculate total
    
    Input: "tôi muốn mua 1 cái bánh mì và 2 hộp sữa"
    Output: {
        "items": [...],
        "total_amount": 39000,
        "success": True,
        "message": "..."
    }
    """
    # Simple parsing với regex
    # Tìm pattern: [số] [tên sản phẩm]
    # → Lookup từ PRODUCTS_DB
    # → Tính tổng tiền
```

---

### 2. **server.py** - System Prompt & Response

#### A. Detect Intent

```python
async def get_ai_response(user_message, conversation_history=None):
    # Detect payment keywords
    payment_keywords = ["mua", "đặt", "order", "thanh toán"]
    is_payment_request = any(
        keyword in user_message.lower() 
        for keyword in payment_keywords
    )
    
    if is_payment_request:
        return await handle_payment_request(user_message)
    else:
        return await handle_normal_chat(user_message, conversation_history)
```

#### B. Payment Handler với System Prompt

```python
async def handle_payment_request(user_message: str) -> str:
    # BƯỚC 1: Parse products từ database
    payment_result = process_payment_request(user_message)
    
    if not payment_result['success']:
        return "Xin lỗi, không tìm thấy sản phẩm..."
    
    # BƯỚC 2: System prompt chuyên biệt
    system_prompt = """Bạn là nhân viên thanh toán thông minh.

NHIỆM VỤ:
- Xác nhận đơn hàng rõ ràng
- Đọc từng món và số lượng
- Thông báo tổng tiền
- Hỏi khách xác nhận

PHONG CÁCH:
- Ngắn gọn, chuyên nghiệp
- Thân thiện, lịch sự
- Đọc rõ ràng từng món và giá"""

    # BƯỚC 3: Prepare order summary
    order_text = "\n".join([
        f"{item['quantity']} {item['unit']} {item['product_name']} "
        f"- {format_price(item['subtotal'])}"
        for item in payment_result['items']
    ])
    
    # BƯỚC 4: Call OpenAI
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user", 
                "content": f"Khách đặt:\n{order_text}\n\nTổng: {total_text}"
            }
        ],
        temperature=0.7,
        max_tokens=200
    )
    
    return response.choices[0].message.content
```

#### C. Normal Chat với System Prompt khác

```python
async def handle_normal_chat(user_message: str, conversation_history: list):
    system_prompt = """Bạn là trợ lý AI thông minh.

NHIỆM VỤ:
- Trả lời câu hỏi khách hàng
- Tư vấn sản phẩm
- Hỗ trợ thanh toán

PHONG CÁCH:
- Ngắn gọn (1-2 câu)
- Thân thiện
- Nhanh chóng"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt}
        ] + conversation_history + [
            {"role": "user", "content": user_message}
        ]
    )
    
    return response.choices[0].message.content
```

---

## 🎬 Ví dụ Flow hoàn chỉnh

### Ví dụ 1: Thanh toán thành công

**Input:**
```
User: "Tôi muốn mua 1 cái bánh mì và 2 hộp sữa"
```

**Processing:**
```python
# 1. Transcribe (Whisper)
transcribed_text = "tôi muốn mua 1 cái bánh mì và 2 hộp sữa"

# 2. Detect intent
is_payment = True  # có từ "mua"

# 3. Parse products
payment_result = {
    "items": [
        {"product_name": "Bánh mì", "quantity": 1, "subtotal": 15000},
        {"product_name": "Sữa", "quantity": 2, "subtotal": 24000}
    ],
    "total_amount": 39000,
    "success": True
}

# 4. System prompt + OpenAI
ai_response = """Dạ, cho em xác nhận đơn hàng:
- 1 cái bánh mì: 15.000đ
- 2 hộp sữa: 24.000đ

Tổng cộng: 39.000đ

Anh/chị xác nhận đơn hàng này nhé?"""

# 5. TTS + Send to client
```

**Output (Voice):**
> "Dạ, cho em xác nhận đơn hàng: một cái bánh mì mười lăm nghìn đồng, hai hộp sữa hai mươi bốn nghìn đồng. Tổng cộng ba mươi chín nghìn đồng. Anh chị xác nhận đơn hàng này nhé?"

---

### Ví dụ 2: Chat thông thường

**Input:**
```
User: "Hôm nay cửa hàng mở cửa không?"
```

**Processing:**
```python
# 1. Detect intent
is_payment = False  # không có từ khóa thanh toán

# 2. Normal chat handler
system_prompt = "Bạn là trợ lý thân thiện..."
ai_response = "Dạ có ạ, cửa hàng mở cửa từ 7h sáng đến 10h tối."
```

---

## 📊 So sánh System Prompts

| Tình huống | System Prompt | Kết quả |
|------------|---------------|---------|
| **Thanh toán** | "Bạn là nhân viên thanh toán. Xác nhận đơn hàng rõ ràng, lịch sự." | Response chuyên nghiệp, có cấu trúc rõ ràng |
| **Chat thông thường** | "Bạn là trợ lý thân thiện. Trả lời ngắn gọn." | Response tự nhiên, ngắn gọn |
| **Tư vấn kỹ thuật** | "Bạn là chuyên gia kỹ thuật. Trả lời chi tiết với thuật ngữ." | Response chuyên sâu, có thuật ngữ |

---

## 🚀 Cách chạy & test

### 1. Test products.py

```bash
cd "Model AI/Audio_webAI"
python products.py
```

**Output:**
```
=== TEST PRODUCTS MODULE ===

1. Tìm sản phẩm 'bánh mì':
   ✓ Bánh mì: 15.000đ/cái

2. Test payment request:
   User: 'tôi muốn mua 1 cái bánh mì và 2 hộp sữa'
   Response: Đơn hàng của bạn:...
   Total: 39.000đ
```

### 2. Test OpenAI examples

```bash
python demo_openai_examples.py
```

**Output:**
```
🌟🌟🌟 OPENAI RESPONSE STRUCTURE & SYSTEM PROMPT EXAMPLES 🌟🌟🌟

============================================================
VÍ DỤ 1: SIMPLE RESPONSE
============================================================
Response: Under the soft glow of the moon...
Role: assistant

============================================================
VÍ DỤ 2: SYSTEM PROMPT - Talk like a pirate
============================================================
Response: Ahoy! Aye, semicolons be optional...
...
```

### 3. Test server với payment

```bash
python server.py
```

**WebSocket test:**
```javascript
// Client code
ws.send(JSON.stringify({
    type: 'chat',
    message: 'tôi muốn mua 1 cái bánh mì và 2 hộp sữa'
}));

// Response
{
    type: 'chat_response',
    message: 'Dạ, cho em xác nhận đơn hàng:...'
}
```

---

## 💡 Best Practices

### 1. **System Prompt Design**

✅ **Tốt:**
```python
system_prompt = """Bạn là nhân viên thanh toán.

NHIỆM VỤ:
- Xác nhận đơn hàng
- Tính tổng tiền

PHONG CÁCH:
- Ngắn gọn
- Lịch sự"""
```

❌ **Không tốt:**
```python
system_prompt = "Bạn là AI. Trả lời câu hỏi."
```

### 2. **Intent Detection**

```python
# Rõ ràng, dễ mở rộng
payment_keywords = ["mua", "đặt", "order", "thanh toán"]
question_keywords = ["có", "không", "thế nào", "như thế"]
```

### 3. **Error Handling**

```python
try:
    payment_result = process_payment_request(user_message)
    if not payment_result['success']:
        # Suggest available products
        return suggest_products()
except Exception as e:
    return "Xin lỗi, có lỗi xảy ra..."
```

---

## 📚 Tài liệu tham khảo

1. **OpenAI Chat Completions**: https://platform.openai.com/docs/api-reference/chat
2. **Structured Outputs**: https://platform.openai.com/docs/guides/structured-outputs
3. **System Prompts Best Practices**: https://platform.openai.com/docs/guides/prompt-engineering

---

## 🎓 Bài tập mở rộng

1. **Thêm xác nhận thanh toán:**
   - User confirm đơn hàng
   - Lưu vào database

2. **Tích hợp giỏ hàng:**
   - Thêm sản phẩm dần dần
   - Xem giỏ hàng
   - Checkout

3. **Gợi ý sản phẩm:**
   - "Bạn có muốn thêm... không?"
   - Upselling, cross-selling

4. **Multi-language:**
   - Detect ngôn ngữ
   - System prompt theo ngôn ngữ

---

## 📞 Hỗ trợ

Nếu có vấn đề, check:
1. `.env` có `OPENAI_API_KEY` chưa?
2. `products.py` import được không?
3. OpenAI API có lỗi gì không? (check logs)

---

**Happy Coding! 🚀**
