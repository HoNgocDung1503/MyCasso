//update 10/11 - ULTRA-FAST: Sync with server.py + remove ALL delays
// mic inmp441, loa max98357a, esp32s3n16r8 (16MB PSRAM)
// Server tối ưu: chunk 8KB, delay 5ms, asyncio.gather song song
// 
// THAY ĐỔI CHỦ YẾU (ULTRA-FAST):
// ✅ Tăng chunk size từ 4KB → 8KB để khớp với server.py
// ✅ Giảm overhead transmission (ít chunks hơn = nhanh hơn)
// ✅ Server xử lý song song text + audio (asyncio.gather)
// ✅ Tối ưu log output (30 chunks thay vì 20)
// ✅ Buffer audio lớn hơn: ~1.6MB (200×8KB) thay vì ~800KB
// ✅ Allocate buffers động trong heap thay vì stack để tránh overflow
// 🚀 BỎ HẾT DELAYS: 300ms→50ms, 100ms→10ms, 500ms→100ms, delay(2) throttle→bỏ
// 🚀 I2S DMA buffer: 8×512 → 4×256 (giảm 4x latency)
// 🚀 I2S write timeout: portMAX_DELAY → 50ms (không block)
// 🚀 Audio playback priority: 3 → 4 (cao nhất)
// 🚀 END signal delay: 200ms → 50ms (nhanh 4x)
//hihi hihi
#include <Arduino.h>
#include "SPIFFS.h"
#include <driver/i2s.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <esp_bt.h>
#include <ArduinoJson.h>
#include <base64.h>
#include <esp_wifi.h>
#include <esp_heap_caps.h>  // Để dùng PSRAM
// hihi
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"

const char* ssid = "dev";
const char* password = "123456789";

//nếu đổi wifi: ipconfig | Select-String "IPv4"
const char* ws_host = "192.168.137.1";  // ✅ Cập nhật IP mới
const uint16_t ws_port = 8765; 
const char* ws_path = "/";
  
WebSocketsClient webSocket;


const int BUTTON_PIN = 9;
bool isRecording = false;
bool autoRecordingMode = false;  // Chế độ tự động thu âm liên tục
unsigned long audioFinishedTime = 0;  // Thời điểm audio phát xong
bool waitingToRestart = false;  // Đang đợi 3 giây để bật lại mic

// === Audio Playback Queue ===
#define MAX_AUDIO_QUEUE 1000  // Tăng lên 200 vì đã có PSRAM (16MB) - đủ cho bài dài
struct AudioChunk {
  uint8_t* data;
  size_t length;
  bool valid;
};

AudioChunk audioQueue[MAX_AUDIO_QUEUE];
volatile int queueHead = 0;
volatile int queueTail = 0;
volatile int queueCount = 0;
SemaphoreHandle_t queueMutex = NULL;
TaskHandle_t audioPlaybackTask = NULL;

// === WebSocket Health Monitoring ===
#define PING_INTERVAL 30000
#define PONG_TIMEOUT 60000
#define RECONNECT_COOLDOWN 5000
#define MAX_RECONNECT_ATTEMPTS 5

unsigned long lastPingTime = 0;
unsigned long lastPongTime = 0;
unsigned long lastReconnectAttempt = 0;
int reconnectAttempts = 0;
bool wsConnected = false;

// === Audio Recording Settings ===
#define I2S_SAMPLE_RATE 24000  // Khớp với server.py - 24kHz
#define I2S_READ_LEN 8192      // Tăng từ 4KB → 8KB để khớp với server
#define CHUNK_SIZE 8192        // Tăng từ 4KB → 8KB để khớp với server.py chunk_size
#define SILENCE_THRESHOLD 150.0f
#define SILENCE_DURATION 3000  // 3 giây im lặng (giảm từ 5s)

bool recordingActive = false;
bool playbackActive = false;
bool endSignalReceived = false;
unsigned long playbackStartTime = 0;
unsigned long waitingForAudioStartTime = 0;



// --- I2S Speaker Config - Optimized DMA ---
#define I2S_SPEAKER_PORT I2S_NUM_1
#define I2S_SPEAKER_BCLK 15
#define I2S_SPEAKER_LRC 16
#define I2S_SPEAKER_DIN 7

// --- I2S Mic Config ---
const i2s_port_t I2S_PORT = I2S_NUM_0;

i2s_pin_config_t pin_config = {
  .bck_io_num = 5,
  .ws_io_num = 4,
  .data_out_num = I2S_PIN_NO_CHANGE,
  .data_in_num = 6
};

// ✅ Allocate buffers động trong heap/PSRAM thay vì stack để tránh overflow
uint8_t* i2sBuffer = nullptr;   // 8KB - sẽ allocate trong setup()
uint8_t* pcmBuffer = nullptr;   // 8KB - sẽ allocate trong setup()

String deviceMacAddress = "";  
String sessionId = "";

// ====== Enhanced Audio Filter for Speech Recognition ======
class AudioFilter {
private:
  float prevInput = 0;
  float prevOutput = 0;
  
  // Noise gate
  const float noiseGateThreshold = 50.0f;
  
  // Pre-emphasis filter for speech clarity
  float preEmphasis_prev = 0;
  const float preEmphasis_coeff = 0.5f;
  
  // AGC (Automatic Gain Control)
  float currentGain = 2.0f;
  float targetGain = 2.0f;
  const float gainSmoothFactor = 0.001f;
  float peakLevel = 0;
  const float peakDecay = 0.999f;
  
public:
  int16_t processSample(int16_t sample) {
    float input = (float)sample;
    
    // 1. DC Blocker
    float alpha = 0.95f;
    float dcBlocked = input - prevInput + alpha * prevOutput;
    prevInput = input;
    prevOutput = dcBlocked;
    
    // 2. Noise Gate - loại bỏ nhiễu nền
    if (fabs(dcBlocked) < noiseGateThreshold) {
      dcBlocked *= 0.3f; // Giảm nhiễu xuống 30%
    }
    
    // 3. Pre-emphasis filter - tăng clarity cho giọng nói
    float emphasized = dcBlocked - preEmphasis_coeff * preEmphasis_prev;
    preEmphasis_prev = dcBlocked;
    
    // 4. AGC - tự động điều chỉnh âm lượng
    float absVal = fabs(emphasized);
    if (absVal > peakLevel) {
      peakLevel = absVal;
    } else {
      peakLevel *= peakDecay;
    }
    
    // Tính target gain dựa trên peak level
    if (peakLevel > 1000.0f) {
      targetGain = 28000.0f / (peakLevel + 100.0f);
    } else {
      targetGain = 2.5f; // Gain mặc định cao hơn
    }
    
    // Smooth gain transition
    currentGain += (targetGain - currentGain) * gainSmoothFactor;
    
    // Apply gain
    float output = emphasized * currentGain;
    
    // 5. Soft limiting
    if (output > 32000.0f) output = 32000.0f;
    if (output < -32000.0f) output = -32000.0f;
    
    return (int16_t)output;    
  }
  
