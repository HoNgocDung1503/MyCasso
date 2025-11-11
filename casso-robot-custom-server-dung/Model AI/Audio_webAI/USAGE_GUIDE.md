# 🚀 Hướng dẫn sử dụng tính năng Conversation Memory

## ✨ Tính năng mới

Server giờ đây **nhớ được cuộc hội thoại** và có thể **xử lý xác nhận thanh toán**!

## 🎯 Kịch bản sử dụng

### **Ví dụ 1: Thanh toán thành công**

```
👤 User: "Cho tôi 1 bánh mì và 2 hộp sữa"

🤖 Bot:  "Dạ, cho em xác nhận đơn hàng:
          - 1 cái Bánh mì: 15.000đ
          - 2 hộp Sữa: 24.000đ
          Tổng cộng: 39.000đ
          
          Anh/chị xác nhận đơn hàng này nhé?"

👤 User: "oke" / "được" / "xác nhận"

🤖 Bot:  "Cảm ơn anh/chị! Đơn hàng đã được xác nhận.
          Tổng tiền: 39.000đ
          
          Đây là mã QR để thanh toán. Vui lòng quét mã để hoàn tất."
```

### **Ví dụ 2: Hủy đơn hàng**

```
👤 User: "Cho tôi 3 chai nước ngọt"

🤖 Bot:  "Dạ, cho em xác nhận đơn hàng:
          - 3 chai Nước ngọt: 45.000đ
          Tổng cộng: 45.000đ
          
          Anh/chị xác nhận đơn hàng này nhé?"

👤 User: "không" / "thôi" / "hủy"

🤖 Bot:  "Dạ, tôi đã hủy đơn hàng. Anh/chị cần gì thêm không ạ?"
```

### **Ví dụ 3: Chat liên tục**

```
👤 User: "Bạn có bán cà phê không?"

🤖 Bot:  "Dạ có ạ! Cà phê của shop là 25.000đ/ly."

👤 User: "Vậy cho tôi 2 ly"

🤖 Bot:  "Dạ, cho em xác nhận đơn hàng:
          - 2 ly Cà phê: 50.000đ
          Tổng cộng: 50.000đ
          
          Anh/chị xác nhận đơn hàng này nhé?"

👤 User: "xác nhận"

🤖 Bot:  "Cảm ơn anh/chị! Đơn hàng đã được xác nhận..."
```

## 🔑 Từ khóa quan trọng

### **Xác nhận đơn hàng:**
- ✅ "oke", "ok", "okay"
- ✅ "được", "đồng ý"
- ✅ "xác nhận", "chấp nhận"
- ✅ "đúng", "vâng", "dạ"
- ✅ "có", "uhm"

### **Hủy đơn hàng:**
- ❌ "không", "thôi"
- ❌ "hủy", "cancel"
- ❌ "đổi ý", "không lấy"

## 🎮 Cách hoạt động

1. **Mỗi device** (theo MAC address) có 1 **conversation context** riêng
2. Server **tự động lưu** lịch sử chat (10 messages gần nhất)
3. Khi user đặt hàng → Server lưu vào **pending payment**
4. Khi user xác nhận/hủy → Server xử lý và **clear pending**
5. Context **tự động reset** sau 5 phút không tương tác

## 🧪 Test ngay

### **Test 1: Context persistence**
```bash
cd "Model AI/Audio_webAI"
python test_context_quick.py
```

### **Test 2: Payment flow** (cần OpenAI API)
```bash
python test_payment_flow.py
```

## 📊 Monitoring

Server sẽ log các sự kiện quan trọng:

```
💰 PAYMENT REQUEST
   User: Cho tôi 1 bánh mì
   Items: 1
   Total: 15.000đ
   AI Response: Dạ, cho em xác nhận...
   ⏳ Pending confirmation...

✅ Payment confirmed for MAC AA:BB:CC:DD:EE:FF

❌ Payment cancelled for MAC AA:BB:CC:DD:EE:FF
```

## 🔧 Technical Details

### **Auto-reset timeout**
- Context reset sau **5 phút** không tương tác
- Tránh memory leak khi user không confirm/cancel

### **History limit**
- Chỉ giữ **10 messages** gần nhất
- Tiết kiệm tokens cho OpenAI API

### **MAC-based tracking**
- ESP32: Sử dụng WiFi MAC address
- Web client: Custom identifier (e.g., "web-client-123")

## 🚀 Integration với ESP32

**ESP32 không cần thay đổi code!**

Server tự động:
1. Nhận audio từ ESP32
2. Transcribe với Whisper
3. Lấy context theo MAC address
4. Xử lý logic confirmation
5. TTS response về ESP32

## 📝 Notes

- ✅ **Không cần gửi history từ client** - Server tự quản lý
- ✅ **Multi-user support** - Mỗi MAC có context riêng
- ✅ **Auto-cleanup** - Context cũ tự động xóa
- ⏳ **QR code UI** - Chưa implement (TODO)

## 🎓 Tài liệu chi tiết

Xem file `README_ConversationContext.md` để hiểu:
- Flow diagram chi tiết
- Code structure
- State machine logic
- Test scenarios

---

**Happy coding! 🎉**
