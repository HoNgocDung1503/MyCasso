# Hướng dẫn hiển thị GIF lên màn hình ST7789 với ESP32

## 📋 Yêu cầu

### Phần cứng:
- ESP32 (bất kỳ board nào)
- Màn hình ST7789 (240x320)
- Dây kết nối

### Phần mềm:
- Arduino IDE (đã cài đặt ESP32 board)
- Python 3.x
- Thư viện Python: Pillow

## 🔌 Sơ đồ kết nối

```
ST7789        ESP32
------------------------
VCC     -->   3.3V
GND     -->   GND
CS      -->   GPIO 5
DC      -->   GPIO 16
RST     -->   GPIO 17
SDA     -->   GPIO 23 (MOSI)
SCK     -->   GPIO 18 (SCLK)
```

## 📦 Cài đặt thư viện Arduino

1. Mở Arduino IDE
2. Vào **Sketch → Include Library → Manage Libraries**
3. Tìm và cài đặt:
   - `Adafruit ST7789`
   - `Adafruit GFX Library`

## 🔧 Cài đặt Python và Pillow

```bash
# Cài đặt Python (nếu chưa có)
# Download từ https://www.python.org/downloads/

# Cài đặt Pillow
pip install Pillow
```

## 🎬 Các bước thực hiện

### Bước 1: Chuyển đổi GIF thành mảng C++

Mở PowerShell/Terminal tại thư mục Downloads:

```powershell
cd C:\Users\DUNGHO\Downloads

# Chuyển đổi 1 file GIF

python gif_to_array_optimized.py "Emoji Dasai Mochi_boiroi.gif" --max-size 80 --max-frames 20 --skip-frames 2 --output emoji_boiroi

//  * Tham số để TĂNG CHẤT LƯỢNG:
//  * --max-size 100-150    : Kích thước lớn hơn (sắc nét hơn)
//  * --max-frames 40-50    : Nhiều frame hơn (mượt hơn)
//  * --skip-frames 0-1     : Bỏ qua ít frame hơn (mượt hơn)
```

Script sẽ tạo ra các file `.h` chứa dữ liệu GIF đã chuyển đổi.

Ví dụ: `emoji1.gif` → `emoji1_frames.h`

### Bước 2: Copy file .h vào thư mục Arduino sketch

1. Copy các file `.h` vừa tạo
2. Paste vào cùng thư mục với file `emoji_display_st7789.ino`

### Bước 3: Chỉnh sửa code Arduino

Mở file `emoji_display_st7789.ino` và uncomment các dòng sau:

```cpp
// Include các file GIF đã chuyển đổi
#include "emoji1_frames.h"
#include "emoji2_frames.h"
#include "emoji3_frames.h"
```

Trong hàm `loop()`, uncomment và chỉnh sửa:

```cpp
void loop() {
  // Phát emoji 1
  playAnimation(emoji1_frames, emoji1_WIDTH, emoji1_HEIGHT, 
                emoji1_FRAMES, emoji1_durations, 60, 80, 2);
  
  delay(500);
  
  // Phát emoji 2
  playAnimation(emoji2_frames, emoji2_WIDTH, emoji2_HEIGHT, 
                emoji2_FRAMES, emoji2_durations, 60, 160, 2);
  
  delay(500);
  
  // Phát emoji 3
  playAnimation(emoji3_frames, emoji3_WIDTH, emoji3_HEIGHT, 
                emoji3_FRAMES, emoji3_durations, 60, 240, 2);
  
  delay(1000);
}
```

### Bước 4: Upload lên ESP32

1. Chọn board: **Tools → Board → ESP32 Dev Module**
2. Chọn COM port: **Tools → Port → COMx**
3. Click **Upload** (nút mũi tên →)

## 📝 Giải thích các hàm

### `playAnimation()`

```cpp
playAnimation(
  frames,      // Mảng chứa frames
  width,       // Chiều rộng GIF
  height,      // Chiều cao GIF
  frameCount,  // Số frames
  durations,   // Thời gian mỗi frame
  x,           // Vị trí X trên màn hình
  y,           // Vị trí Y trên màn hình
  loops        // Số lần lặp (0=1 lần, 1=2 lần, -1=vô hạn)
);
```

### `playAnimationScaled()`

Tương tự `playAnimation()` nhưng có thêm tham số `scale` để phóng to/thu nhỏ:

```cpp
playAnimationScaled(..., scale, loops);
// scale = 1: kích thước gốc
// scale = 2: phóng to 2 lần
// scale = 3: phóng to 3 lần
```

## 💡 Lưu ý

1. **Kích thước GIF**: 
   - GIF nhỏ hơn 100x100 pixel sẽ load nhanh hơn
   - GIF lớn hơn 150x150 pixel có thể hết RAM ESP32

2. **Số frames**:
   - Càng nhiều frames thì càng tốn RAM
   - Nên giữ dưới 20 frames cho mỗi GIF

3. **Tối ưu hóa**:
   - Giảm kích thước GIF trước khi chuyển đổi
   - Giảm số màu trong GIF (256 màu hoặc ít hơn)
   - Giảm số frames nếu cần thiết

4. **Memory**:
   - Mỗi pixel = 2 bytes (RGB565)
   - GIF 100x100, 10 frames = 100 x 100 x 10 x 2 = ~195 KB
   - ESP32 có khoảng 320KB RAM (SRAM)