  void reset() {
    prevInput = 0;
    prevOutput = 0;
    preEmphasis_prev = 0;
    currentGain = 2.0f;
    targetGain = 2.0f;
    peakLevel = 0;
  }
};

// ====== ENHANCED Audio Smoother với Professional DSP ======
class EnhancedAudioSmoother {
private:
  struct BiquadFilter {
    float b0, b1, b2, a1, a2;
    float x1 = 0, x2 = 0, y1 = 0, y2 = 0;
    
    void setLowPass(float sampleRate, float cutoffFreq, float Q = 0.707f) {
      float w0 = 2.0f * PI * cutoffFreq / sampleRate;
      float cosw0 = cos(w0);
      float sinw0 = sin(w0);
      float alpha = sinw0 / (2.0f * Q);
      
      float a0 = 1.0f + alpha;
      b0 = ((1.0f - cosw0) / 2.0f) / a0;
      b1 = (1.0f - cosw0) / a0;
      b2 = ((1.0f - cosw0) / 2.0f) / a0;
      a1 = (-2.0f * cosw0) / a0;
      a2 = (1.0f - alpha) / a0;
    }
    
    float process(float input) {
      float output = b0 * input + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
      x2 = x1; x1 = input;
      y2 = y1; y1 = output;
      return output;
    }
    
    void reset() {
      x1 = x2 = y1 = y2 = 0;
    }
  };
  
  BiquadFilter lpf;
  float dcBlocker_x1 = 0, dcBlocker_y1 = 0;
  const float dcBlocker_R = 0.995f;
  
  static const int INTERP_SIZE = 3;
  float interpBuffer[INTERP_SIZE] = {0};
  int interpIndex = 0;
  
  float targetGain = 1.0f;  // Âm lượng loa mặc định 100%
  float currentGain = 1.0f;
  const float gainSmoothFactor = 0.0001f;
  
  float peakEnvelope = 0;
  const float attackTime = 0.001f;
  const float releaseTime = 0.100f;
  float attackCoeff, releaseCoeff;
  
  float softClip(float x, float threshold = 0.85f) {
    float absX = fabs(x);
    if (absX < threshold) {
      return x;
    } else {
      float sign = (x > 0) ? 1.0f : -1.0f;
      float excess = absX - threshold;
      return sign * (threshold + excess / (1.0f + excess * excess));
    }
  }
  
  int fadeCounter = 0;
  static const int FADE_SAMPLES = 96;
  bool isFadingIn = true;
  
public:
  EnhancedAudioSmoother() {
    lpf.setLowPass(24000.0f, 8000.0f, 0.707f);
    attackCoeff = exp(-1.0f / (24000.0f * attackTime));
    releaseCoeff = exp(-1.0f / (24000.0f * releaseTime));
  }
  
  void reset() {
    lpf.reset();
    dcBlocker_x1 = dcBlocker_y1 = 0;
    interpIndex = 0;
    for (int i = 0; i < INTERP_SIZE; i++) interpBuffer[i] = 0;
    currentGain = 1.0f;  // Reset về 100% volume
    targetGain = 1.0f;
    peakEnvelope = 0;
    fadeCounter = 0;
    isFadingIn = true;
  }
  
  int16_t processSample(int16_t sample) {
    float input = sample / 32768.0f;
    
    float dcBlocked = input - dcBlocker_x1 + dcBlocker_R * dcBlocker_y1;
    dcBlocker_x1 = input;
    dcBlocker_y1 = dcBlocked;
    
    float filtered = lpf.process(dcBlocked);
    
    interpBuffer[interpIndex] = filtered;
    interpIndex = (interpIndex + 1) % INTERP_SIZE;
    
    float smoothed = 0;
    for (int i = 0; i < INTERP_SIZE; i++) {
      smoothed += interpBuffer[i];
    }
    smoothed /= INTERP_SIZE;
    
    currentGain += (targetGain - currentGain) * gainSmoothFactor;
    float gained = smoothed * currentGain;
    
    float absVal = fabs(gained);
    if (absVal > peakEnvelope) {
      peakEnvelope = attackCoeff * peakEnvelope + (1.0f - attackCoeff) * absVal;
    } else {
      peakEnvelope = releaseCoeff * peakEnvelope + (1.0f - releaseCoeff) * absVal;
    }
    
    if (peakEnvelope > 0.8f) {
      float reduction = 0.8f / (peakEnvelope + 0.001f);
      gained *= reduction;
    }
    
    gained = softClip(gained, 0.85f);
    
    if (isFadingIn && fadeCounter < FADE_SAMPLES) {
      float fadeGain = 0.5f * (1.0f - cos(PI * fadeCounter / FADE_SAMPLES));
      gained *= fadeGain;
      fadeCounter++;
    }
    
    if (gained > 0.95f) gained = 0.95f;
    if (gained < -0.95f) gained = -0.95f;
    
    int32_t output = (int32_t)(gained * 32767.0f);
    
    return (int16_t)output;
  }
  
  void processBuffer(int16_t* buffer, size_t numSamples) {
    for (size_t i = 0; i < numSamples; i++) {
      buffer[i] = processSample(buffer[i]);
    }
  }
  
  void setGain(float gain) {
    targetGain = gain;
  }
};

