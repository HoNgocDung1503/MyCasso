// ============================================================
// ESP32-S3N16R8: Voice Assistant + QR + Emoji + Servo Direction
// Hardware: INMP441 + MAX98357A + ST7789 + 2x MAX9814 + Servo MG90S
// Communication: WebSocket (Voice) + MQTT (QR Display)
// Features: Animated Emoji + Auto Servo Direction Tracking
// Version: 3.0 INTEGRATED
// ============================================================

#include <Arduino.h>
#include "SPIFFS.h"
#include <driver/i2s.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <PubSubClient.h>
#include <esp_bt.h>
#include <ArduinoJson.h>
#include <base64.h>
#include <esp_wifi.h>
#include <esp_heap_caps.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>
#include <ESP32Servo.h>

// ============================================================
// EMOJI HEADER FILES
// ============================================================
#include "emoji_hon_frames.h"
#include "emoji_batngo_frames.h"
#include "emoji_buonngu_frames.h"
#include "emoji_boiroi_frames.h"
#include "emoji_haihuoc_frames.h"
#include "emoji_thoaimai4_frames.h"
#include "emoji_thoaimai_frames.h"
#include "emoji_ngongan_frames.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"

// ============================================================
// WIFI & SERVER CONFIG
// ============================================================
const char* ssid = "dev";
const char* password = "123456789";
// const char* ws_host = "192.168.80.185";
const char* ws_host = "10.198.143.72";
// const char* ws_host = "192.168.1.185";
const uint16_t ws_port = 8765; 
const char* ws_path = "/";

// ============================================================
// MQTT CONFIG
// ============================================================
const char* mqtt_server = "mqtt.loathanhtoan.com";
const int mqtt_port = 1883;
const char* mqtt_password = "GC0pCmTP2gLCiocpXyjXlVJPVkRLQuyK";
String mqtt_username;
String topic_qr;

// ============================================================
// TFT DISPLAY CONFIG (ST7789 - 240×320)
// ============================================================
#define TFT_CS 10
#define TFT_DC 21
#define TFT_RST 47
#define TFT_SDA 13  // MOSI
#define TFT_SCK 12  // SCK
#define SCREEN_WIDTH 320   // Landscape mode
#define SCREEN_HEIGHT 240  // Landscape mode

Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);

// QR Matrix storage
bool qrMatrix[200][200];
int qrMatrixSize = 0;
bool qrDisplayed = false;
unsigned long qrDisplayStartTime = 0;
const unsigned long QR_DISPLAY_DURATION = 30000;
unsigned long qrLockUntil = 0;

// ============================================================
// SERVO DIRECTION TRACKING CONFIG
// ============================================================
#define LEFT_MIC 1        // MAX9814 trái (ADC1_CH7)
#define RIGHT_MIC 2       // MAX9814 phải (ADC1_CH0)
#define SERVO_PIN 8        // Servo MG90S

// Servo parameters
const int SERVO_MIN_US = 500;
const int SERVO_MAX_US = 2500;
const int SERVO_FREQ = 50;

// Servo angles
const int ANGLE_CENTER = 0;
const int ANGLE_LEFT = -90;
const int ANGLE_RIGHT = 90;

// Direction detection parameters
const int BASELINE_MIN = 1000;
const int BASELINE_MAX = 1700;
const int THRESHOLD = 50;
const int NOISE_TOLERANCE = 5;
const int SAMPLE_WINDOW = 50;
const int SAMPLE_DELAY = 1;

// Direction state
enum ServoDirection {
  SERVO_CENTER,
  SERVO_LEFT,
  SERVO_RIGHT
};

Servo myServo;
volatile ServoDirection currentServoDirection = SERVO_CENTER;
unsigned long lastServoSoundTime = 0;
const unsigned long SERVO_TIMEOUT = 10000;  // 10 seconds
bool servoAtCenter = true;
SemaphoreHandle_t servoMutex = NULL;
TaskHandle_t directionTask = NULL;

// ============================================================
// EMOJI STATE MANAGEMENT
// ============================================================
enum EmojiState {
  EMOJI_IDLE,
  EMOJI_CONFUSED,
  EMOJI_SURPRISED,
  EMOJI_WAITING,
  EMOJI_QR
};

volatile EmojiState currentEmojiState = EMOJI_IDLE;
volatile EmojiState previousEmojiState = EMOJI_IDLE;
volatile bool emojiStateChanged = false;
SemaphoreHandle_t emojiStateMutex = NULL;
TaskHandle_t emojiTask = NULL;
volatile bool stopCurrentEmoji = false;

// Emoji animation config
const int ANIMATION_SPEED = 2;
const uint16_t WHITE_THRESHOLD = 0xF7DE;
const uint16_t BLACK_THRESHOLD = 0x2000;
const uint16_t EYE_COLOR = 0xF800;

// ============================================================
// WEBSOCKET & MQTT CLIENTS
// ============================================================
WebSocketsClient webSocket;
WiFiClient espClient;
PubSubClient mqtt(espClient);

// ============================================================
// BUTTON & CONTROL
// ============================================================
const int BUTTON_PIN = 11;
bool isRecording = false;
bool autoRecordingMode = false;
unsigned long audioFinishedTime = 0;
bool waitingToRestart = false;

// ============================================================
// AUDIO CONFIGS
// ============================================================
#define I2S_SAMPLE_RATE 24000
#define I2S_READ_LEN 8192
#define CHUNK_SIZE 8192
#define SILENCE_THRESHOLD 150.0f
#define SILENCE_DURATION 3000

// I2S Mic Config (INMP441)
const i2s_port_t I2S_PORT = I2S_NUM_0;
i2s_pin_config_t pin_config = {
  .bck_io_num = 5,
  .ws_io_num = 4,
  .data_out_num = I2S_PIN_NO_CHANGE,
  .data_in_num = 6
};

// I2S Speaker Config (MAX98357A)
#define I2S_SPEAKER_PORT I2S_NUM_1
#define I2S_SPEAKER_BCLK 15
#define I2S_SPEAKER_LRC 16
#define I2S_SPEAKER_DIN 7

// Audio buffers
uint8_t* i2sBuffer = nullptr;
uint8_t* pcmBuffer = nullptr;

// ============================================================
// AUDIO PLAYBACK QUEUE
// ============================================================
#define MAX_AUDIO_QUEUE 1000
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

bool recordingActive = false;
bool playbackActive = false;
bool endSignalReceived = false;
unsigned long playbackStartTime = 0;

// ============================================================
// WEBSOCKET HEALTH MONITORING
// ============================================================
#define PING_INTERVAL 30000
#define PONG_TIMEOUT 60000
#define RECONNECT_COOLDOWN 5000
#define MAX_RECONNECT_ATTEMPTS 5

