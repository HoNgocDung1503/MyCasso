

// python gif_to_array_optimized.py "Emoji Dasai Mochi_khoc.gif" --max-size 64 --max-frames 15 --skip-frames 2 --output emoji_khoc


//  * Tham số để TĂNG CHẤT LƯỢNG:
//  * --max-size 100-150    : Kích thước lớn hơn (sắc nét hơn)
//  * --max-frames 40-50    : Nhiều frame hơn (mượt hơn)
//  * --skip-frames 0-1     : Bỏ qua ít frame hơn (mượt hơn)

// mới chỉnh sửa, test ok rồi nhé
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>

#include "emoji_hon_frames.h"       // Hôn: 80x48 frames 80 30
#include "emoji_batngo_frames.h"    // Bất ngờ: 80x48 frames 80 50 lang nghe
#include "emoji_buonngu_frames.h"   //buồn ngủ: 80 x48 frames 80 40 
#include "emoji_tutin_frames.h"       // Tự tin: 80x48 frames 80 50 noi chuyen
#include "emoji_cuoilon_frames.h"  // Cười lớn: 80x48 frames 80 30
#include "emoji_boiroi_frames.h"  // Bối rối: 80x48 frames 80 30
#include "emoji_haihuoc_frames.h"  // Hài hước: 80x48 frames 80 50
#include "emoji_thoaimai4_frames.h" // Thoải mái4: 80x48 frames 80 50
#include "emoji_thoaimai_frames.h" // Thoải mái: 80x48 frames 80 50
#include "emoji_ngongan_frames.h" // Ngóng ăn: 80x48 frames 80 40

// ST7789 Pin definitions for ESP32
#define TFT_CS   5
#define TFT_DC   16
#define TFT_RST  17
#define TFT_MOSI 23  // SDA
#define TFT_SCLK 18  // SCK

// Create display object
Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);

// Biến để tracking animation
int currentFrame = 0;
unsigned long lastFrameTime = 0;

const int ANIMATION_SPEED = 3; // Tăng lên 15x để animation mượt và nhanh hơn

// Ngưỡng màu (định nghĩa 1 lần, dùng cho tất cả hàm)
const uint16_t WHITE_THRESHOLD = 0xF7DE;  // Màu trắng/gần trắng
const uint16_t BLACK_THRESHOLD = 0x2000;  // Màu đen/tối (mắt emoji)
const uint16_t EYE_COLOR = 0xF800;        // Màu đỏ cho mắt

// Cấu trúc để lưu thông tin emoji
struct EmojiInfo {
  const uint16_t* frames;
  int width;
  int height;
  int frameCount;
  const int* durations;
  int scale;
  int loops;
};

// Forward declarations - khai báo trước các hàm
void drawFrame(const uint16_t* frameData, int width, int height, int x, int y);
void drawFrameScaled(const uint16_t* frameData, int width, int height, int x, int y, int scale);
void playAnimation(const uint16_t* frames, int width, int height, int frameCount, const int* durations, int x, int y, int loops = 1);
void playAnimationScaled(const uint16_t* frames, int width, int height, int frameCount, const int* durations, int x, int y, int scale, int loops = 1);
void demoMode();

void setup() {
  Serial.begin(115200);
  Serial.println("ST7789 GIF Animation Display");

  // Khởi tạo SPI
  SPI.begin(TFT_SCLK, -1, TFT_MOSI, TFT_CS);
  
  // Initialize display
  tft.init(240, 320); 
  tft.setRotation(3);   // Xoay màn hình nếu cần (0-3)
  tft.fillScreen(ST77XX_RED);
  
  delay(2000);
  tft.fillScreen(ST77XX_RED);
}