AudioFilter audioFilter;
EnhancedAudioSmoother outputSmoother;

// === Audio Queue Functions ===
bool enqueueAudio(const uint8_t* data, size_t length) {
  if (xSemaphoreTake(queueMutex, pdMS_TO_TICKS(100)) != pdTRUE) {
    return false;
  }
  
  if (queueCount >= MAX_AUDIO_QUEUE) {
    Serial.printf("⚠️ Audio queue FULL (%d/%d) - Dropping chunk!\n", queueCount, MAX_AUDIO_QUEUE);
    xSemaphoreGive(queueMutex);
    return false;
  }
  
  // Allocate memory from PSRAM (16MB available on ESP32-S3N16R8)
  uint8_t* buffer = (uint8_t*)heap_caps_malloc(length, MALLOC_CAP_SPIRAM);
  if (!buffer) {
    // Fallback to internal RAM if PSRAM fails
    buffer = (uint8_t*)malloc(length);
    if (!buffer) {
      Serial.println("❌ Out of memory for audio chunk!");
      xSemaphoreGive(queueMutex);
      return false;
    }
  }
  
  memcpy(buffer, data, length);
  
  audioQueue[queueTail].data = buffer;
  audioQueue[queueTail].length = length;
  audioQueue[queueTail].valid = true;
  
  queueTail = (queueTail + 1) % MAX_AUDIO_QUEUE;
  queueCount++;
  
  xSemaphoreGive(queueMutex);
  return true;
}

AudioChunk dequeueAudio() {
  AudioChunk chunk = {NULL, 0, false};
  
  if (xSemaphoreTake(queueMutex, pdMS_TO_TICKS(10)) != pdTRUE) {
    return chunk;
  }
  
  if (queueCount > 0) {
    chunk = audioQueue[queueHead];
    audioQueue[queueHead].valid = false;
    queueHead = (queueHead + 1) % MAX_AUDIO_QUEUE;
    queueCount--;
  }
  
  xSemaphoreGive(queueMutex);
  return chunk;
}

void clearAudioQueue() {
  if (xSemaphoreTake(queueMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
    for (int i = 0; i < MAX_AUDIO_QUEUE; i++) {
      if (audioQueue[i].valid && audioQueue[i].data) {
        free(audioQueue[i].data);
        audioQueue[i].data = NULL;
        audioQueue[i].valid = false;
      }
    }
    queueHead = 0;
    queueTail = 0;
    queueCount = 0;
    xSemaphoreGive(queueMutex);
  }
}

// === Audio Playback Task ===
void audioPlaybackTaskFunction(void* parameter) {
  Serial.println("🔊 Audio playback task started");
  
  int totalChunksPlayed = 0;
  
  while (true) {
    AudioChunk chunk = dequeueAudio();
    
    if (chunk.valid && chunk.data) {
      // Process audio with smoother
      int16_t* audioSamples = (int16_t*)chunk.data;
      size_t numSamples = chunk.length / 2;
      
      float preGain = 1.0f;  // Âm lượng loa 100%
      outputSmoother.setGain(preGain);
      outputSmoother.processBuffer(audioSamples, numSamples);
      
      // Write to I2S - Không block WebSocket
      size_t written = 0;
      esp_err_t result = i2s_write(I2S_SPEAKER_PORT, chunk.data, chunk.length, &written, pdMS_TO_TICKS(50));  // Timeout 50ms thay vì portMAX_DELAY
      
      if (result == ESP_OK) {
        totalChunksPlayed++;
        // Log mỗi 30 chunks để giảm spam log (tăng từ 20 vì chunk lớn hơn)
        if (totalChunksPlayed % 30 == 0) {
          Serial.printf(">>> Played %d chunks | Queue: %d\n", totalChunksPlayed, queueCount);
        }
      } else {
        Serial.printf("!!! I2S write error: %d\n", result);
      }
      
      // Free memory NGAY LẬP TỨC
      free(chunk.data);
      
      // Update lastPongTime để tránh timeout
      lastPongTime = millis();
    } else {
      // No audio to play, wait a bit
      vTaskDelay(pdMS_TO_TICKS(1));  // Giữ 1ms để phát NHANH
    }
  }
}

String macToUTF8String(const String& mac) {
  String result = mac;
  result.toUpperCase();
  return result;
}

String generateUUIDv4() {
  uint8_t uuid[16];
  for (int i = 0; i < 16; i++) {
    uuid[i] = (uint8_t)esp_random();
  }
  uuid[6] = (uuid[6] & 0x0F) | 0x40;
  uuid[8] = (uuid[8] & 0x3F) | 0x80;

  char uuidStr[37];
  sprintf(uuidStr,
          "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
          uuid[0], uuid[1], uuid[2], uuid[3],
          uuid[4], uuid[5], uuid[6], uuid[7],
          uuid[8], uuid[9],
          uuid[10], uuid[11], uuid[12], uuid[13], uuid[14], uuid[15]);
  return String(uuidStr);
}

float calculateRMS(int16_t* samples, size_t count) {
  long sum = 0;
  for (size_t i = 0; i < count; i++) {
    long val = samples[i];
    sum += val * val;
  }
  return sqrt(sum / (float)count);
}

bool i2sSpeakerInit() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 24000,  // Khớp với server.py - 24kHz
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 4,    // Giảm từ 8 → 4 để reduce latency
    .dma_buf_len = 256,    // Giảm từ 512 → 256 để reduce latency (total buffer = 4×256 = 1KB)
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SPEAKER_BCLK,
    .ws_io_num = I2S_SPEAKER_LRC,
    .data_out_num = I2S_SPEAKER_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  if (i2s_driver_install(I2S_SPEAKER_PORT, &i2s_config, 0, NULL) != ESP_OK) return false;
  if (i2s_set_pin(I2S_SPEAKER_PORT, &pin_config) != ESP_OK) return false;
  
  i2s_set_sample_rates(I2S_SPEAKER_PORT, 24000);
  i2s_zero_dma_buffer(I2S_SPEAKER_PORT);
  return true;
}

