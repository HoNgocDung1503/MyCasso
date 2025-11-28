/*
 * Hệ thống nhận diện hướng âm thanh + Điều khiển Servo
 * - 2 cảm biến MAX9814: GPIO 35 (trái) và GPIO 34 (phải)
 * - Servo MG90S: GPIO 12
 * - Tự động quay servo theo hướng có người nói
 * - Tự động quay về giữa sau 10 giây không có âm thanh
 */

#include <ESP32Servo.h>

// ========== CẤU HÌNH CHÂN ==========
const int LEFT_MIC = 1;    // Cảm biến bên trái
const int RIGHT_MIC = 2;   // Cảm biến bên phải
const int SERVO_PIN = 8;   // Servo

// ========== CẤU HÌNH CẢMBIẾN ÂM THANH ==========
const int BASELINE_MIN = 1000;
const int BASELINE_MAX = 1800;
const int THRESHOLD = 50;
const int NOISE_TOLERANCE = 5;  // Cho phép tối đa 5 mẫu nhiễu
const int SAMPLE_WINDOW = 50;
const int SAMPLE_DELAY = 1;

// ========== CẤU HÌNH SERVO ==========
const int SERVO_MIN_US = 500;
const int SERVO_MAX_US = 2500;
const int SERVO_FREQ = 50;

// Góc servo
const int ANGLE_CENTER = 0;
const int ANGLE_LEFT = -90;
const int ANGLE_RIGHT = 90;

// ========== BIẾN TOÀN CỤC ==========
Servo myServo;
unsigned long lastSoundTime = 0;       // Thời điểm phát hiện âm thanh cuối cùng
const unsigned long TIMEOUT = 10000;   // 10 giây timeout
int currentServoAngle = 0;             // Góc hiện tại của servo
bool isAtCenter = true;                // Servo có đang ở giữa không

// Enum để quản lý trạng thái
enum Direction {
  DIR_CENTER,
  DIR_LEFT,
  DIR_RIGHT
};

Direction currentDirection = DIR_CENTER;

