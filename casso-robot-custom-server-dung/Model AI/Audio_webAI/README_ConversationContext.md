# Conversation Context & Payment Flow

## 🎯 Vấn đề đã giải quyết

Trước đây, server **không lưu conversation history**, nên mỗi câu hỏi đều được xử lý độc lập:
- User mua hàng → Bot xác nhận đơn
- User nói "oke" → Bot không biết là xác nhận gì
- Mỗi request bị reset → Không có context liên tục

## ✅ Giải pháp

### 1. **Conversation Context System**
```python
class ConversationContext:
    - conversation_history: list[dict]  # Lịch sử chat với OpenAI
    - pending_payment: dict             # Đơn hàng đang chờ xác nhận
    - last_interaction: datetime        # Auto-reset sau 5 phút
```

Mỗi **MAC address** có 1 context riêng để track conversation.

### 2. **Payment State Machine**

```
┌─────────────┐
│   Normal    │
│   Chat      │
└──────┬──────┘
       │
       │ "mua 1 bánh mì"
       ▼
┌─────────────────────┐
│  Pending Payment    │  ← Lưu đơn hàng vào context.pending_payment
│  (Chờ xác nhận)     │
└──────┬──────┬───────┘
       │      │
  "oke"│      │"không"
       ▼      ▼
   ┌────┐  ┌─────┐
   │ ✅ │  │ ❌  │
   │ OK │  │ Hủy │
   └────┘  └─────┘
```

### 3. **Flow chi tiết**

#### **Bước 1: User đặt hàng**
```
User: "Cho tôi 1 bánh mì và 2 hộp sữa"
                ↓
   process_payment_request(message)
                ↓
        Payment Result
                ↓
   context.set_pending_payment(result)
                ↓
Bot: "Dạ, cho em xác nhận đơn hàng:
      - 1 cái Bánh mì: 15.000đ
      - 2 hộp Sữa: 24.000đ
      Tổng cộng: 39.000đ
      
      Anh/chị xác nhận đơn hàng này nhé?"
```

**Context State:**
- `pending_payment` = Payment data
- `conversation_history` = [user_msg, bot_msg]

#### **Bước 2: User xác nhận**
```
User: "oke" / "được" / "xác nhận"
                ↓
   Check confirmation keywords
                ↓
   context.pending_payment exists? → YES
                ↓
   generate_qr_code_data(payment)
                ↓
Bot: "Cảm ơn anh/chị! Đơn hàng đã được xác nhận.
      Tổng tiền: 39.000đ
      
      Đây là mã QR để thanh toán. Vui lòng quét mã để hoàn tất."
                ↓
   context.clear_pending_payment()
```

**Context State:**
- `pending_payment` = None (cleared)
- `conversation_history` = [... previous ..., user_confirm, bot_qr]

#### **Bước 3: User hủy đơn**
```
User: "không" / "thôi" / "hủy"
                ↓
   Check cancellation keywords
                ↓
   context.pending_payment exists? → YES
                ↓
Bot: "Dạ, tôi đã hủy đơn hàng. Anh/chị cần gì thêm không ạ?"
                ↓
   context.clear_pending_payment()
```

## 🔑 Các thành phần chính

### **1. ConversationContext Class**
```python
class ConversationContext:
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.conversation_history = []
        self.pending_payment = None
        self.last_interaction = datetime.now()
    
    def add_message(self, role, content):
        """Thêm message vào history (auto limit 10 messages)"""
        
    def set_pending_payment(self, payment_data):
        """Lưu đơn hàng đang chờ xác nhận"""
        
    def clear_pending_payment(self):
        """Xóa pending payment sau khi confirm/cancel"""
        
    def reset(self):
        """Reset context (timeout 5 phút)"""
```

### **2. Confirmation Detection**
```python
confirmation_keywords = [
    "oke", "ok", "okay", "được", "đồng ý", "xác nhận", 
    "chấp nhận", "đúng", "vâng", "dạ", "có", "uhm"
]

cancellation_keywords = [
    "không", "thôi", "hủy", "cancel", "đổi ý", "không lấy"
]
```

### **3. QR Code Generation**
```python
def generate_qr_code_data(payment_data):
    """
    Tạo QR code data với format:
    {
        "order_id": "ABC12345",
        "total_amount": 39000,
        "currency": "VND",
        "items": [...],
        "timestamp": "2024-..."
    }
    """
```