unsigned long lastPingTime = 0;
unsigned long lastPongTime = 0;
unsigned long lastReconnectAttempt = 0;
int reconnectAttempts = 0;
bool wsConnected = false;

String deviceMacAddress = "";  
String sessionId = "";

// ============================================================
// SERVO DIRECTION DETECTION FUNCTIONS
// ============================================================

int countOutOfRange(int values[], int size) {
  int count = 0;
  for (int i = 0; i < size; i++) {
    if (values[i] < BASELINE_MIN || values[i] > BASELINE_MAX) {
      count++;
    }
  }
  return count;
}

float calculateVariance(int values[], int size) {
  float mean = 0;
  for (int i = 0; i < size; i++) {
    mean += values[i];
  }
  mean /= size;
  
  float sumSquaredDiff = 0;
  for (int i = 0; i < size; i++) {
    float diff = values[i] - mean;
    sumSquaredDiff += diff * diff;
  }
  
  return sumSquaredDiff / size;
}

int calculateAverage(int values[], int size) {
  long sum = 0;
  for (int i = 0; i < size; i++) {
    sum += values[i];
  }
  return sum / size;
}

int getMin(int values[], int size) {
  int minVal = values[0];
  for (int i = 1; i < size; i++) {
    if (values[i] < minVal) minVal = values[i];
  }
  return minVal;
}

int getMax(int values[], int size) {
  int maxVal = values[0];
  for (int i = 1; i < size; i++) {
    if (values[i] > maxVal) maxVal = values[i];
  }
  return maxVal;
}

void moveServoToAngle(int angle) {
  angle = constrain(angle, -90, 90);
  int writeValue = angle + 90;  // Convert -90~90 to 0~180
  myServo.write(writeValue);
  delay(300);  // Wait for servo to move
}

// ============================================================
// DIRECTION DETECTION TASK
// ============================================================

