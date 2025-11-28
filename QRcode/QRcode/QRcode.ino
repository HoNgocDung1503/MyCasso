#include <WiFi.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <SPI.h>


// TFT Pins
#define TFT_CS 10
#define TFT_DC 21
#define TFT_RST 47
#define TFT_SDA 13
#define TFT_SCK 12
#define SCREEN_WIDTH 240
#define SCREEN_HEIGHT 320

Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_SDA, TFT_SCK, TFT_RST);

// WiFi & MQTT
const char* ssid = "dev";
const char* password = "123456789";
const char* mqtt_server = "mqtt.loathanhtoan.com";
String mqtt_password = "GC0pCmTP2gLCiocpXyjXlVJPVkRLQuyK";
String topic_qr, mqtt_username;

WiFiClient espClient;
PubSubClient mqtt(espClient);

bool matrix[200][200];
int matrixSize = 0;

void showMsg(String msg, uint16_t color = ST77XX_WHITE) {
  Serial.println("📺 TFT: " + msg);
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(color);
  tft.setTextSize(2);
  tft.setCursor(20, 140);
  tft.println(msg);
}

void drawQR() {
  if (!matrixSize) {
    Serial.println("⚠️ Matrix size = 0, không vẽ QR");
    return;
  }
  
  int moduleSize = min(SCREEN_WIDTH, SCREEN_HEIGHT) / (matrixSize + 4);
  if (moduleSize < 2) moduleSize = 2;
  if (moduleSize > 12) moduleSize = 12;
  
  int qrSize = matrixSize * moduleSize;
  int offsetX = (SCREEN_WIDTH - qrSize) / 2;
  int offsetY = (SCREEN_HEIGHT - qrSize) / 2;
  
  Serial.printf("🎨 Vẽ QR: Size=%dx%d, Module=%dpx, Offset=(%d,%d)\n", 
                matrixSize, matrixSize, moduleSize, offsetX, offsetY);
  
  tft.fillScreen(ST77XX_BLACK);
  
  for (int y = 0; y < matrixSize; y++) {
    for (int x = 0; x < matrixSize; x++) {
      tft.fillRect(
        offsetX + x * moduleSize,
        offsetY + y * moduleSize,
        moduleSize, moduleSize,
        matrix[y][x] ? ST77XX_WHITE : ST77XX_BLACK
      );
    }
  }
  
  Serial.println("✅ QR code đã được vẽ");
}

void mqttCallback(char* topic, byte* payload, unsigned int len) {
  Serial.printf("📨 MQTT nhận: Topic='%s', Length=%d bytes\n", topic, len);
  
  String msg = "";
  for (unsigned int i = 0; i < len; i++) msg += (char)payload[i];
  
  Serial.println("📄 Nội dung: " + msg.substring(0, min((int)msg.length(), 100)) + (msg.length() > 100 ? "..." : ""));
  
  if (msg.startsWith("[[")) {
    Serial.println("🔍 Phát hiện JSON array, bắt đầu parse...");
    
    DynamicJsonDocument doc(50000);
    DeserializationError error = deserializeJson(doc, msg);
    
    if (error) {
      Serial.printf("❌ JSON parse lỗi: %s\n", error.c_str());
      return;
    }
    
    Serial.println("✅ JSON parse thành công");
    
    JsonArray rows = doc.as<JsonArray>();
    matrixSize = rows.size();
    
    Serial.printf("📊 Matrix size: %d\n", matrixSize);
    
    if (matrixSize >= 10 && matrixSize <= 200) {
      for (int y = 0; y < matrixSize; y++) {
        JsonArray row = rows[y];
        for (int x = 0; x < matrixSize; x++) {
          matrix[y][x] = row[x].as<bool>();
        }
      }
      Serial.println("✅ Matrix đã được load");
      drawQR();
    } else {
      Serial.printf("⚠️ Matrix size không hợp lệ: %d (phải từ 10-200)\n", matrixSize);
    }
  } else {
    Serial.println("ℹ️ Message không phải QR matrix");
  }
}

void connectMQTT() {
  while (!mqtt.connected()) {
    showMsg("MQTT...", ST77XX_YELLOW);
    Serial.println("🔄 Đang kết nối MQTT...");
    Serial.printf("   Server: %s:1883\n", mqtt_server);
    Serial.printf("   Username: %s\n", mqtt_username.c_str());
    
    if (mqtt.connect(("ESP32_" + String(random(0xffff), HEX)).c_str(), 
                     mqtt_username.c_str(), mqtt_password.c_str())) {
      Serial.println("✅ MQTT connected");
      
      mqtt.subscribe(topic_qr.c_str());
      Serial.printf("📬 Subscribed to: %s\n", topic_qr.c_str());
      
      showMsg("READY", ST77XX_GREEN);
      delay(1000);
    } else {
      Serial.printf("❌ MQTT failed, rc=%d\n", mqtt.state());
      Serial.println("   Thử lại sau 5s...");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n\n==========================================");
  Serial.println("🚀 ESP32 QR Display System Starting...");
  Serial.println("==========================================\n");
  
  Serial.println("🖥️ Khởi tạo TFT display...");
  tft.init(SCREEN_WIDTH, SCREEN_HEIGHT);
  tft.setRotation(0);
  showMsg("STARTING");
  Serial.printf("   Resolution: %dx%d\n", SCREEN_WIDTH, SCREEN_HEIGHT);
  
  Serial.println("\n📡 Kết nối WiFi...");
  Serial.printf("   SSID: %s\n", ssid);
  WiFi.begin(ssid, password);
  showMsg("WiFi...", ST77XX_YELLOW);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  
  showMsg("WiFi OK", ST77XX_GREEN);
  Serial.println("✅ WiFi connected");
  Serial.printf("   IP: %s\n", WiFi.localIP().toString().c_str());
  
  String mac = WiFi.macAddress();
  mac.toUpperCase();
  Serial.printf("   MAC: %s\n", mac.c_str());
  
  mqtt_username = "external_publisher_usr@" + mac;
  topic_qr = "CASSOROBOT" + mac + "/qr";

  Serial.println("\n🔧 MQTT Configuration:");
  Serial.printf("   Username: %s\n", mqtt_username.c_str());
  Serial.printf("   Topic: %s\n", topic_qr.c_str());
  
  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(10240);
  Serial.printf("   Buffer size: 10240 bytes\n");
  
  Serial.println("\n🔌 Kết nối MQTT broker...");
  connectMQTT();
  
  Serial.println("\n✅ Setup hoàn tất - Hệ thống sẵn sàng!\n");
}

void loop() {
  if (!mqtt.connected()) {
    Serial.println("⚠️ MQTT disconnected, reconnecting...");
    connectMQTT();
  }
  mqtt.loop();
  delay(10);
}