bool i2sInit() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = I2S_SAMPLE_RATE,  // 24kHz khớp với server
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 16,    // Tăng DMA buffer
    .dma_buf_len = 512,     // Tăng buffer length
    .use_apll = false
  };

  if (i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL) != ESP_OK) return false;
  if (i2s_set_pin(I2S_PORT, &pin_config) != ESP_OK) return false;
  i2s_zero_dma_buffer(I2S_PORT);
  i2s_start(I2S_PORT);
  return true;
}

// === Enhanced WebSocket Event Handler ===
void webSocketEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.println("✅ WS connected");
      wsConnected = true;
      reconnectAttempts = 0;
      lastPingTime = millis();
      lastPongTime = millis();
      outputSmoother.reset();
      break;

    case WStype_DISCONNECTED:
      Serial.println("❌ WS disconnected");
      wsConnected = false;
      
      // ✅ FIX: KHÔNG clear audio queue - để phát hết audio đã nhận
      // Chỉ set endSignalReceived để task tự dừng khi hết queue
      if (playbackActive || queueCount > 0) {
        Serial.printf("⚠️ WS ngắt nhưng vẫn phát tiếp %d chunks còn lại\n", queueCount);
        endSignalReceived = true;  // Đánh dấu kết thúc để không đợi thêm
        // KHÔNG clear queue và KHÔNG set playbackActive = false
      }
      // clearAudioQueue();  // ❌ BỎ: Không xóa queue để phát hết
      break;

    case WStype_ERROR:
      Serial.println("⚠️ WS Error");
      wsConnected = false;
      break;

    case WStype_PING:
      Serial.println("📡 Received PING from server");
      break;

    case WStype_PONG:
      lastPongTime = millis();
      Serial.printf("📡 Received PONG (RTT: %lums)\n", millis() - lastPingTime);
      break;

    case WStype_TEXT: {
      lastPongTime = millis();
      String message = String((char*)payload);
      
      // Parse JSON để hiển thị đẹp hơn
      if (message.startsWith("{")) {
        DynamicJsonDocument doc(2048);
        DeserializationError error = deserializeJson(doc, message);
        if (!error) {
          String type = doc["type"] | "";
          
          // ✅ XỬ LÝ TRANSCRIPTION (user nói gì)
          if (type == "transcription") {
            String text = doc["message"] | "";
            if (text.length() > 0) {
              Serial.println("\n═══════════════════════════════════");
              Serial.println("👤 BẠN NÓI:");
              Serial.println("   " + text);
              Serial.println("═══════════════════════════════════");
            }
          }
          // ✅ XỬ LÝ CHAT RESPONSE (AI trả lời)
          else if (type == "chat_response") {
            String text = doc["message"] | "";
            if (text.length() > 0) {
              Serial.println("\n🤖 AI TRẢ LỜI:");
              Serial.println("───────────────────────────────────");
              
              // Kiểm tra xem có phải payment response không
              if (text.indexOf("đơn hàng") >= 0 || text.indexOf("Tổng cộng") >= 0 || 
                  text.indexOf("xác nhận") >= 0) {
                Serial.println("💰 THÔNG TIN THANH TOÁN:");
                Serial.println(text);
              } else {
                Serial.println(text);
              }
              Serial.println("───────────────────────────────────\n");
            }
          }
          // ✅ XỬ LÝ PAYMENT INFO CHI TIẾT (nếu server gửi structured data)
          else if (type == "payment_info") {
            Serial.println("\n💳 CHI TIẾT ĐƠN HÀNG:");
            Serial.println("───────────────────────────────────");
            
            if (doc.containsKey("items")) {
              JsonArray items = doc["items"];
              for (JsonObject item : items) {
                String name = item["product_name"] | "";
                int qty = item["quantity"] | 0;
                String unit = item["unit"] | "";
                float price = item["subtotal"] | 0.0;
                
                Serial.printf("   %d %s %s: %.0f₫\n", 
                             qty, unit.c_str(), name.c_str(), price);
              }
            }
            
            if (doc.containsKey("total_amount")) {
              float total = doc["total_amount"] | 0.0;
              Serial.println("───────────────────────────────────");
              Serial.printf("   TỔNG CỘNG: %.0f₫\n", total);
            }
            
            if (doc.containsKey("success")) {
              bool success = doc["success"] | false;
              Serial.println(success ? "   ✅ Thành công" : "   ❌ Thất bại");
            }
            
            Serial.println("═══════════════════════════════════\n");
          }
          // Legacy format support
          else if (type == "TEXT.INPUT.TRANSCRIPT") {
            String data = doc["data"] | "";
            if (data.length() > 0) {
              Serial.println("═══════════════════════════════════");
              Serial.println("  BẠN NÓI: " + data);
              Serial.println("═══════════════════════════════════");
            }
          }
          else if (type == "TEXT.OUTPUT.TRANSCRIPT") {
            String data = doc["data"] | "";
            if (data.length() > 0) {
              Serial.println("═══════════════════════════════════");
              Serial.println("🤖 TRỢ LÝ: " + data);
              Serial.println("═══════════════════════════════════");
            }
          }
          else {
            // Hiển thị raw message cho debug
            Serial.println("📝 Unknown type: " + message);
          }
        } else {
          Serial.println("⚠️ JSON parse error: " + message);
        }
      } else {
        Serial.println("📝 " + message);
      }
      break;
    }

    case WStype_BIN: {
      lastPongTime = millis();
      
      Serial.printf("📦 Binary received: %u bytes\n", length);

      size_t offset = 0;
      if (length < 10) break; 

      // Parse Wire Protocol: macAddress → type → id → audio data
      auto read_u16 = [&](uint8_t* d, size_t& o) {
        uint16_t v = (d[o] << 8) | d[o + 1];  // Big-endian
        o += 2;
        return v;
      };
      auto read_u32 = [&](uint8_t* d, size_t& o) {
        uint32_t v = (d[o] << 24) | (d[o + 1] << 16) | (d[o + 2] << 8) | d[o + 3];  // Big-endian
        o += 4;
        return v;
      };

      // 1. macAddress: 2 bytes length + data
      uint16_t macLen = read_u16(payload, offset);
      String mac((char*)payload + offset, macLen);
      offset += macLen;

      // 2. type: 2 bytes length + data
      uint16_t typeLen = read_u16(payload, offset);
      String msgType((char*)payload + offset, typeLen);
      offset += typeLen;

      // 3. id: 2 bytes length + data
      uint16_t uuidLen = read_u16(payload, offset);
      String uuid((char*)payload + offset, uuidLen);
      offset += uuidLen;

      // 4. audio data: 4 bytes length + data
      uint32_t audioLen = read_u32(payload, offset);
      uint8_t* audioData = payload + offset;
      offset += audioLen;

      Serial.printf("🔊 Type: %s | UUID: %s | AudioLen: %lu\n",
                    msgType.c_str(), uuid.c_str(), audioLen);

      if (msgType == "START") {
        // Server bắt đầu gửi audio response
        if (!playbackActive) {
          playbackActive = true;
          playbackStartTime = millis();
          endSignalReceived = false;
          Serial.println("═══════════════════════════════════");
          Serial.println(">>> BAT DAU PHAT AUDIO <<<");
          Serial.println("═══════════════════════════════════");
        }
      }
      else if (msgType == "PROCESSING" && audioLen > 0) {
        // Nhận audio chunks từ server
        lastPongTime = millis();
        
        if (!playbackActive) {
          playbackActive = true;
          playbackStartTime = millis();
          Serial.println("═══════════════════════════════════");
          Serial.println(">>> BAT DAU PHAT AUDIO <<<");
          Serial.println("═══════════════════════════════════");
        }
        
        // Thêm vào queue thay vì play trực tiếp - KHÔNG BLOCK WebSocket!
        bool queued = enqueueAudio(audioData, audioLen);
        
        if (!queued) {
          static int dropCount = 0;
          dropCount++;
          if (dropCount % 10 == 0) {
            Serial.printf("!!! Dropped %d chunks total\n", dropCount);
          }
        }
      }
      else if (msgType == "END") {
        // Server kết thúc gửi audio
        Serial.println("═══════════════════════════════════");
        Serial.println(">>> END SIGNAL RECEIVED <<<");
        Serial.println("═══════════════════════════════════");
        endSignalReceived = true;
        // KHÔNG chờ trong event handler - sẽ xử lý trong loop()
      }
      
      break;  
    } 

    default:
      break;
  }
}

