# Hệ thống Chat AI với Text và Voice Input/Output
## Cấu trúc Audio Message Wire Protocol
### Message Format
```
macAddress → type → id → data
```
### Binary Layout
```
+----------------+------------------+
| Length (2B)    | macAddress       | UTF-8 string
+----------------+------------------+
| Length (2B)    | type             | UTF-8 string (START/PROCESSING/END)
+----------------+------------------+
| Length (2B)    | id               | UTF-8 string (UUID format)
+----------------+------------------+
| Length (4B)    | data             | Audio data (PCM int16)
+----------------+------------------+
```

### Message Types

1. **START** - Bắt đầu audio session
   - `data` field rỗng (length = 0)
   - Server trả lời START acknowledgment

2. **PROCESSING** - Gửi audio chunks
   - `data` chứa PCM int16 audio samples
   - Format: 24kHz, mono, 16-bit PCM
   - Each int16 sample là little-endian

3. **END** - Kết thúc audio session
   - `data` field rỗng (length = 0)
   - Server xử lý audio và trả lời
   - Server gửi END acknowledgment

### Audio Format
- **Sample Rate**: 24,000 Hz
- **Channels**: 1 (mono)
- **Sample Format**: 16-bit signed integer PCM (little-endian per sample)
- **Byte Order**: Each int16 sample is little-endian within the data field



## Sử dụng

### Cách nhanh nhất: Chạy bằng file `start.bat`

**Bước 1:** Mở file `.env` và điền API key của bạn:
```
OPENAI_API_KEY=sk-your-actual-api-key-here
```

**Bước 2:** Chạy file `start.bat` (double-click hoặc từ terminal):
```powershell
.\start.bat
```
**Bước 3:** Mở file `index.html` trong trình duyệt

---



#### Binary Messages (Audio Protocol)
- Format: Wire Protocol (macAddress → type → id → data)
- Used for: Voice input/output

#### JSON Messages (Text Protocol)
```json
// Request
{
    "type": "chat",
    "message": "Xin chào",
    "history": [...],
    "voice_output": true,
    "mac_address": "web-client-xxx"
}

// Response
{
    "type": "chat_response",
    "message": "Xin chào! Tôi có thể giúp gì cho bạn?"
}
```