void loop() {
  const int SCREEN_WIDTH = 320;
  const int SCREEN_HEIGHT = 240;
  const int BASE_SCALE = 3;
  // Danh sách các emoji để phát 
  EmojiInfo emojis[] = {
    // HON (Hôn)
    {
      (const uint16_t*)emoji_hon_frames,
      emoji_hon_WIDTH,
      emoji_hon_HEIGHT,
      emoji_hon_FRAMES,
      emoji_hon_durations,
      BASE_SCALE,
      2
    },


    // BATNGO (Bất ngờ)
    {
      (const uint16_t*)emoji_batngo_frames,
      emoji_batngo_WIDTH,
      emoji_batngo_HEIGHT,
      emoji_batngo_FRAMES,
      emoji_batngo_durations,
      BASE_SCALE,
      2
    },
    // BUONNGU (Buồn ngủ) 
    {
      (const uint16_t*)emoji_buonngu_frames,
      emoji_buonngu_WIDTH,
      emoji_buonngu_HEIGHT,
      emoji_buonngu_FRAMES,
      emoji_buonngu_durations,
      BASE_SCALE ,  
      3
    },

    // TUTIN (Tự tin)
    {
      (const uint16_t*)emoji_tutin_frames,
      emoji_tutin_WIDTH,
      emoji_tutin_HEIGHT,
      emoji_tutin_FRAMES,
      emoji_tutin_durations,
      BASE_SCALE,
      2
    },

   // CUOILON (Cười lớn)
    {
      (const uint16_t*)emoji_cuoilon_frames,
      emoji_cuoilon_WIDTH,
      emoji_cuoilon_HEIGHT,
      emoji_cuoilon_FRAMES,
      emoji_cuoilon_durations,
      BASE_SCALE,
      3
    },
    // BOIROI (Bối rối)
      {
        (const uint16_t*)emoji_boiroi_frames,
        emoji_boiroi_WIDTH,
        emoji_boiroi_HEIGHT,
        emoji_boiroi_FRAMES,
        emoji_boiroi_durations,
        BASE_SCALE,
        2
      },
    // HAIHUOC (Hài hước)
      {
        (const uint16_t*)emoji_haihuoc_frames,
        emoji_haihuoc_WIDTH,
        emoji_haihuoc_HEIGHT,
        emoji_haihuoc_FRAMES,
        emoji_haihuoc_durations,
        BASE_SCALE,
        2
      },
    // THOAIMAI4 (Thoải mái4)
      {
        (const uint16_t*)emoji_thoaimai4_frames,
        emoji_thoaimai4_WIDTH,
        emoji_thoaimai4_HEIGHT,
        emoji_thoaimai4_FRAMES,
        emoji_thoaimai4_durations,
        BASE_SCALE,
        2
      },
    // THOAIMAI (Thoải mái)
      {
        (const uint16_t*)emoji_thoaimai_frames,
        emoji_thoaimai_WIDTH,
        emoji_thoaimai_HEIGHT,
        emoji_thoaimai_FRAMES,
        emoji_thoaimai_durations,
        BASE_SCALE,
        2
      },
    // NGONGAN (Ngóng ăn)
      {
        (const uint16_t*)emoji_ngongan_frames,
        emoji_ngongan_WIDTH,
        emoji_ngongan_HEIGHT,
        emoji_ngongan_FRAMES,
        emoji_ngongan_durations,
        BASE_SCALE,
        3
      }
  };
  // Phát từng emoji
  const int numEmojis = sizeof(emojis) / sizeof(emojis[0]);
  for (int i = 0; i < numEmojis; i++) {
    // Tính toán vị trí căn giữa
    int x = (SCREEN_WIDTH - emojis[i].width * emojis[i].scale) / 2;
    int y = (SCREEN_HEIGHT - emojis[i].height * emojis[i].scale) / 2;
    
    // Phát animation
    playAnimationScaled(
      emojis[i].frames,
      emojis[i].width,
      emojis[i].height,
      emojis[i].frameCount,
      emojis[i].durations,
      x, y,
      emojis[i].scale,
      emojis[i].loops
    );
    
    delay(300); 
  }
}

void drawFrame(const uint16_t* frameData, int width, int height, int x, int y) {
  tft.startWrite();
  
  // Vẽ từng pixel
  for (int py = 0; py < height; py++) {
    for (int px = 0; px < width; px++) {
      uint16_t color = pgm_read_word(&frameData[py * width + px]);

      if (color <= WHITE_THRESHOLD) {
        tft.writePixel(x + px, y + py, color);
      }
    }
  }
  
  tft.endWrite();
}

void drawFrameScaled(const uint16_t* frameData, int width, int height, 
                     int x, int y, int scale) {
  tft.startWrite();
  
  if (scale == 1) {
    // Không scale - vẽ trực tiếp (nhanh nhất)
    for (int py = 0; py < height; py++) {
      for (int px = 0; px < width; px++) {
        uint16_t color = pgm_read_word(&frameData[py * width + px]);
        if (color <= WHITE_THRESHOLD) {
          // Thay màu đen/tối (mắt) sang màu đỏ
          if (color < BLACK_THRESHOLD) {
            color = EYE_COLOR;
          }
          tft.writePixel(x + px, y + py, color);
        }
      }
    }
  } else {
    // Scale - vẽ các khối pixel đã scale
    for (int py = 0; py < height; py++) {
      for (int px = 0; px < width; px++) {
        uint16_t color = pgm_read_word(&frameData[py * width + px]);
        if (color <= WHITE_THRESHOLD) {
          // Thay màu đen/tối (mắt) sang màu đỏ
          if (color < BLACK_THRESHOLD) {
            color = EYE_COLOR;
          }
         
          tft.writeFillRect(x + px * scale, y + py * scale, scale, scale, color);
        }
      }
    }
  }
  
  tft.endWrite(); 
}

void playAnimation(const uint16_t* frames, int width, int height,
                   int frameCount, const int* durations, 
                   int x, int y, int loops) {
  int loopCount = 0;
  int frameSize = width * height;
  
  while (loops == -1 || loopCount <= loops) {
    for (int i = 0; i < frameCount; i++) {
      // Vẽ frame - trỏ tới frame thứ i
      drawFrame(&frames[i * frameSize], width, height, x, y);
      
      // Delay theo thời gian của frame
      delay(durations[i]);
    }
    
    loopCount++;
    if (loops == 0) break; // Chỉ chạy 1 lần
  }
}

void playAnimationScaled(const uint16_t* frames, int width, int height,
                         int frameCount, const int* durations, 
                         int x, int y, int scale, int loops) {
  int loopCount = 0;
  int frameSize = width * height;
  
  while (loops == -1 || loopCount <= loops) {
    for (int i = 0; i < frameCount; i++) {
      // Vẽ frame với scale - trỏ tới frame thứ i
      drawFrameScaled(&frames[i * frameSize], width, height, x, y, scale);
      
      // Đọc duration từ PROGMEM
      int frameDuration = pgm_read_word(&durations[i]);
      
      // Delay theo thời gian của frame (chia cho ANIMATION_SPEED để tăng tốc)
      delay(frameDuration / ANIMATION_SPEED);
    }
    
    loopCount++;
    if (loops == 0) break;
  }
}