// === WiFi Connection với Power Management ===
bool connectWiFi() {
  WiFi.mode(WIFI_STA);
  
  // Tắt WiFi power save để giữ kết nối ổn định
  esp_wifi_set_ps(WIFI_PS_NONE);
  
  // Tăng TX power cho tín hiệu mạnh hơn
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
  
  WiFi.begin(ssid, password);
  Serial.print("🔌 WiFi connecting");
  
  for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; i++) {
    Serial.print(".");
    delay(1000);
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    deviceMacAddress = macToUTF8String(WiFi.macAddress());
    Serial.println("\n✅ WiFi connected");
    Serial.println("MAC: " + deviceMacAddress);
    Serial.println("IP: " + WiFi.localIP().toString());
    Serial.printf("RSSI: %d dBm\n", WiFi.RSSI());
    return true;
  }
  
  Serial.println("\n❌ WiFi failed");
  return false;
}

// === WebSocket với Enhanced Stability ===
void initWebSocket() {
  webSocket.begin(ws_host, ws_port, ws_path);
  webSocket.onEvent(webSocketEvent);
  
  // Tăng thời gian reconnect để tránh spam server
  webSocket.setReconnectInterval(5000);
  
  // Tắt heartbeat tự động, dùng manual ping
  webSocket.disableHeartbeat();
  
  Serial.printf("🔌 Connecting to %s:%d%s\n", ws_host, ws_port, ws_path);
}

// === Manual Ping/Pong Monitoring ===
void checkWebSocketHealth() {
  if (!wsConnected) return;
  
  // KHÔNG làm gì khi đang recording hoặc playback - tránh làm gián đoạn
  if (recordingActive || playbackActive) {
    return;
  }
  
  unsigned long now = millis();
  
  // Chỉ gửi ping khi KHÔNG đang phát audio
  if (now - lastPingTime > PING_INTERVAL) {
    Serial.println("📡 Sending manual PING");
    webSocket.sendPing();
    lastPingTime = now;
  }
  
  // Kiểm tra timeout - CHỈ KHI idle hoàn toàn (KHÔNG đang phát audio)
  if (!playbackActive && queueCount == 0 && now - lastPongTime > PONG_TIMEOUT) {
    Serial.println("⚠️ WebSocket timeout (idle) - forcing reconnect");
    wsConnected = false;
    webSocket.disconnect();
    delay(1000);
    initWebSocket();
  }
  else if (playbackActive || queueCount > 0) {
    // Khi đang phát audio, update lastPongTime để tránh timeout
    lastPongTime = now;
  }
}

// === Smart Reconnect với Exponential Backoff ===
void handleReconnect() {
  if (wsConnected) {
    waitingForAudioStartTime = 0;  // Reset timer khi connected
    return;
  }
  
  unsigned long now = millis();
  
  // ✅ FIX: Nếu đang phát audio, KHÔNG reconnect để tránh gián đoạn
  if (playbackActive || queueCount > 0) {
    Serial.printf("⏳ Đang phát audio (%d chunks) - Delay reconnect\n", queueCount);
    waitingForAudioStartTime = 0;
    lastReconnectAttempt = now;  // Reset cooldown
    return;  // Chờ phát xong audio
  }
  
  waitingForAudioStartTime = 0;  // Reset timer
  
  // Chỉ thử reconnect sau cooldown period
  if (now - lastReconnectAttempt < RECONNECT_COOLDOWN) return;
  
  lastReconnectAttempt = now;
  reconnectAttempts++;
  
  Serial.printf("🔄 Reconnect attempt %d/%d\n", reconnectAttempts, MAX_RECONNECT_ATTEMPTS);
  
  // Kiểm tra WiFi trước
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ WiFi disconnected, reconnecting...");
    WiFi.disconnect();
    delay(100);
    connectWiFi();
  }
  
  // Thử reconnect WebSocket
  initWebSocket();
  
  // Nếu quá nhiều lần thất bại, restart ESP32
  if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    Serial.println("❌ Max reconnect attempts reached, restarting...");
    delay(1000);
    ESP.restart();
  }
}

