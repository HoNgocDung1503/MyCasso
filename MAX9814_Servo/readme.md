code này là liên kết giữa sensor cảm biến âm thanh max9814 và servo
dùng để nhận biết âm thanh trái hoặc phải và servo quay hướng tương ứng

servo mg90s này quay được góc 90 độ, tức là từ -90 -> 90

Phạm vi xung PWM 0.5ms - 2.5ms: góc quay tối đa 180 độ

input pulse signal range                        servo output shaft 
cycle is 20ms                                       turning angel

0.5ms                                                   -90 độ 
1ms                                                     -45 độ
1.5ms                                                   -0 độ
2ms                                                     45 độ
2.5ms                                                   90 độ


thiết lập sai sẽ CHÁYY

// ========== CẤU HÌNH SERVO ==========
const int SERVO_MIN_US = 500;
const int SERVO_MAX_US = 2500;
const int SERVO_FREQ = 50;

// Góc servo
const int ANGLE_CENTER = 0;
const int ANGLE_LEFT = -90;
const int ANGLE_RIGHT = 90;