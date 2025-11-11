# Cách Enable PSRAM cho ESP32-S3N16R8

## Trong Arduino IDE:

1. **Tools → Board** → chọn `ESP32S3 Dev Module` (hoặc board tương thích)

2. **Tools → PSRAM** → chọn `OPI PSRAM` (ESP32-S3 dùng OPI PSRAM)

3. **Tools → Flash Mode** → chọn `QIO 80MHz` hoặc `OPI 80MHz`

4. **Tools → Partition Scheme** → chọn scheme có PSRAM (ví dụ: `16MB Flash (3MB APP/9.9MB FATFS)`)

5. Upload code

## Kiểm tra PSRAM hoạt động:

Khi khởi động, bạn sẽ thấy log:
```
✅ PSRAM detected!
   Total PSRAM: 16777216 bytes (16.00 MB)
   Free PSRAM: 16777216 bytes (16.00 MB)
```

Nếu thấy:
```
⚠️ PSRAM NOT found - using internal RAM only!
```

→ Chưa enable đúng PSRAM settings!

## Lưu ý:

- ESP32-S3N16R8 có **16MB PSRAM** (Octal SPI)
- Phải chọn đúng board ESP32-S3 (không phải ESP32 thường)
- PSRAM setting phải là `OPI PSRAM` hoặc `QSPI PSRAM`