void sendBinaryPacket(
    const String& macStr,
    const String& typeStr,
    const String& uuidStr,
    const uint8_t* audioData,
    uint32_t audioLen
) {
  if (!wsConnected) {
    // Không spam log nữa, chỉ return
    return;
  }

  uint16_t macLen = macStr.length();
  uint16_t typeLen = typeStr.length();
  uint16_t uuidLen = uuidStr.length();

  // Wire Protocol: macAddress (2B len + data) → type (2B len + data) → id (2B len + data) → audio (4B len + data)
  size_t totalSize = 2 + macLen + 2 + typeLen + 2 + uuidLen + 4 + audioLen;

  if (totalSize > 65535) {
    Serial.println("❌ Gói tin quá lớn: " + String(totalSize));
    return;
  }

  uint8_t* buffer = (uint8_t*)malloc(totalSize);
  if (!buffer) {
    Serial.println("❌ Không đủ RAM");
    return;
  }

  size_t offset = 0;

  // macAddress: 2 bytes length (big-endian) + data
  buffer[offset++] = (macLen >> 8) & 0xFF;
  buffer[offset++] = macLen & 0xFF;
  memcpy(buffer + offset, macStr.c_str(), macLen);
  offset += macLen;

  // type: 2 bytes length (big-endian) + data
  buffer[offset++] = (typeLen >> 8) & 0xFF;
  buffer[offset++] = typeLen & 0xFF;
  memcpy(buffer + offset, typeStr.c_str(), typeLen);
  offset += typeLen;

  // id: 2 bytes length (big-endian) + data
  buffer[offset++] = (uuidLen >> 8) & 0xFF;
  buffer[offset++] = uuidLen & 0xFF;
  memcpy(buffer + offset, uuidStr.c_str(), uuidLen);
  offset += uuidLen;

  // audio data: 4 bytes length (big-endian) + data
  buffer[offset++] = (audioLen >> 24) & 0xFF;
  buffer[offset++] = (audioLen >> 16) & 0xFF;
  buffer[offset++] = (audioLen >> 8) & 0xFF;
  buffer[offset++] = audioLen & 0xFF;

  if (audioData && audioLen > 0) {
    memcpy(buffer + offset, audioData, audioLen);
  }

  bool sent = webSocket.sendBIN(buffer, totalSize);
  free(buffer);
  
  if (!sent) {
    Serial.println("⚠️ Failed to send packet");
    wsConnected = false;
  }
}

void recordAndStream() {
  if (!wsConnected) {
    Serial.println("❌ WebSocket chưa sẵn sàng");
    return;
  }

  // ✅ CRITICAL: Kiểm tra buffers đã được allocate chưa
  if (!i2sBuffer || !pcmBuffer) {
    Serial.println("❌ Audio buffers chưa được khởi tạo!");
    return;
  }

  // Đợi audio phát xong trước khi ghi mới - TỐI ƯU: giảm delay
  if (playbackActive || queueCount > 0) {
    Serial.println("⏳ Đợi phát xong audio trước...");
    unsigned long waitStart = millis();
    while ((playbackActive || queueCount > 0) && millis() - waitStart < 30000) {
      delay(10);  // Giảm từ 100ms → 10ms để phản hồi nhanh hơn
      webSocket.loop();
    }
    delay(100); // Giảm từ 500ms → 100ms
  }

  // Clear audio queue trước khi bắt đầu
  clearAudioQueue();
  outputSmoother.reset();
  playbackActive = false;
  endSignalReceived = false;
  
  sessionId = generateUUIDv4();
  Serial.println("\n═══════════════════════════════════");
  Serial.println("🎙️ BẮT ĐẦU GHI ÂM - Tiếng Việt");
  Serial.println("Session ID: " + sessionId);
  Serial.println("Sample Rate: 24kHz (Khớp với OpenAI TTS)");
  Serial.println("═══════════════════════════════════");

  sendBinaryPacket(deviceMacAddress, "START", sessionId, NULL, 0);
  delay(50);  // Giảm từ 300ms → 50ms để bắt đầu nhanh hơn

  audioFilter.reset();
  recordingActive = true;

  unsigned long startTime = millis();
  unsigned long lastSoundTime = millis();
  unsigned long lastPrintTime = millis();
  unsigned long lastHealthCheck = millis();
  int chunkCount = 0;
  bool hadSound = false;

  while (true) {
    // Kiểm tra WebSocket health trong khi recording
    if (millis() - lastHealthCheck > 2000) {
      if (!wsConnected) {
        Serial.println("❌ Mất kết nối, dừng ghi âm");
        break;
      }
      webSocket.loop(); // Đảm bảo WebSocket vẫn hoạt động
      lastHealthCheck = millis();
    }

    size_t bytesRead = 0;
    i2s_read(I2S_PORT, i2sBuffer, I2S_READ_LEN, &bytesRead, portMAX_DELAY);
    if (bytesRead == 0) continue;

    size_t pcmSamples = bytesRead / 2;
    size_t pcmBytes = 0;
    
    // ✅ Allocate samples array động thay vì trên stack (tránh overflow)
    int16_t* samples = (int16_t*)malloc(pcmSamples * sizeof(int16_t));
    if (!samples) {
      Serial.println("❌ Out of memory for samples array");
      continue;
    }

    for (size_t i = 0; i < pcmSamples && pcmBytes < CHUNK_SIZE - 2; i++) {
      int16_t sample = (int16_t)((i2sBuffer[i*2+1] << 8) | i2sBuffer[i*2]);
      sample = audioFilter.processSample(sample);
      samples[i] = sample;
      
      pcmBuffer[pcmBytes++] = sample & 0xFF;
      pcmBuffer[pcmBytes++] = (sample >> 8) & 0xFF;
    }

    float rms = calculateRMS(samples, pcmSamples);
    
    // ✅ Free samples array ngay sau khi dùng xong
    free(samples);
    
    if (rms > SILENCE_THRESHOLD) {
      lastSoundTime = millis();
      hadSound = true;
    }

    if (millis() - lastPrintTime > 500) {
      unsigned long silenceDuration = millis() - lastSoundTime;
      if (rms > SILENCE_THRESHOLD) {
        Serial.printf("🎤 RMS: %.1f ✅ (Đang nói)\n", rms);
      } else {
        Serial.printf("🔇 RMS: %.1f (Im lặng: %.1fs)\n", rms, silenceDuration/1000.0);
      }
      lastPrintTime = millis();
    }

    unsigned long silenceDuration = millis() - lastSoundTime;
    if (hadSound && silenceDuration > SILENCE_DURATION) {
      Serial.printf("\n⏹️ Im lặng %.1fs - Dừng ghi âm\n", silenceDuration/1000.0);
      break;
    }

    if (pcmBytes > 0) {
      bool disconnectedDuringSend = false;
      for (size_t offset = 0; offset < pcmBytes; offset += CHUNK_SIZE) {
        size_t chunkLen = min((size_t)CHUNK_SIZE, pcmBytes - offset);
        
        // Kiểm tra kết nối trước khi gửi
        if (!wsConnected) {
          Serial.println("⚠️ Mất kết nối trong khi gửi chunk");
          disconnectedDuringSend = true;
          break;
        }
        
        sendBinaryPacket(deviceMacAddress, "PROCESSING", sessionId, pcmBuffer + offset, chunkLen);
        chunkCount++;
        
        // Cho WebSocket thời gian xử lý giữa các chunk - TỐI ƯU: giảm delay
        webSocket.loop();
        // delay(2); // ❌ BỎ: Throttle không cần thiết - server đã tối ưu nhận
        yield();
      }
      
      // Nếu mất kết nối khi gửi, thoát luôn khỏi vòng lặp chính
      if (disconnectedDuringSend) {
        break;
      }
    }
  }

  Serial.println("═══════════════════════════════════");
  Serial.println("📤 Gửi END packet...");
  sendBinaryPacket(deviceMacAddress, "END", sessionId, NULL, 0);
  
  Serial.printf("✅ Đã gửi %d chunks trong %.1fs\n", 
                chunkCount, (millis() - startTime) / 1000.0);
  Serial.println("🔊 Đang chờ server xử lý và phát lại...");
  Serial.println("═══════════════════════════════════\n");
  
  recordingActive = false;
}