## 🚀 Cách sử dụng

### **Từ ESP32 (Audio)**
```cpp
// ESP32 gửi audio → Server transcribe
// Server tự động track conversation theo MAC address
// Không cần gửi history từ client
```

### **Từ Web Client**
```javascript
// Gửi text message
ws.send(JSON.stringify({
    type: 'chat',
    message: 'Cho tôi 1 bánh mì',
    mac_address: 'web-client-123'  // ← Client MAC để track context
}));
```

## 📊 Flow hoàn chỉnh

```
┌──────────────────────────────────────────────────────────────┐
│                    USER INTERACTION                           │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
                ┌────────────────┐
                │  Transcribe    │  (Whisper)
                │  Audio → Text  │
                └────────┬───────┘
                         │
                         ▼
                ┌────────────────────┐
                │ get_or_create_     │  ← Lấy context theo MAC
                │ context(mac_addr)  │
                └────────┬───────────┘
                         │
                         ▼
          ┌──────────────┴──────────────┐
          │                             │
    Has pending                    No pending
     payment?                       payment
          │                             │
          ▼                             ▼
  ┌───────────────┐           ┌──────────────────┐
  │ Check confirm │           │ Detect payment   │
  │ or cancel     │           │ intent           │
  └───────┬───────┘           └─────────┬────────┘
          │                             │
          ├─── "oke" ────→ Confirm      ├─── "mua" ──→ Process
          │                ↓            │              ↓
          │           Generate QR       │       Set pending_payment
          │                             │              ↓
          └─── "không" ──→ Cancel       └────→ Ask confirmation
                         ↓
                    Clear pending
```

## 🧪 Testing

Chạy test script:
```bash
cd "Model AI/Audio_webAI"
python test_payment_flow.py
```

Expected output:
```
TEST: PAYMENT FLOW VỚI CONVERSATION CONTEXT
============================================================

📝 BƯỚC 1: User đặt hàng
User: Cho tôi 1 bánh mì và 2 hộp sữa

Bot: Dạ, cho em xác nhận đơn hàng:
     - 1 cái Bánh mì: 15.000đ
     - 2 hộp Sữa: 24.000đ
     Tổng cộng: 39.000đ
     
     Anh/chị xác nhận đơn hàng này nhé?

✅ Context state:
   - Conversation history: 2 messages
   - Pending payment: YES
   - Order total: 39.000đ

📝 BƯỚC 2: User xác nhận
User: oke

Bot: Cảm ơn anh/chị! Đơn hàng đã được xác nhận.
     Tổng tiền: 39.000đ
     
     Đây là mã QR để thanh toán...

✅ Context state after confirmation:
   - Pending payment: NO
```

## 🔧 Các thay đổi trong code

### **server.py**
1. **Thêm ConversationContext class** (line ~40)
2. **Thêm conversation_contexts dict** (line ~38)
3. **Thêm get_or_create_context()** (line ~125)
4. **Thêm generate_qr_code_data()** (line ~145)
5. **Update get_ai_response()** - Thêm confirmation logic (line ~220)
6. **Update handle_payment_request()** - Lưu pending payment (line ~275)
7. **Update handle_normal_chat()** - Lưu conversation (line ~365)
8. **Update handle_audio_message()** - Pass mac_address (line ~564)
9. **Update handle_text_message()** - Pass mac_address (line ~641)

### **products.py**
Không thay đổi - vẫn giữ nguyên logic parse payment

## 📝 Notes

- **Auto-reset**: Context tự động reset sau 5 phút không tương tác
- **History limit**: Chỉ giữ 10 messages gần nhất để tiết kiệm tokens
- **MAC tracking**: Mỗi device có context riêng (ESP32, web client, etc.)
- **QR code**: Data được generate nhưng chưa có UI hiển thị (TODO)

## 🎯 Next Steps

1. **Tích hợp QR code UI** - Hiển thị QR code trên web/ESP32
2. **Payment gateway** - Kết nối với cổng thanh toán thực
3. **Order management** - Lưu lịch sử đơn hàng vào database
4. **Receipt printing** - In hóa đơn sau khi thanh toán
