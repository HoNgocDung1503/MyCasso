// Đã có trong audio.ino:
#include <Arduino.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <driver/i2s.h>

// Thêm mới cho TFT:
#include <Adafruit_GFX.h>      // v1.11.x
#include <Adafruit_ST7789.h>   // v1.10.x
#include <SPI.h>
#include "FontMaker.h"         // Custom font tiếng Việt
```

---

## ⚠️ Lưu ý quan trọng

### Memory Management
- **PSRAM:** Ưu tiên cho audio buffers (1.6MB)
- **Internal RAM:** Dùng cho TFT buffers, chat history
- **Stack size:** TFT task cần 8KB stack

### Priority
```
Audio playback task: Priority 4, Core 0
WebSocket loop: Priority -, Core 1 (main loop)
TFT update task: Priority 2, Core 1