void setup() {
  Serial.begin(115200);
  esp_bt_controller_disable();

  pinMode(BUTTON_PIN, INPUT_PULLUP); 

  if (!SPIFFS.begin(true)) {
    Serial.println("❌ SPIFFS failed");
    return;
  }
  
  // Kiểm tra PSRAM
  if (psramFound()) {
    Serial.println("✅ PSRAM detected!");
    Serial.printf("   Total PSRAM: %d bytes (%.2f MB)\n", ESP.getPsramSize(), ESP.getPsramSize() / 1024.0 / 1024.0);
    Serial.printf("   Free PSRAM: %d bytes (%.2f MB)\n", ESP.getFreePsram(), ESP.getFreePsram() / 1024.0 / 1024.0);
    
    // Allocate buffers trong PSRAM
    i2sBuffer = (uint8_t*)heap_caps_malloc(I2S_READ_LEN, MALLOC_CAP_SPIRAM);
    pcmBuffer = (uint8_t*)heap_caps_malloc(CHUNK_SIZE, MALLOC_CAP_SPIRAM);
    
    if (!i2sBuffer || !pcmBuffer) {
      Serial.println("❌ Failed to allocate buffers in PSRAM!");
      return;
    }
    Serial.println("✅ Audio buffers (8KB×2=16KB) allocated in PSRAM");
  } else {
    Serial.println("⚠️ PSRAM NOT found - using internal RAM!");
    
    // Fallback: allocate trong internal RAM
    i2sBuffer = (uint8_t*)malloc(I2S_READ_LEN);
    pcmBuffer = (uint8_t*)malloc(CHUNK_SIZE);
    
    if (!i2sBuffer || !pcmBuffer) {
      Serial.println("❌ Failed to allocate buffers in RAM!");
      return;
    }
    Serial.println("✅ Audio buffers (8KB×2=16KB) allocated in internal RAM");
  }

  if (!connectWiFi()) {
    Serial.println("❌ WiFi failed, restarting...");
    ESP.restart();
  }
  
  if (!i2sInit()) {
    Serial.println("❌ I2S mic init failed");
    return;
  }

  if (!i2sSpeakerInit()) {
    Serial.println("❌ I2S speaker init failed");
    return;
  }

  // Initialize audio queue
  queueMutex = xSemaphoreCreateMutex();
  if (queueMutex == NULL) {
    Serial.println("❌ Failed to create queue mutex");
    return;
  }
  
  // Initialize audio queue
  for (int i = 0; i < MAX_AUDIO_QUEUE; i++) {
    audioQueue[i].data = NULL;
    audioQueue[i].length = 0;
    audioQueue[i].valid = false;
  }
  
  // Create audio playback task on Core 0
  xTaskCreatePinnedToCore(
    audioPlaybackTaskFunction,
    "AudioPlayback",
    8192,        // Stack size
    NULL,
    4,           // Priority (tăng từ 3 → 4 để ưu tiên CAO NHẤT cho audio)
    &audioPlaybackTask,
    0            // Core 0
  );
  
  if (audioPlaybackTask == NULL) {
    Serial.println("❌ Failed to create audio playback task");
    return;
  }

  initWebSocket();

  Serial.println("═══════════════════════════════════");
  Serial.println("✅ ESP32 SẴN SÀNG!");
  Serial.println("═══════════════════════════════════");
  Serial.println("📱 CHẾ ĐỘ TỰ ĐỘNG:");
  Serial.println("   🔘 Nhấn nút PIN 9 1 lần → Bật chế độ tự động");
  Serial.println("   ⏺️  Tự động thu âm khi im lặng 3 giây");
  Serial.println("   🔄 Sau khi AI trả lời xong → Đợi 3s → Tự động bật lại mic");
  Serial.println("   ⏹️  Nhấn nút lần nữa → Tắt chế độ tự động");
  Serial.println("🎵 Audio Playback: Non-blocking Queue System");
  Serial.println("  Queue Size: 200 slots (dùng PSRAM 16MB)");
  Serial.println("  Chunk Size: 8KB (khớp với server.py)");
  Serial.println("  Max Audio: ~1.6MB buffered (200×8KB)");
  Serial.println("  Sample Rate: 24kHz (Khớp với OpenAI TTS)");
  Serial.println("🇻🇳 Tối ưu cho Tiếng Việt");
  Serial.println("🔊 Audio DSP: Pre-emphasis + AGC + Noise Gate");
  Serial.println("🔒 WebSocket: Auto Reconnect + Stability Enhanced");
  Serial.println("⏱️  Auto Stop: Im lặng 3 giây");
  Serial.println("⚡ Server tối ưu: chunk 8KB + delay 5ms");
  Serial.println("═══════════════════════════════════\n");
}