void setup() {
  Serial.begin(115200);
  delay(500);
  
  Serial.println("\n========================================");
  Serial.println("Hệ thống Nhận diện Hướng + Servo");
  Serial.println("========================================");
  Serial.println("Trái: GPIO 35 | Phải: GPIO 34");
  Serial.println("Servo: GPIO 12");
  Serial.println("========================================\n");
  
  // Khởi tạo Servo
  ESP32PWM::allocateTimer(0);
  myServo.setPeriodHertz(SERVO_FREQ);
  myServo.attach(SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  
  // Đưa servo về vị trí giữa
  moveServoToAngle(ANGLE_CENTER);
  
  Serial.println("✓ Servo đã sẵn sàng tại vị trí 0°");
  Serial.println("✓ Bắt đầu giám sát âm thanh...\n");
  
  lastSoundTime = millis();
}

void loop() {
  // Thu thập mẫu từ 2 cảm biến
  int leftValues[SAMPLE_WINDOW];
  int rightValues[SAMPLE_WINDOW];
  
  for (int i = 0; i < SAMPLE_WINDOW; i++) {
    leftValues[i] = analogRead(LEFT_MIC);
    rightValues[i] = analogRead(RIGHT_MIC);
    delay(SAMPLE_DELAY);
  }
  
  // Tính toán các chỉ số
  float leftVariance = calculateVariance(leftValues, SAMPLE_WINDOW);
  float rightVariance = calculateVariance(rightValues, SAMPLE_WINDOW);
  int leftAvg = calculateAverage(leftValues, SAMPLE_WINDOW);
  int rightAvg = calculateAverage(rightValues, SAMPLE_WINDOW);
  int leftMin = getMin(leftValues, SAMPLE_WINDOW);
  int leftMax = getMax(leftValues, SAMPLE_WINDOW);
  int rightMin = getMin(rightValues, SAMPLE_WINDOW);
  int rightMax = getMax(rightValues, SAMPLE_WINDOW);
  
  // Đếm số mẫu vượt ngưỡng
  int leftOutOfRange = countOutOfRange(leftValues, SAMPLE_WINDOW);
  int rightOutOfRange = countOutOfRange(rightValues, SAMPLE_WINDOW);
  
  // Hiển thị thông tin
  Serial.print("L: ");
  Serial.print(leftAvg);
  Serial.print("[");
  Serial.print(leftMin);
  Serial.print("-");
  Serial.print(leftMax);
  Serial.print("] Var=");
  Serial.print(leftVariance, 0);
  Serial.print(" Out=");
  Serial.print(leftOutOfRange);
  
  Serial.print(" | R: ");
  Serial.print(rightAvg);
  Serial.print("[");
  Serial.print(rightMin);
  Serial.print("-");
  Serial.print(rightMax);
  Serial.print("] Var=");
  Serial.print(rightVariance, 0);
  Serial.print(" Out=");
  Serial.print(rightOutOfRange);
  
  // Kiểm tra có âm thanh không
  bool leftHasSound = (leftOutOfRange > NOISE_TOLERANCE);
  bool rightHasSound = (rightOutOfRange > NOISE_TOLERANCE);
  
  if (!leftHasSound && !rightHasSound) {
    // Không có âm thanh
    Serial.print(" [Yên tĩnh]");
    
    // Kiểm tra timeout - quay về giữa sau 10 giây không có âm thanh
    if (!isAtCenter && (millis() - lastSoundTime >= TIMEOUT)) {
      Serial.println();
      Serial.println(">>> TIMEOUT: Quay về vị trí giữa (0°)");
      moveServoToAngle(ANGLE_CENTER);
      currentDirection = DIR_CENTER;
      isAtCenter = true;
    }
    
  } else {
    // CÓ ÂM THANH - Cập nhật thời gian
    lastSoundTime = millis();
    isAtCenter = false;
    
    // Phân tích hướng
    float varianceDiff = abs(leftVariance - rightVariance);
    Direction detectedDirection = DIR_CENTER;
    
    if (varianceDiff > THRESHOLD) {
      if (leftVariance > rightVariance) {
        detectedDirection = DIR_LEFT;
        Serial.print(" >>> BÊN TRÁI");
      } else {
        detectedDirection = DIR_RIGHT;
        Serial.print(" >>> BÊN PHẢI");
      }
    } else {
      detectedDirection = DIR_CENTER;
      Serial.print(" >>> GIỮA");
    }
    
    // Điều khiển servo nếu hướng thay đổi
    if (detectedDirection != currentDirection) {
      Serial.println();
      
      switch(detectedDirection) {
        case DIR_LEFT:
          Serial.println("🎯 Servo quay TRÁI (-90°)");
          moveServoToAngle(ANGLE_LEFT);
          break;
          
        case DIR_RIGHT:
          Serial.println("🎯 Servo quay PHẢI (+90°)");
          moveServoToAngle(ANGLE_RIGHT);
          break;
          
        case DIR_CENTER:
          Serial.println("🎯 Servo quay GIỮA (0°)");
          moveServoToAngle(ANGLE_CENTER);
          break;
      }
      
      currentDirection = detectedDirection;
    }
  }
  
  Serial.println();
  delay(200);
}

// ========== HÀM ĐIỀU KHIỂN SERVO ==========

/**
 * Di chuyển servo đến góc chỉ định
 */
void moveServoToAngle(int angle) {
  angle = constrain(angle, -90, 90);
  int writeValue = angle + 90;  // Chuyển từ -90~90 sang 0~180
  myServo.write(writeValue);
  currentServoAngle = angle;
  delay(300);  // Đợi servo di chuyển
}

/**
 * Di chuyển servo mượt mà (tùy chọn)
 */
void smoothMoveToAngle(int targetAngle, int stepDelay = 15) {
  targetAngle = constrain(targetAngle, -90, 90);
  
  int currentWrite = myServo.read();
  int currentAngle = currentWrite - 90;
  
  int step = (targetAngle > currentAngle) ? 1 : -1;
  
  for(int angle = currentAngle; angle != targetAngle; angle += step) {
    int writeValue = angle + 90;
    myServo.write(writeValue);
    delay(stepDelay);
  }
  
  myServo.write(targetAngle + 90);
  currentServoAngle = targetAngle;
}

// ========== HÀM XỬ LÝ CẢMBIẾN ==========

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
  float mean = calculateAverage(values, size);
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