void directionDetectionTaskFunction(void* parameter) {
  Serial.println("🎯 Direction detection task started");
  
  // Initialize servo
  ESP32PWM::allocateTimer(0);
  myServo.setPeriodHertz(SERVO_FREQ);
  myServo.attach(SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  moveServoToAngle(ANGLE_CENTER);
  
  Serial.println("✓ Servo ready at 0°");
  
  lastServoSoundTime = millis();
  
  while (true) {
    // Collect samples from both mics
    int leftValues[SAMPLE_WINDOW];
    int rightValues[SAMPLE_WINDOW];
    
    for (int i = 0; i < SAMPLE_WINDOW; i++) {
      leftValues[i] = analogRead(LEFT_MIC);
      rightValues[i] = analogRead(RIGHT_MIC);
      vTaskDelay(pdMS_TO_TICKS(SAMPLE_DELAY));
    }
    
    // Calculate statistics
    float leftVariance = calculateVariance(leftValues, SAMPLE_WINDOW);
    float rightVariance = calculateVariance(rightValues, SAMPLE_WINDOW);
    int leftAvg = calculateAverage(leftValues, SAMPLE_WINDOW);
    int rightAvg = calculateAverage(rightValues, SAMPLE_WINDOW);
    int leftOutOfRange = countOutOfRange(leftValues, SAMPLE_WINDOW);
    int rightOutOfRange = countOutOfRange(rightValues, SAMPLE_WINDOW);
    
    // Check for sound
    bool leftHasSound = (leftOutOfRange > NOISE_TOLERANCE);
    bool rightHasSound = (rightOutOfRange > NOISE_TOLERANCE);
    
    // Debug output (every 1 second)
    static unsigned long lastDebug = 0;
    if (millis() - lastDebug > 1000) {
      Serial.printf("🎧 L:%d[Var:%.0f Out:%d] R:%d[Var:%.0f Out:%d]",
                    leftAvg, leftVariance, leftOutOfRange,
                    rightAvg, rightVariance, rightOutOfRange);
      
      if (!leftHasSound && !rightHasSound) {
        Serial.print(" [Quiet]");
      }
      Serial.println();
      lastDebug = millis();
    }
    
    if (!leftHasSound && !rightHasSound) {
      // No sound detected - check timeout
      if (!servoAtCenter && (millis() - lastServoSoundTime >= SERVO_TIMEOUT)) {
        Serial.println("🔄 SERVO TIMEOUT: Returning to center (0°)");
        
        if (xSemaphoreTake(servoMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
          moveServoToAngle(ANGLE_CENTER);
          currentServoDirection = SERVO_CENTER;
          servoAtCenter = true;
          xSemaphoreGive(servoMutex);
        }
      }
    } else {
      // Sound detected
      lastServoSoundTime = millis();
      servoAtCenter = false;
      
      // Analyze direction
      float varianceDiff = abs(leftVariance - rightVariance);
      ServoDirection detectedDirection = SERVO_CENTER;
      
      if (varianceDiff > THRESHOLD) {
        if (leftVariance > rightVariance) {
          detectedDirection = SERVO_LEFT;
        } else {
          detectedDirection = SERVO_RIGHT;
        }
      } else {
        detectedDirection = SERVO_CENTER;
      }
      
      // Move servo if direction changed
      if (xSemaphoreTake(servoMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        if (detectedDirection != currentServoDirection) {
          switch(detectedDirection) {
            case SERVO_LEFT:
              Serial.println("🎯 Servo → LEFT (-90°)");
              moveServoToAngle(ANGLE_LEFT);
              break;
              
            case SERVO_RIGHT:
              Serial.println("🎯 Servo → RIGHT (+90°)");
              moveServoToAngle(ANGLE_RIGHT);
              break;
              
            case SERVO_CENTER:
              Serial.println("🎯 Servo → CENTER (0°)");
              moveServoToAngle(ANGLE_CENTER);
              break;
          }
          
          currentServoDirection = detectedDirection;
        }
        xSemaphoreGive(servoMutex);
      }
    }
    
    vTaskDelay(pdMS_TO_TICKS(200));
  }
}

// ============================================================
// EMOJI FUNCTIONS
// ============================================================

struct EmojiInfo {
  const uint16_t* frames;
  int width;
  int height;
  int frameCount;
  const int* durations;
};

void drawEmojiFrameScaled(const uint16_t* frameData, int width, int height, 
                          int x, int y, int scale) {
  static int debugFrameCount = 0;
  
  if (debugFrameCount < 3) {
    Serial.printf("🎨 Drawing emoji frame: %dx%d at (%d,%d) scale=%d\n", 
                  width, height, x, y, scale);
    debugFrameCount++;
  }
  
  tft.startWrite();
  
  int pixelsDrawn = 0;
  
  for (int py = 0; py < height; py++) {
    if (py % 5 == 0 && stopCurrentEmoji) {
      tft.endWrite();
      Serial.println("   ⏹️  Emoji drawing interrupted by stop flag");
      return;
    }
    
    for (int px = 0; px < width; px++) {
      uint16_t color = pgm_read_word(&frameData[py * width + px]);
      
      if (color <= WHITE_THRESHOLD) {
        if (color < BLACK_THRESHOLD) {
          color = EYE_COLOR;
        }
        
        if (scale == 1) {
          tft.writePixel(x + px, y + py, color);
        } else {
          tft.writeFillRect(x + px * scale, y + py * scale, scale, scale, color);
        }
        pixelsDrawn++;
      }
    }
  }
  
  tft.endWrite();
  
  if (debugFrameCount <= 3) {
    Serial.printf("   ✅ Drew %d pixels\n", pixelsDrawn);
  }
}

void playEmojiAnimation(const uint16_t* frames, int width, int height,
                        int frameCount, const int* durations, int loops) {
  int frameSize = width * height;
  int scale = 5;
  
  int x = (SCREEN_WIDTH - width * scale) / 2;
  int y = (SCREEN_HEIGHT - height * scale) / 2;
  
  int loopCount = 0;
  
  while ((loops == -1 || loopCount < loops) && !stopCurrentEmoji) {
    for (int i = 0; i < frameCount && !stopCurrentEmoji; i++) {
      drawEmojiFrameScaled(&frames[i * frameSize], width, height, x, y, scale);
      
      int frameDuration = pgm_read_word(&durations[i]);
      int adjustedDuration = frameDuration / ANIMATION_SPEED;
      
      int checkInterval = 10;
      for (int d = 0; d < adjustedDuration && !stopCurrentEmoji; d += checkInterval) {
        delay(min(checkInterval, adjustedDuration - d));
      }
    }
    
    loopCount++;
  }
}

void playRandomIdleEmoji() {
  EmojiInfo idleEmojis[] = {
    {(const uint16_t*)emoji_buonngu_frames, emoji_buonngu_WIDTH, emoji_buonngu_HEIGHT, 
     emoji_buonngu_FRAMES, emoji_buonngu_durations},
    {(const uint16_t*)emoji_hon_frames, emoji_hon_WIDTH, emoji_hon_HEIGHT,
     emoji_hon_FRAMES, emoji_hon_durations},
    {(const uint16_t*)emoji_haihuoc_frames, emoji_haihuoc_WIDTH, emoji_haihuoc_HEIGHT,
     emoji_haihuoc_FRAMES, emoji_haihuoc_durations},
    {(const uint16_t*)emoji_thoaimai_frames, emoji_thoaimai_WIDTH, emoji_thoaimai_HEIGHT,
     emoji_thoaimai_FRAMES, emoji_thoaimai_durations},
    {(const uint16_t*)emoji_thoaimai4_frames, emoji_thoaimai4_WIDTH, emoji_thoaimai4_HEIGHT,
     emoji_thoaimai4_FRAMES, emoji_thoaimai4_durations}
  };
  
  const char* emojiNames[] = {"buonngu", "hon", "haihuoc", "thoaimai", "thoaimai4"};
  
  int randomIndex = random(0, 5);
  EmojiInfo emoji = idleEmojis[randomIndex];
  
  Serial.printf("🎭 Playing IDLE emoji: %s (%dx%d, %d frames)\n", 
                emojiNames[randomIndex], emoji.width, emoji.height, emoji.frameCount);
  
  tft.fillScreen(ST77XX_BLACK);
  playEmojiAnimation(emoji.frames, emoji.width, emoji.height, 
                     emoji.frameCount, emoji.durations, 2);
}

void playConfusedEmoji() {
  tft.fillScreen(ST77XX_BLACK);
  playEmojiAnimation((const uint16_t*)emoji_boiroi_frames, 
                     emoji_boiroi_WIDTH, emoji_boiroi_HEIGHT,
                     emoji_boiroi_FRAMES, emoji_boiroi_durations, -1);
}

void playSurprisedEmoji() {
  tft.fillScreen(ST77XX_BLACK);
  playEmojiAnimation((const uint16_t*)emoji_batngo_frames,
                     emoji_batngo_WIDTH, emoji_batngo_HEIGHT,
                     emoji_batngo_FRAMES, emoji_batngo_durations, -1);
}

void playWaitingEmoji() {
  tft.fillScreen(ST77XX_BLACK);
  playEmojiAnimation((const uint16_t*)emoji_ngongan_frames,
                     emoji_ngongan_WIDTH, emoji_ngongan_HEIGHT,
                     emoji_ngongan_FRAMES, emoji_ngongan_durations, -1);
}

void setEmojiState(EmojiState newState) {
  if (xSemaphoreTake(emojiStateMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
    if (millis() < qrLockUntil) {
      if (currentEmojiState == EMOJI_QR && newState != EMOJI_QR && newState != EMOJI_IDLE) {
        Serial.printf("🔒 QR LOCKED - Blocked emoji change to %d (lock for %lus more)\n", 
                      newState, (qrLockUntil - millis()) / 1000);
        xSemaphoreGive(emojiStateMutex);
        return;
      }
    }
    
    if (currentEmojiState != newState) {
      previousEmojiState = currentEmojiState;
      currentEmojiState = newState;
      emojiStateChanged = true;
      stopCurrentEmoji = true;
      
      Serial.printf("🎭 Emoji State: %d → %d", previousEmojiState, currentEmojiState);
      if (newState == EMOJI_QR) {
        Serial.printf(" (QR locked for 30s)");
      }
      Serial.println();
    }
    xSemaphoreGive(emojiStateMutex);
  }
}

void emojiTaskFunction(void* parameter) {
  Serial.println("🎭 Emoji task started");
  
  while (true) {
    EmojiState state;
    bool stateChanged = false;
    
    if (xSemaphoreTake(emojiStateMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
      state = currentEmojiState;
      stateChanged = emojiStateChanged;
      if (stateChanged) {
        emojiStateChanged = false;
        stopCurrentEmoji = false;
      }
      xSemaphoreGive(emojiStateMutex);
    } else {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }
    
    if (state == EMOJI_QR) {
      vTaskDelay(pdMS_TO_TICKS(100));
      continue;
    }
    
    switch (state) {
      case EMOJI_IDLE:
        if (stateChanged || stopCurrentEmoji == false) {
          playRandomIdleEmoji();
        }
        break;
        
      case EMOJI_CONFUSED:
        if (stateChanged) {
          playConfusedEmoji();
        }
        break;
        
      case EMOJI_SURPRISED:
        if (stateChanged) {
          playSurprisedEmoji();
        }
        break;
        
      case EMOJI_WAITING:
        if (stateChanged) {
          playWaitingEmoji();
        }
        break;
    }
    
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// ============================================================
// TFT DISPLAY FUNCTIONS (QR)
// ============================================================

void drawQR() {
  if (qrMatrixSize == 0) {
    Serial.println("❌ QR matrix empty");
    return;
  }
  
  Serial.printf("🎨 drawQR() called: %dx%d matrix\n", qrMatrixSize, qrMatrixSize);
  
  stopCurrentEmoji = true;
  delay(100);
  
  Serial.println("   🖥️  Clearing screen...");
  tft.fillScreen(ST77XX_BLACK);
  delay(50);
  
  int maxDimension = min(SCREEN_WIDTH, SCREEN_HEIGHT);
  int moduleSize = maxDimension / (qrMatrixSize + 4);
  if (moduleSize < 2) moduleSize = 2;
  if (moduleSize > 12) moduleSize = 12;
  
  int qrSize = qrMatrixSize * moduleSize;
  int offsetX = (SCREEN_WIDTH - qrSize) / 2;
  int offsetY = (SCREEN_HEIGHT - qrSize) / 2;
  
  Serial.printf("   📏 Module size: %d, QR size: %d, Offset: (%d, %d)\n", 
                moduleSize, qrSize, offsetX, offsetY);
  
  Serial.println("   ✍️  Drawing title...");
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(2);
  tft.setCursor(30, 10);
  tft.println("MA QR THANH TOAN");
  
  Serial.println("   🎨 Drawing QR pixels...");
  int pixelCount = 0;
  for (int y = 0; y < qrMatrixSize; y++) {
    for (int x = 0; x < qrMatrixSize; x++) {
      if (qrMatrix[y][x]) {
        tft.fillRect(
          offsetX + x * moduleSize,
          offsetY + y * moduleSize + 30,
          moduleSize, moduleSize,
          ST77XX_WHITE
        );
        pixelCount++;
      }
    }
  }
  Serial.printf("   ✅ Drew %d QR pixels\n", pixelCount);
  
  Serial.println("   ✍️  Drawing footer...");
  tft.setTextSize(1);
  tft.setCursor(40, SCREEN_HEIGHT - 20);
  tft.println("Quet ma de thanh toan");
  
  qrDisplayed = true;
  qrDisplayStartTime = millis();
  qrLockUntil = millis() + QR_DISPLAY_DURATION;
  
  setEmojiState(EMOJI_QR);
  
  Serial.printf("   ✅ QR display complete!\n");
  Serial.printf("   🔒 QR LOCKED until: %lu (for 30s)\n", qrLockUntil);
}

void clearQRDisplay() {
  if (qrDisplayed) {
    Serial.println("🗑️ Clearing QR display...");
    
    qrMatrixSize = 0;
    qrDisplayed = false;
    qrLockUntil = 0;
    
    tft.fillScreen(ST77XX_BLACK);
    
    stopCurrentEmoji = false;
    setEmojiState(EMOJI_IDLE);
    
    Serial.println("   ✅ QR cleared, lock released, back to IDLE");
  }
}

// ============================================================
// MQTT FUNCTIONS
// ============================================================

void mqttCallback(char* topic, byte* payload, unsigned int len) {
  Serial.println("═══════════════════════════════════");
  Serial.printf("📩 MQTT RECEIVED from topic: %s\n", topic);
  Serial.printf("   Payload size: %u bytes\n", len);
  
  String msg = "";
  for (unsigned int i = 0; i < len; i++) {
    msg += (char)payload[i];
  }
  
  Serial.printf("   First 100 chars: %s...\n", msg.substring(0, min(100, (int)msg.length())).c_str());
  
  if (msg.startsWith("[[")) {
    Serial.println("   ✅ Detected QR matrix format");
    Serial.println("   🛑 FORCE STOPPING ALL ACTIVITIES...");
    
    stopCurrentEmoji = true;
    delay(300);
    
    if (playbackActive && queueCount > 0) {
      Serial.println("   ⚠️  Audio is playing - will continue after QR");
    }
    
    setEmojiState(EMOJI_QR);
    delay(200);
    
    DynamicJsonDocument doc(50000);
    DeserializationError error = deserializeJson(doc, msg);
    
    if (error) {
      Serial.printf("   ❌ JSON parse error: %s\n", error.c_str());
      Serial.println("═══════════════════════════════════");
      return;
    }
    
    JsonArray rows = doc.as<JsonArray>();
    qrMatrixSize = rows.size();
    
    if (qrMatrixSize >= 10 && qrMatrixSize <= 200) {
      Serial.printf("   ✅ Parsing QR matrix: %d×%d\n", qrMatrixSize, qrMatrixSize);
      
      for (int y = 0; y < qrMatrixSize; y++) {
        JsonArray row = rows[y];
        for (int x = 0; x < qrMatrixSize && x < row.size(); x++) {
          qrMatrix[y][x] = row[x].as<bool>();
        }
      }
      
      Serial.println("   🎨 Drawing QR code now...");
      drawQR();
      Serial.println("   ✅ QR displayed successfully");
      Serial.printf("   ⏱️  QR will auto-clear in %d seconds\n", QR_DISPLAY_DURATION / 1000);
    } else {
      Serial.printf("   ❌ Invalid matrix size: %d\n", qrMatrixSize);
    }
  } else {
    Serial.println("   ⚠️  Not a QR matrix");
  }
  Serial.println("═══════════════════════════════════");
}

void connectMQTT() {
  while (!mqtt.connected()) {
    Serial.print("🔌 MQTT connecting...");
    
    String clientId = "ESP32_" + String(random(0xffff), HEX);
    
    if (mqtt.connect(clientId.c_str(), mqtt_username.c_str(), mqtt_password)) {
      Serial.println(" ✅ Connected");
      
      Serial.printf("📡 Subscribing to topic: '%s'\n", topic_qr.c_str());
      bool subResult = mqtt.subscribe(topic_qr.c_str());
      
      if (subResult) {
        Serial.println("   ✅ Subscribed successfully");
      } else {
        Serial.println("   ❌ Subscribe failed!");
      }
    } else {
      Serial.printf(" ❌ Failed (rc=%d)\n", mqtt.state());
      delay(5000);
    }
  }
}

// ============================================================
// AUDIO FILTER CLASS
// ============================================================
class AudioFilter {
private:
  float prevInput = 0;
  float prevOutput = 0;
  const float noiseGateThreshold = 50.0f;
  float preEmphasis_prev = 0;
  const float preEmphasis_coeff = 0.5f;
  float currentGain = 2.0f;
  float targetGain = 2.0f;
  const float gainSmoothFactor = 0.001f;
  float peakLevel = 0;
  const float peakDecay = 0.999f;
  
public:
  int16_t processSample(int16_t sample) {
    float input = (float)sample;
    float alpha = 0.95f;
    float dcBlocked = input - prevInput + alpha * prevOutput;
    prevInput = input;
    prevOutput = dcBlocked;
    
    if (fabs(dcBlocked) < noiseGateThreshold) {
      dcBlocked *= 0.3f;
    }
    
    float emphasized = dcBlocked - preEmphasis_coeff * preEmphasis_prev;
    preEmphasis_prev = dcBlocked;
    
    float absVal = fabs(emphasized);
    if (absVal > peakLevel) {
      peakLevel = absVal;
    } else {
      peakLevel *= peakDecay;
    }
    
    if (peakLevel > 1000.0f) {
      targetGain = 28000.0f / (peakLevel + 100.0f);
    } else {
      targetGain = 2.5f;
    }
    
    currentGain += (targetGain - currentGain) * gainSmoothFactor;
    float output = emphasized * currentGain;
    
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

// ============================================================
// AUDIO SMOOTHER CLASS
// ============================================================
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
  
  float targetGain = 1.0f;
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
    currentGain = 1.0f;
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

// ============================================================
// AUDIO QUEUE FUNCTIONS
// ============================================================

bool enqueueAudio(const uint8_t* data, size_t length) {
  if (xSemaphoreTake(queueMutex, pdMS_TO_TICKS(100)) != pdTRUE) {
    return false;
  }
  
  if (queueCount >= MAX_AUDIO_QUEUE) {
    Serial.printf("⚠️ Audio queue FULL\n");
    xSemaphoreGive(queueMutex);
    return false;
  }
  
  uint8_t* buffer = (uint8_t*)heap_caps_malloc(length, MALLOC_CAP_SPIRAM);
  if (!buffer) {
    buffer = (uint8_t*)malloc(length);
    if (!buffer) {
      Serial.println("❌ Out of memory");
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

// ============================================================
// AUDIO PLAYBACK TASK
// ============================================================

void audioPlaybackTaskFunction(void* parameter) {
  Serial.println("🔊 Audio playback task started");
  
  int totalChunksPlayed = 0;
  bool wasPlaying = false;
  
  while (true) {
    AudioChunk chunk = dequeueAudio();
    
    if (chunk.valid && chunk.data) {
      if (!wasPlaying) {
        if (millis() >= qrLockUntil) {
          setEmojiState(EMOJI_WAITING);
          Serial.println("🔊 Playback started - WAITING emoji");
        } else {
          Serial.printf("🔊 Playback started - QR LOCKED (skip emoji, %lus left)\n",
                        (qrLockUntil - millis()) / 1000);
        }
        wasPlaying = true;
      }
      
      int16_t* audioSamples = (int16_t*)chunk.data;
      size_t numSamples = chunk.length / 2;
      
      float preGain = 1.0f;
      outputSmoother.setGain(preGain);
      outputSmoother.processBuffer(audioSamples, numSamples);
      
      size_t written = 0;
      esp_err_t result = i2s_write(I2S_SPEAKER_PORT, chunk.data, chunk.length, &written, pdMS_TO_TICKS(50));
      
      if (result == ESP_OK) {
        totalChunksPlayed++;
        if (totalChunksPlayed % 30 == 0) {
          Serial.printf(">>> Played %d chunks | Queue: %d\n", totalChunksPlayed, queueCount);
        }
      }
      
      free(chunk.data);
      lastPongTime = millis();
    } else {
      if (wasPlaying && queueCount == 0 && endSignalReceived) {
        wasPlaying = false;
        
        if (millis() >= qrLockUntil) {
          Serial.println("🔊 Playback finished - back to IDLE");
          setEmojiState(EMOJI_IDLE);
        } else {
          Serial.printf("🔊 Playback finished - QR still locked (%lus left), keep QR\n",
                        (qrLockUntil - millis()) / 1000);
        }
      }
      
      vTaskDelay(pdMS_TO_TICKS(1));
    }
  }
}

// ============================================================
// HELPER FUNCTIONS
// ============================================================

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

// ============================================================
// I2S INIT
// ============================================================

bool i2sSpeakerInit() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 24000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 4,
    .dma_buf_len = 256,
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
    .sample_rate = I2S_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 16,
    .dma_buf_len = 512,
    .use_apll = false
  };

  if (i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL) != ESP_OK) return false;
  if (i2s_set_pin(I2S_PORT, &pin_config) != ESP_OK) return false;
  i2s_zero_dma_buffer(I2S_PORT);
  i2s_start(I2S_PORT);
  return true;
}

// ============================================================
// WEBSOCKET EVENT HANDLER
// ============================================================

void webSocketEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.println("✅ WS connected");
      wsConnected = true;
      reconnectAttempts = 0;
      lastPingTime = millis();
      lastPongTime = millis();
      outputSmoother.reset();
      
      setEmojiState(EMOJI_IDLE);
      break;

    case WStype_DISCONNECTED:
      Serial.println("❌ WS disconnected");
      wsConnected = false;
      
      if (playbackActive || queueCount > 0) {
        Serial.printf("⚠️ WS ngắt - phát tiếp %d chunks\n", queueCount);
        endSignalReceived = true;
      }
      break;

    case WStype_TEXT: {
      lastPongTime = millis();
      String message = String((char*)payload);
      
      if (message.startsWith("{")) {
        DynamicJsonDocument doc(2048);
        DeserializationError error = deserializeJson(doc, message);
        if (!error) {
          String type = doc["type"] | "";
          
          if (type == "transcription") {
            String text = doc["message"] | "";
            if (text.length() > 0) {
              Serial.println("\n═══════════════════════════════════");
              Serial.println("👤 BẠN NÓI:");
              Serial.println("   " + text);
              Serial.println("═══════════════════════════════════");
            }
          }
          else if (type == "chat_response") {
            String text = doc["message"] | "";
            if (text.length() > 0) {
              Serial.println("\n🤖 AI TRẢ LỜI:");
              Serial.println("───────────────────────────────────");
              Serial.println(text);
              Serial.println("───────────────────────────────────\n");
            }
          }
        }
      }
      break;
    }

    case WStype_BIN: {
      lastPongTime = millis();
      
      size_t offset = 0;
      if (length < 10) break;

      auto read_u16 = [&](uint8_t* d, size_t& o) {
        uint16_t v = (d[o] << 8) | d[o + 1];
        o += 2;
        return v;
      };
      auto read_u32 = [&](uint8_t* d, size_t& o) {
        uint32_t v = (d[o] << 24) | (d[o + 1] << 16) | (d[o + 2] << 8) | d[o + 3];
        o += 4;
        return v;
      };

      uint16_t macLen = read_u16(payload, offset);
      String mac((char*)payload + offset, macLen);
      offset += macLen;

      uint16_t typeLen = read_u16(payload, offset);
      String msgType((char*)payload + offset, typeLen);
      offset += typeLen;

      uint16_t uuidLen = read_u16(payload, offset);
      String uuid((char*)payload + offset, uuidLen);
      offset += uuidLen;

      uint32_t audioLen = read_u32(payload, offset);
      uint8_t* audioData = payload + offset;

      if (msgType == "START") {
        if (!playbackActive) {
          playbackActive = true;
          playbackStartTime = millis();
          endSignalReceived = false;
          Serial.println(">>> PLAYBACK START <<<");
        }
      }
      else if (msgType == "PROCESSING" && audioLen > 0) {
        lastPongTime = millis();
        
        if (!playbackActive) {
          playbackActive = true;
          playbackStartTime = millis();
        }
        
        enqueueAudio(audioData, audioLen);
      }
      else if (msgType == "END") {
        Serial.println(">>> END SIGNAL <<<");
        endSignalReceived = true;
      }
      
      break;
    }

    default:
      break;
  }
}

// ============================================================
// WIFI CONNECTION
// ============================================================

bool connectWiFi() {
  WiFi.mode(WIFI_STA);
  esp_wifi_set_ps(WIFI_PS_NONE);
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
    
    String mac = WiFi.macAddress();
    mac.toUpperCase();
    mqtt_username = "external_publisher_usr@" + mac;
    topic_qr = "CASSOROBOT" + mac + "/qr";
    
    Serial.println("MQTT User: " + mqtt_username);
    Serial.println("MQTT Topic: " + topic_qr);
    
    return true;
  }
  
  Serial.println("\n❌ WiFi failed");
  return false;
}

// ============================================================
// WEBSOCKET INIT
// ============================================================

void initWebSocket() {
  webSocket.begin(ws_host, ws_port, ws_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.disableHeartbeat();
  Serial.printf("🔌 Connecting to %s:%d%s\n", ws_host, ws_port, ws_path);
}

// ============================================================
// WEBSOCKET HEALTH CHECK
// ============================================================

void checkWebSocketHealth() {
  if (!wsConnected) return;
  if (recordingActive || playbackActive) return;
  
  unsigned long now = millis();
  
  if (now - lastPingTime > PING_INTERVAL) {
    Serial.println("📡 Sending PING");
    webSocket.sendPing();
    lastPingTime = now;
  }
  
  if (!playbackActive && queueCount == 0 && now - lastPongTime > PONG_TIMEOUT) {
    Serial.println("⚠️ WS timeout - reconnecting");
    wsConnected = false;
    webSocket.disconnect();
    delay(1000);
    initWebSocket();
  }
  else if (playbackActive || queueCount > 0) {
    lastPongTime = now;
  }
}

void handleReconnect() {
  if (wsConnected) return;
  if (playbackActive || queueCount > 0) return;
  
  unsigned long now = millis();
  if (now - lastReconnectAttempt < RECONNECT_COOLDOWN) return;
  
  lastReconnectAttempt = now;
  reconnectAttempts++;
  
  Serial.printf("🔄 Reconnect attempt %d/%d\n", reconnectAttempts, MAX_RECONNECT_ATTEMPTS);
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ WiFi disconnected");
    WiFi.disconnect();
    delay(100);
    connectWiFi();
  }
  
  initWebSocket();
  
  if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    Serial.println("❌ Max reconnect - restarting");
    delay(1000);
    ESP.restart();
  }
}

// ============================================================
// WEBSOCKET SEND PACKET
// ============================================================

void sendBinaryPacket(
    const String& macStr,
    const String& typeStr,
    const String& uuidStr,
    const uint8_t* audioData,
    uint32_t audioLen
) {
  if (!wsConnected) return;

  uint16_t macLen = macStr.length();
  uint16_t typeLen = typeStr.length();
  uint16_t uuidLen = uuidStr.length();

  size_t totalSize = 2 + macLen + 2 + typeLen + 2 + uuidLen + 4 + audioLen;

  if (totalSize > 65535) {
    Serial.println("❌ Packet too large");
    return;
  }

  uint8_t* buffer = (uint8_t*)malloc(totalSize);
  if (!buffer) {
    Serial.println("❌ Out of memory");
    return;
  }

  size_t offset = 0;

  buffer[offset++] = (macLen >> 8) & 0xFF;
  buffer[offset++] = macLen & 0xFF;
  memcpy(buffer + offset, macStr.c_str(), macLen);
  offset += macLen;

  buffer[offset++] = (typeLen >> 8) & 0xFF;
  buffer[offset++] = typeLen & 0xFF;
  memcpy(buffer + offset, typeStr.c_str(), typeLen);
  offset += typeLen;

  buffer[offset++] = (uuidLen >> 8) & 0xFF;
  buffer[offset++] = uuidLen & 0xFF;
  memcpy(buffer + offset, uuidStr.c_str(), uuidLen);
  offset += uuidLen;

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
    Serial.println("⚠️ Send failed");
    wsConnected = false;
  }
}

// ============================================================
// RECORD AND STREAM
// ============================================================

void recordAndStream() {
  if (!wsConnected) {
    Serial.println("❌ WS not ready");
    return;
  }

  if (!i2sBuffer || !pcmBuffer) {
    Serial.println("❌ Buffers not initialized");
    return;
  }

  clearQRDisplay();

  if (playbackActive || queueCount > 0) {
    Serial.println("⏳ Waiting for audio to finish...");
    unsigned long waitStart = millis();
    while ((playbackActive || queueCount > 0) && millis() - waitStart < 30000) {
      delay(10);
      webSocket.loop();
    }
    delay(100);
  }

  clearAudioQueue();
  outputSmoother.reset();
  playbackActive = false;
  endSignalReceived = false;
  
  sessionId = generateUUIDv4();
  Serial.println("\n🎙️ RECORDING START");
  Serial.println("Session: " + sessionId);

  sendBinaryPacket(deviceMacAddress, "START", sessionId, NULL, 0);
  delay(50);

  audioFilter.reset();
  recordingActive = true;

  unsigned long startTime = millis();
  unsigned long lastSoundTime = millis();
  unsigned long lastPrintTime = millis();
  unsigned long lastHealthCheck = millis();
  int chunkCount = 0;
  bool hadSound = false;
  bool isConfused = true;

  setEmojiState(EMOJI_CONFUSED);

  while (true) {
    if (millis() - lastHealthCheck > 2000) {
      if (!wsConnected) {
        Serial.println("❌ Lost connection");
        break;
      }
      webSocket.loop();
      lastHealthCheck = millis();
    }

    size_t bytesRead = 0;
    i2s_read(I2S_PORT, i2sBuffer, I2S_READ_LEN, &bytesRead, portMAX_DELAY);
    if (bytesRead == 0) continue;

    size_t pcmSamples = bytesRead / 2;
    size_t pcmBytes = 0;
    
    int16_t* samples = (int16_t*)malloc(pcmSamples * sizeof(int16_t));
    if (!samples) {
      Serial.println("❌ OOM samples");
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
    free(samples);
    
    if (rms > SILENCE_THRESHOLD) {
      lastSoundTime = millis();
      hadSound = true;
      
      if (isConfused) {
        setEmojiState(EMOJI_SURPRISED);
        isConfused = false;
      }
    }

    if (millis() - lastPrintTime > 500) {
      unsigned long silenceDuration = millis() - lastSoundTime;
      if (rms > SILENCE_THRESHOLD) {
        Serial.printf("🎤 RMS: %.1f ✅\n", rms);
      } else {
        Serial.printf("🔇 RMS: %.1f (%.1fs)\n", rms, silenceDuration/1000.0);
      }
      lastPrintTime = millis();
    }

    unsigned long silenceDuration = millis() - lastSoundTime;
    if (hadSound && silenceDuration > SILENCE_DURATION) {
      Serial.printf("\n⏹️ Silence %.1fs - Stop\n", silenceDuration/1000.0);
      break;
    }

    if (pcmBytes > 0) {
      bool disconnected = false;
      for (size_t offset = 0; offset < pcmBytes; offset += CHUNK_SIZE) {
        size_t chunkLen = min((size_t)CHUNK_SIZE, pcmBytes - offset);
        
        if (!wsConnected) {
          Serial.println("⚠️ Lost connection");
          disconnected = true;
          break;
        }
        
        sendBinaryPacket(deviceMacAddress, "PROCESSING", sessionId, pcmBuffer + offset, chunkLen);
        chunkCount++;
        webSocket.loop();
        yield();
      }
      
      if (disconnected) break;
    }
  }

  Serial.println("📤 Sending END...");
  sendBinaryPacket(deviceMacAddress, "END", sessionId, NULL, 0);
  
  Serial.printf("✅ Sent %d chunks in %.1fs\n", 
                chunkCount, (millis() - startTime) / 1000.0);
  
  recordingActive = false;
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(115200);
  esp_bt_controller_disable();

  pinMode(BUTTON_PIN, INPUT_PULLUP);

  Serial.println("🖥️ Initializing TFT...");
  
  SPI.begin(TFT_SCK, -1, TFT_SDA, TFT_CS);
  Serial.println("   ✅ SPI initialized");
  
  tft.init(240, 320);
  Serial.println("   ✅ TFT init OK");
  
  tft.setRotation(3);
  Serial.println("   ✅ Rotation set to 3 (Landscape)");
  
  tft.fillScreen(ST77XX_RED);
  Serial.println("   🔴 Screen RED");
  delay(1000);
  
  tft.fillScreen(ST77XX_GREEN);
  Serial.println("   🟢 Screen GREEN");
  delay(1000);
  
  tft.fillScreen(ST77XX_BLUE);
  Serial.println("   🔵 Screen BLUE");
  delay(1000);
  
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(2);
  tft.setCursor(50, SCREEN_HEIGHT/2 - 10);
  tft.println("STARTING...");
  Serial.println("   ✅ TFT fully ready");

  if (!SPIFFS.begin(true)) {
    Serial.println("❌ SPIFFS failed");
    tft.fillScreen(ST77XX_RED);
    tft.setCursor(30, SCREEN_HEIGHT/2 - 10);
    tft.println("SPIFFS FAIL");
    return;
  }
  
  if (psramFound()) {
    Serial.println("✅ PSRAM detected");
    Serial.printf("   Total: %d bytes (%.2f MB)\n", ESP.getPsramSize(), ESP.getPsramSize() / 1024.0 / 1024.0);
    Serial.printf("   Free: %d bytes (%.2f MB)\n", ESP.getFreePsram(), ESP.getFreePsram() / 1024.0 / 1024.0);
    
    i2sBuffer = (uint8_t*)heap_caps_malloc(I2S_READ_LEN, MALLOC_CAP_SPIRAM);
    pcmBuffer = (uint8_t*)heap_caps_malloc(CHUNK_SIZE, MALLOC_CAP_SPIRAM);
    
    if (!i2sBuffer || !pcmBuffer) {
      Serial.println("❌ Failed to allocate in PSRAM");
      return;
    }
    Serial.println("✅ Buffers allocated in PSRAM");
  } else {
    Serial.println("⚠️ PSRAM not found");
    i2sBuffer = (uint8_t*)malloc(I2S_READ_LEN);
    pcmBuffer = (uint8_t*)malloc(CHUNK_SIZE);
    
    if (!i2sBuffer || !pcmBuffer) {
      Serial.println("❌ Failed to allocate buffers");
      return;
    }
    Serial.println("✅ Buffers allocated in RAM");
  }

  if (!connectWiFi()) {
    Serial.println("❌ WiFi failed");
    ESP.restart();
  }
  
  if (!i2sInit()) {
    Serial.println("❌ I2S mic failed");
    return;
  }

  if (!i2sSpeakerInit()) {
    Serial.println("❌ I2S speaker failed");
    return;
  }

  Serial.println("🔌 Initializing MQTT...");
  mqtt.setServer(mqtt_server, mqtt_port);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(16384);
  Serial.println("   ✅ MQTT buffer: 16KB");
  connectMQTT();

  emojiStateMutex = xSemaphoreCreateMutex();
  if (emojiStateMutex == NULL) {
    Serial.println("❌ Failed to create emoji mutex");
    return;
  }

  queueMutex = xSemaphoreCreateMutex();
  if (queueMutex == NULL) {
    Serial.println("❌ Failed to create audio mutex");
    return;
  }
  
  servoMutex = xSemaphoreCreateMutex();
  if (servoMutex == NULL) {
    Serial.println("❌ Failed to create servo mutex");
    return;
  }
  
  for (int i = 0; i < MAX_AUDIO_QUEUE; i++) {
    audioQueue[i].data = NULL;
    audioQueue[i].length = 0;
    audioQueue[i].valid = false;
  }
  
  // Create emoji task (Core 1, Priority 2)
  xTaskCreatePinnedToCore(
    emojiTaskFunction,
    "EmojiTask",
    8192,
    NULL,
    2,
    &emojiTask,
    1
  );
  
  if (emojiTask == NULL) {
    Serial.println("❌ Failed to create emoji task");
    return;
  }
  
  // Create audio playback task (Core 0, Priority 4)
  xTaskCreatePinnedToCore(
    audioPlaybackTaskFunction,
    "AudioPlayback",
    8192,
    NULL,
    4,
    &audioPlaybackTask,
    0
  );
  
  if (audioPlaybackTask == NULL) {
    Serial.println("❌ Failed to create audio task");
    return;
  }

  // Create direction detection task (Core 1, Priority 1)
  xTaskCreatePinnedToCore(
    directionDetectionTaskFunction,
    "DirectionDetection",
    4096,
    NULL,
    1,
    &directionTask,
    1
  );
  
  if (directionTask == NULL) {
    Serial.println("❌ Failed to create direction task");
    return;
  }

  initWebSocket();

  Serial.println("═══════════════════════════════════");
  Serial.println("✅ ESP32 VOICE AI + EMOJI + QR + SERVO!");
  Serial.println("═══════════════════════════════════");
  Serial.println("🎭 EMOJI STATES:");
  Serial.println("   😴 Idle: Random animations");
  Serial.println("   😕 Confused: Button pressed, no sound");
  Serial.println("   😲 Surprised: Recording audio");
  Serial.println("   😋 Waiting: Playing response");
  Serial.println("   💳 QR: Payment code displayed");
  Serial.println("═══════════════════════════════════");
  Serial.println("🎯 SERVO DIRECTION:");
  Serial.println("   🎧 MAX9814 Left: GPIO 35");
  Serial.println("   🎧 MAX9814 Right: GPIO 36");
  Serial.println("   🔄 Servo: GPIO 8");
  Serial.println("   ⏱️  Auto-center: 10s timeout");
  Serial.println("═══════════════════════════════════");
  Serial.println("📱 AUTO MODE:");
  Serial.println("   🔘 Press button → Auto mode ON");
  Serial.println("   🔄 Auto record when silence 3s");
  Serial.println("   ⏹️  Press again → Auto mode OFF");
  Serial.println("═══════════════════════════════════\n");
  
  delay(2000);
}

// ============================================================
// LOOP
// ============================================================

void loop() {
  webSocket.loop();
  
  if (!mqtt.connected()) {
    Serial.println("⚠️ MQTT disconnected - reconnecting...");
    connectMQTT();
  }
  mqtt.loop();
  
  static unsigned long lastMqttDebug = 0;
  if (millis() - lastMqttDebug > 10000) {
    lastMqttDebug = millis();
    Serial.printf("📊 MQTT Status: %s | Topic: %s\n", 
                  mqtt.connected() ? "Connected" : "Disconnected",
                  topic_qr.c_str());
  }
  
  if (qrDisplayed && !waitingToRestart) {
    unsigned long qrDisplayTime = millis() - qrDisplayStartTime;
    
    static unsigned long lastCountdownUpdate = 0;
    if (millis() - lastCountdownUpdate >= 1000) {
      lastCountdownUpdate = millis();
      
      int secondsLeft = (QR_DISPLAY_DURATION - qrDisplayTime) / 1000;
      if (secondsLeft > 0 && secondsLeft <= 30) {
        if (currentEmojiState == EMOJI_QR && millis() < qrLockUntil) {
          tft.fillRect(SCREEN_WIDTH - 50, 5, 45, 20, ST77XX_BLACK);
          tft.setTextColor(ST77XX_YELLOW);
          tft.setTextSize(2);
          tft.setCursor(SCREEN_WIDTH - 45, 8);
          tft.printf("%02d", secondsLeft);
        }
        
        Serial.printf("⏱️  QR locked for %d more seconds...\n", secondsLeft);
      }
    }
    
    if (qrDisplayTime >= QR_DISPLAY_DURATION) {
      Serial.println("⏰ QR display timeout (30s) - clearing and resuming...");
      clearQRDisplay();
      
      if (autoRecordingMode && wsConnected) {
        Serial.println("🔄 Auto-resuming conversation...");
        audioFinishedTime = millis();
        waitingToRestart = true;
      }
    }
  }
  
  if (endSignalReceived && playbackActive) {
    if (queueCount == 0) {
      delay(50);
      clearAudioQueue();
      outputSmoother.reset();
      playbackActive = false;
      endSignalReceived = false;
      Serial.println(">>> PLAYBACK DONE <<<");
      
      if (!qrDisplayed || (millis() - qrDisplayStartTime >= QR_DISPLAY_DURATION)) {
        setEmojiState(EMOJI_IDLE);
      }
      
      if (autoRecordingMode) {
        audioFinishedTime = millis();
        waitingToRestart = true;
        Serial.println("⏳ Wait 3s...");
      }
    }
  }
  
  if (playbackActive && !endSignalReceived) {
    if (millis() - playbackStartTime > 120000) {
      Serial.println("⚠️ Playback timeout");
      clearAudioQueue();
      outputSmoother.reset();
      playbackActive = false;
      endSignalReceived = false;
      if (!qrDisplayed || (millis() - qrDisplayStartTime >= QR_DISPLAY_DURATION)) {
        setEmojiState(EMOJI_IDLE);
      }
    }
  }
  
  static unsigned long lastQueueEmptyTime = 0;
  if (playbackActive && queueCount == 0 && !endSignalReceived) {
    if (lastQueueEmptyTime == 0) {
      lastQueueEmptyTime = millis();
    }
    
    unsigned long waitTime = millis() - lastQueueEmptyTime;
    
    if (!wsConnected) {
      Serial.println("⚠️ WS disconnected");
      playbackActive = false;
      endSignalReceived = false;
      clearAudioQueue();
      lastQueueEmptyTime = 0;
      return;
    }
    
    if (waitTime > 2000 && waitTime % 2000 < 100) {
      Serial.printf("⏳ Waiting audio... (%.1fs)\n", waitTime / 1000.0);
    }
    
    if (waitTime > 10000) {
      Serial.println("⚠️ Audio timeout 10s");
      playbackActive = false;
      endSignalReceived = false;
      clearAudioQueue();
      lastQueueEmptyTime = 0;
      if (!qrDisplayed || (millis() - qrDisplayStartTime >= QR_DISPLAY_DURATION)) {
        setEmojiState(EMOJI_IDLE);
      }
    }
  } else if (queueCount > 0) {
    lastQueueEmptyTime = 0;
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ WiFi disconnected");
    connectWiFi();
  }
  
  checkWebSocketHealth();
  handleReconnect();
  
  if (waitingToRestart && autoRecordingMode && wsConnected) {
    if (millis() - audioFinishedTime >= 3000) {
      waitingToRestart = false;
      Serial.println("🔄 AUTO RESTART");
      
      if (!isRecording && !playbackActive && queueCount == 0 && !endSignalReceived) {
        isRecording = true;
        recordAndStream();
        isRecording = false;
      }
    }
  }
  
  static bool lastButtonState = HIGH;
  bool currentButtonState = digitalRead(BUTTON_PIN);

  if (lastButtonState == HIGH && currentButtonState == LOW) {
    delay(50);
    if (digitalRead(BUTTON_PIN) == LOW) {
      if (!autoRecordingMode) {
        autoRecordingMode = true;
        Serial.println("✅ AUTO MODE ON");

        if (wsConnected && !isRecording && !playbackActive) {
          isRecording = true;
          recordAndStream();
          isRecording = false;
        }
      } else {
        autoRecordingMode = false;
        waitingToRestart = false;
        Serial.println("⏹️ AUTO MODE OFF");

        if (!qrDisplayed) {
          setEmojiState(EMOJI_IDLE);
        }
      }

      while (digitalRead(BUTTON_PIN) == LOW) {
        delay(10);
      }
    }
  }
  lastButtonState = currentButtonState;

  delay(5);
}

#pragma GCC diagnostic pop