void loop() {
  // 1. WebSocket loop (ưu tiên cao nhất)
  webSocket.loop();
  
  // 2. Xử lý END signal - đợi audio phát hết
  if (endSignalReceived && playbackActive) {
    if (queueCount == 0) {
      // Queue đã empty, audio đã phát xong
      delay(50); // Giảm từ 200ms → 50ms để nhanh hơn
      outputSmoother.reset();
      playbackActive = false;
      endSignalReceived = false;
      Serial.println("═══════════════════════════════════");
      Serial.println(">>> DA PHAT XONG TOAN BO AUDIO <<<");
      Serial.println("═══════════════════════════════════");
      
      // Nếu đang ở chế độ tự động, bắt đầu đếm 3 giây
      if (autoRecordingMode) {
        audioFinishedTime = millis();
        waitingToRestart = true;
        Serial.println("⏳ Đợi 3 giây trước khi tự động bật lại mic...");
      }
    }
  }
  
  // 2.5. Timeout nếu đang phát audio quá lâu (120s) mà không có END signal
  if (playbackActive && !endSignalReceived) {
    if (millis() - playbackStartTime > 120000) {
      Serial.println("⚠️ Playback timeout 120s - forcing stop");
      clearAudioQueue();
      outputSmoother.reset();
      playbackActive = false;
      endSignalReceived = false;
    }
  }
  
  // 2.6. Timeout khi đợi audio quá lâu - có thể server đã ngắt hoặc WS disconnect
  static unsigned long lastQueueEmptyTime = 0;
  if (playbackActive && queueCount == 0 && !endSignalReceived) {
    if (lastQueueEmptyTime == 0) {
      lastQueueEmptyTime = millis();
    }
    
    unsigned long waitTime = millis() - lastQueueEmptyTime;
    
    // ✅ Nếu WS đã disconnect, timeout ngay lập tức
    if (!wsConnected) {
      Serial.println("⚠️ WS đã ngắt kết nối - dừng playback");
      playbackActive = false;
      endSignalReceived = false;
      clearAudioQueue();
      lastQueueEmptyTime = 0;
      return; // Thoát luôn để reconnect
    }
    
    // Log mỗi 2 giây (chỉ khi WS còn kết nối)
    if (waitTime > 2000 && waitTime % 2000 < 100) {
      Serial.printf("⏳ Đang đợi audio từ server... (%.1fs)\n", waitTime / 1000.0);
    }
    
    // Timeout sau 10 giây - server có thể đã xong hoặc bị lỗi
    if (waitTime > 10000) {
      Serial.println("⚠️ Timeout đợi audio 10s - dừng playback");
      playbackActive = false;
      endSignalReceived = false;
      clearAudioQueue();
      lastQueueEmptyTime = 0;
    }
  } else if (queueCount > 0) {
    lastQueueEmptyTime = 0;
  }
  
  // 3. Kiểm tra WiFi health
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ WiFi disconnected!");
    connectWiFi();
  }
  
  // 4. Kiểm tra WebSocket health
  checkWebSocketHealth();
  
  // 5. Handle reconnect nếu cần
  handleReconnect();
  
  // 6. Xử lý chế độ tự động bật lại mic sau 3 giây
  if (waitingToRestart && autoRecordingMode && wsConnected) {
    if (millis() - audioFinishedTime >= 3000) {
      waitingToRestart = false;
      Serial.println("═══════════════════════════════════");
      Serial.println("🔄 TỰ ĐỘNG BẬT LẠI MIC SAU 3 GIÂY");
      Serial.println("═══════════════════════════════════");
      
      // Tự động bắt đầu ghi âm lại
      if (!isRecording && !playbackActive && queueCount == 0 && !endSignalReceived) {
        isRecording = true;
        recordAndStream();
        isRecording = false;
      }
    }
  }
  
  // 7. Button handler - Bật/tắt chế độ tự động
  static bool lastButtonState = HIGH;
  bool currentButtonState = digitalRead(BUTTON_PIN);
  
  if (lastButtonState == HIGH && currentButtonState == LOW) {
    delay(50); // Debounce
    if (digitalRead(BUTTON_PIN) == LOW) {
      if (!autoRecordingMode) {
        // Bật chế độ tự động và bắt đầu ghi âm
        autoRecordingMode = true;
        Serial.println("═══════════════════════════════════");
        Serial.println("✅ BẬT CHẾ ĐỘ TỰ ĐỘNG - Nhấn lại để tắt");
        Serial.println("═══════════════════════════════════");
        
        if (wsConnected && !isRecording && !playbackActive) {
          isRecording = true;
          recordAndStream();
          isRecording = false;
        }
      } else {
        // Tắt chế độ tự động
        autoRecordingMode = false;
        waitingToRestart = false;
        Serial.println("═══════════════════════════════════");
        Serial.println("⏹️ TẮT CHẾ ĐỘ TỰ ĐỘNG");
        Serial.println("═══════════════════════════════════");
      }
      
      // Đợi nhả nút
      while (digitalRead(BUTTON_PIN) == LOW) {
        delay(10);
      }
    }
  }
  lastButtonState = currentButtonState;
  
  // 8. Yield để không block watchdog
  delay(5);
}

#pragma GCC diagnostic pop
