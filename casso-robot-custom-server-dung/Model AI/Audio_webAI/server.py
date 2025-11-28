# server.py - Complete Voice AI Assistant with QR Payment
# ✅ FIXED: QR timing - Send QR BEFORE TTS audio
# ✅ FIXED: MAC address topic format with colons "DC:B4:D9:13:55:C8"
# Features: Voice Recognition, Product Management, Payment, QR Display
# Version: 2.0 COMPLETE FIX

import asyncio
import websockets
import struct
import json
import uuid
import wave
import io
import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
import importlib
import products
import re

# ============================================================
# MQTT & QR GENERATION IMPORTS
# ============================================================
import paho.mqtt.client as mqtt
import requests
from PIL import Image
import numpy as np
import base64 as b64

# ============================================================
# SERVER CONFIG
# ============================================================
SERVER_NAME = "javis"
SERVER_INTRO = "Chào bạn, tôi là javis, trợ lí AI của cửa hàng, rất vui được nói chuyện với bạn."

# ============================================================
# MQTT CONFIG
# ============================================================
MQTT_BROKER = "mqtt.loathanhtoan.com"
MQTT_PORT = 1883
MQTT_PASSWORD = "GC0pCmTP2gLCiocpXyjXlVJPVkRLQuyK"
# Username sẽ được truyền động theo MAC, mặc định để trống
MQTT_USERNAME = None

# ============================================================
# VIETQR CONFIG - ✅ THAY ĐỔI THÔNG TIN TÀI KHOẢN CỦA BẠN
# ============================================================
VIETQR_API = "https://api.vietqr.io/v2/generate"
VIETQR_API_KEY = "we-l0v3-v1et-qr"
VIETQR_ACCOUNT = {
    "accountNo": "0987648717",        # ✅ Số tài khoản
    "accountName": "HO NGOC DUNG",    # ✅ Tên tài khoản
    "acqId": 970415,                  # ✅ Mã ngân hàng (VietinBank)
    "format": "text",
    "template": "qr_only"
}

# Global MQTT client
mqtt_client = None

# ============================================================
# MQTT INIT - ✅ IMPROVED WITH CONNECTION MONITORING
# ============================================================

def init_mqtt(mac_address=None):
    """Khởi tạo MQTT client với monitoring và truyền đúng username nếu có"""
    global mqtt_client
    global MQTT_USERNAME
    try:
        mqtt_client = mqtt.Client()
        # Nếu có MAC address, tạo username đúng format
        if mac_address:
            mac_clean = mac_address.upper()
            if ":" not in mac_clean:
                mac_clean = ":".join([mac_clean[i:i+2] for i in range(0, len(mac_clean), 2)])
            MQTT_USERNAME = f"external_publisher_usr@{mac_clean}"
        # Nếu không có MAC, để username trống (hoặc có thể cấu hình mặc định)
        if MQTT_USERNAME:
            mqtt_client.username_pw_set(username=MQTT_USERNAME, password=MQTT_PASSWORD)
            print(f"🔑 MQTT Username: {MQTT_USERNAME}")
        else:
            mqtt_client.username_pw_set(username="", password=MQTT_PASSWORD)
            print(f"🔑 MQTT Username: <empty>")
        # ✅ Set callbacks để monitor connection
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                print("✅ MQTT connected successfully")
            else:
                print(f"❌ MQTT connection failed: rc={rc}")
        def on_disconnect(client, userdata, rc):
            print(f"⚠️ MQTT disconnected: rc={rc}")
            if rc != 0:
                print("🔄 Unexpected disconnect - will auto-reconnect")
        def on_publish(client, userdata, mid):
            print(f"✅ MQTT message published: mid={mid}")
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_publish = on_publish
        print(f"🔌 Connecting to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        import time
        time.sleep(2)
        if mqtt_client.is_connected():
            print(f"✅ MQTT broker connected: {MQTT_BROKER}")
            return True
        else:
            print("❌ MQTT connection timeout")
            return False
    except Exception as e:
        print(f"❌ MQTT init failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================
# QR GENERATION FUNCTIONS
# ============================================================

def generate_qr_matrix(payment_data: dict) -> list:
    """
    Sinh QR code VietQR và chuyển thành matrix
    
    Args:
        payment_data: Dict chứa total_amount, items, order_id
    
    Returns:
        List 2D (1=đen, 0=trắng) hoặc None nếu lỗi
    """
    try:
        # 1. Chuẩn bị payload cho VietQR API
        amount = int(payment_data['total_amount'])
        order_id = payment_data.get('order_id', 'ORDER')
        
        vietqr_payload = {
            **VIETQR_ACCOUNT,
            "amount": amount,
            "addInfo": f"Thanh toan {order_id}",
            "format": "text",
            "template": "compact"
        }
        
        print(f"\n🔄 Generating QR for {amount:,}đ (Order: {order_id})")
        
        # 2. Gọi API VietQR
        headers = {
            'x-api-key': VIETQR_API_KEY,
            'Content-Type': 'application/json'
        }
        response = requests.post(VIETQR_API, json=vietqr_payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        # 3. Lấy chuỗi qrCode
        if 'data' in data and 'qrCode' in data['data']:
            qr_code_string = data['data']['qrCode']
        elif 'qrCode' in data:
            qr_code_string = data['qrCode']
        else:
            print("❌ Không tìm thấy qrCode trong response")
            print("Response:", data)
            return None
        print(f"QR Code String: {qr_code_string[:50]}...")
        
        # 4. Tạo QR code từ chuỗi
        import qrcode
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=0,
        )
        qr.add_data(qr_code_string)
        qr.make(fit=True)
        # 5. Lấy ma trận
        qr_matrix = qr.get_matrix()
        matrix = [[int(cell) for cell in row] for row in qr_matrix]
        print(f"✅ QR matrix generated: {len(matrix)}x{len(matrix[0])}")
        return matrix
        
    except requests.Timeout:
        print("❌ VietQR API timeout")
        return None
    except Exception as e:
        print(f"❌ Error generating QR matrix: {e}")
        import traceback
        traceback.print_exc()
        return None

def send_qr_to_display(mac_address: str, qr_matrix: list):
    """
    Gửi QR matrix qua MQTT đến ESP32 display
    
    Args:
        mac_address: MAC của ESP32 (VD: "DC:B4:D9:13:55:C8")
        qr_matrix: List 2D
    """
    if not mqtt_client or not qr_matrix:
        print("❌ MQTT not ready or QR matrix empty")
        return False
    
    try:
       
        mac_clean = mac_address.upper()
        
        # Nếu không có dấu :, thêm vào (format: AABBCCDDEEFF -> AA:BB:CC:DD:EE:FF)
        if ":" not in mac_clean:
            mac_clean = ":".join([mac_clean[i:i+2] for i in range(0, len(mac_clean), 2)])
        
        # ✅ Topic format: CASSOROBOTDC:B4:D9:13:55:C8/qr (GIỮ NGUYÊN dấu :)
        topic = f"CASSOROBOT{mac_clean}/qr"
        
        # ✅ Kiểm tra MQTT connection
        if not mqtt_client.is_connected():
            print("❌ MQTT client not connected! Reconnecting...")
            try:
                mqtt_client.reconnect()
                import time
                time.sleep(1)
            except Exception as e:
                print(f"❌ Reconnect failed: {e}")
                return False
        
        # Convert matrix to JSON string
        payload = json.dumps(qr_matrix, separators=(',', ':'))
        
        print(f"\n📡 Publishing QR to MQTT:")
        print(f"   Topic: {topic}")
        print(f"   MAC address: {mac_clean}")
        print(f"   Payload size: {len(payload)} bytes")
        print(f"   MQTT connected: {mqtt_client.is_connected()}")
        
        # Publish to MQTT với QoS 1 để đảm bảo delivery
        result = mqtt_client.publish(topic, payload, qos=1)
        
        # Đợi publish hoàn tất
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"⏳ Waiting for publish confirmation...")
            result.wait_for_publish(timeout=3.0)
            print(f"✅ QR sent to MQTT successfully (mid={result.mid})")
            return True
        else:
            print(f"❌ MQTT publish failed: rc={result.rc}")
            print(f"   Error codes: 0=success, 1=QoS1, 2=QoS2, 4=disconnected")
            return False
            
    except Exception as e:
        print(f"❌ Error sending QR to MQTT: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_order_id():
    """Tạo order ID ngắn gọn"""
    import hashlib
    timestamp = str(datetime.now().timestamp())
    return hashlib.md5(timestamp.encode()).hexdigest()[:8].upper()

# ============================================================
# PRODUCTS MODULE RELOAD
# ============================================================

def reload_products_module():
    """Reload products module to get latest code and update all accessors"""
    global products
    global process_payment_request, get_all_products, search_products, format_price
    global get_store_info, get_store_address, format_store_info
    global add_product, remove_product, update_product_price
    
    products = importlib.reload(products)
    
    # Update all accessor functions
    process_payment_request = products.process_payment_request
    get_all_products = products.get_all_products
    search_products = products.search_products
    format_price = products.format_price    
    get_store_info = products.get_store_info
    get_store_address = products.get_store_address
    format_store_info = products.format_store_info
    add_product = products.add_product
    remove_product = products.remove_product
    update_product_price = products.update_product_price
    
    print("🔄 Products module reloaded and all accessors updated!")
    return products

# Convenience accessors (initial setup)
process_payment_request = products.process_payment_request
get_all_products = products.get_all_products
search_products = products.search_products
format_price = products.format_price
get_store_info = products.get_store_info
get_store_address = products.get_store_address
format_store_info = products.format_store_info

# NEW: Dynamic product management accessors
add_product = products.add_product
remove_product = products.remove_product
update_product_price = products.update_product_price

# ============================================================
# OPENAI CLIENT
# ============================================================

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

# ============================================================
# SESSION STORAGE
# ============================================================

active_sessions = {}
conversation_contexts = {}

# ============================================================
# CONVERSATION CONTEXT CLASS
# ============================================================

class ConversationContext:
    """Lưu trữ context của conversation cho mỗi user (theo MAC address)"""
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.conversation_history = []
        self.pending_payment = None
        self.last_interaction = datetime.now()
        
    def add_message(self, role, content):
        """Thêm message vào conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content
        })
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
        self.last_interaction = datetime.now()
    
    def set_pending_payment(self, payment_data):
        """Lưu thông tin đơn hàng đang chờ xác nhận"""
        self.pending_payment = payment_data
        self.last_interaction = datetime.now()
    
    def clear_pending_payment(self):
        """Xóa đơn hàng pending"""
        self.pending_payment = None
    
    def reset(self):
        """Reset conversation"""
        self.conversation_history = []
        self.pending_payment = None
        self.last_interaction = datetime.now()

# ============================================================
# AUDIO SESSION CLASS
# ============================================================

class AudioSession:
    def __init__(self, session_id, mac_address):
        self.session_id = session_id
        self.mac_address = mac_address
        self.audio_buffer = bytearray()
        self.sample_rate = 24000
        self.channels = 1
        self.created_at = datetime.now()
        
    def add_audio_chunk(self, audio_data):
        self.audio_buffer.extend(audio_data)
        
    def get_wav_bytes(self):
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(bytes(self.audio_buffer))
        return wav_buffer.getvalue()
    
    def clear_buffer(self):
        self.audio_buffer = bytearray()

# ============================================================
# PROTOCOL FUNCTIONS
# ============================================================

def encode_length_string(text):
    text_bytes = text.encode('utf-8')
    length = len(text_bytes)
    return struct.pack('>H', length) + text_bytes

def decode_length_string(data, offset):
    length = struct.unpack('>H', data[offset:offset+2])[0]
    text = data[offset+2:offset+2+length].decode('utf-8')
    return text, offset + 2 + length

def create_message(mac_address, msg_type, msg_id, data=b''):
    message = bytearray()
    message.extend(encode_length_string(mac_address))
    message.extend(encode_length_string(msg_type))
    message.extend(encode_length_string(msg_id))
    message.extend(struct.pack('>I', len(data)))
    message.extend(data)
    return bytes(message)

def parse_message(data):
    offset = 0
    mac_address, offset = decode_length_string(data, offset)
    msg_type, offset = decode_length_string(data, offset)
    msg_id, offset = decode_length_string(data, offset)
    data_length = struct.unpack('>I', data[offset:offset+4])[0]
    offset += 4
    audio_data = data[offset:offset+data_length] if data_length > 0 else b''
    return mac_address, msg_type, msg_id, audio_data

# ============================================================
# CONTEXT MANAGEMENT
# ============================================================

def get_or_create_context(mac_address):
    if mac_address not in conversation_contexts:
        conversation_contexts[mac_address] = ConversationContext(mac_address)
    
    context = conversation_contexts[mac_address]
    time_diff = (datetime.now() - context.last_interaction).total_seconds()
    if time_diff > 300:
        print(f"🔄 Context timeout for {mac_address}, resetting...")
        context.reset()
    
    return context

# ============================================================
# PRODUCT MANAGEMENT DETECTION FUNCTIONS
# ============================================================

def detect_add_product_intent(user_message: str) -> dict:
    """Phát hiện ý định THÊM MÓN MỚI VÀO MENU"""
    message_lower = user_message.lower().strip()
    
    has_price_keyword = "giá" in message_lower or "gia" in message_lower
    
    if not has_price_keyword:
        return {'is_add_product': False}
    
    price_match = re.search(r'(\d+)\s*(nghìn|ngàn|k|đ|đồng)?', message_lower)
    
    if not price_match:
        return {'is_add_product': False}
    
    price_value = int(price_match.group(1))
    price_unit = price_match.group(2) if len(price_match.groups()) > 1 and price_match.group(2) else ""
    
    if price_unit in ['nghìn', 'ngàn', 'k']:
        actual_price = price_value * 1000
    else:
        actual_price = price_value
    
    if actual_price < 5000:
        return {'is_add_product': False}
    
    match = re.search(r'(.+?)(?:\s+|\s*\W*)giá\s*', message_lower)
    
    if not match:
        return {'is_add_product': False}
    
    raw_text = match.group(1).strip()
    product_name = raw_text
    
    words_to_remove = [
        'thêm', 'tạo', 'sản phẩm', 'món', 'vào', 'menu', 'thực đơn'
    ]
    
    for word in words_to_remove:
        product_name = re.sub(r'\b' + word + r'\b', '', product_name, flags=re.IGNORECASE)
    
    product_name = re.sub(r'\b(cho\s+(?:tôi|em))\b', '', product_name, flags=re.IGNORECASE)
    
    product_name = re.sub(
        r'^\s*\d+\s+(?:cái|tô|to|ly|li|lí|hộp|hop|chai|gói|goi|kg|ki|bó|bo)\s+',
        '',
        product_name,
        flags=re.IGNORECASE
    )
    
    product_name = ' '.join(product_name.split())
    
    if not product_name or len(product_name) < 2:
        return {'is_add_product': False}
    
    unit_keywords = {
        'cái': 'cái',
        'hộp': 'hộp', 'hop': 'hộp',
        'chai': 'chai',
        'ly': 'ly', 'li': 'ly', 'lí': 'ly',
        'tô': 'tô', 'to': 'tô',
        'gói': 'gói', 'goi': 'gói',
        'kg': 'kg', 'ki': 'kg',
        'bó': 'bó', 'bo': 'bó'
    }
    
    unit = "cái"
    
    for keyword, unit_value in unit_keywords.items():
        if re.search(r'\b' + keyword + r'\b', message_lower):
            unit = unit_value
            break
    
    product_name = ' '.join(word.capitalize() for word in product_name.split())
    
    category = "Khác"
    product_name_lower = product_name.lower()
    
    food_keywords = ['bánh', 'phở', 'bún', 'cơm', 'mì', 'canh', 'hủ tiếu', 'tiêu', 'bao', 'xôi']
    drink_keywords = ['nước', 'sữa', 'cà phê', 'trà', 'cafe', 'coffee', 'đá', 'cam', 'chanh']
    snack_keywords = ['snack', 'kẹo', 'quy', 'bánh quy']
    fruit_keywords = ['táo', 'cam', 'chuối', 'xoài', 'dưa', 'ổi']
    
    if any(word in product_name_lower for word in food_keywords):
        category = "Thức ăn"
    elif any(word in product_name_lower for word in drink_keywords):
        category = "Đồ uống"
    elif any(word in product_name_lower for word in snack_keywords):
        category = "Snack"
    elif any(word in product_name_lower for word in fruit_keywords):
        category = "Trái cây"
    
    print(f"\n{'='*60}")
    print(f"✅ ADD PRODUCT INTENT DETECTED")
    print(f"{'='*60}")
    print(f"📝 Raw input    : '{user_message}'")
    print(f"📝 Raw text     : '{raw_text}'")
    print(f"🍽️  Product name : '{product_name}'")
    print(f"💰 Price        : {actual_price:,}đ")
    print(f"📦 Unit         : {unit}")
    print(f"📂 Category     : {category}")
    print(f"{'='*60}\n")
    
    return {
        'is_add_product': True,
        'product_name': product_name,
        'price': actual_price,
        'unit': unit,
        'category': category
    }

def detect_remove_product_intent(user_message: str) -> dict:
    """Phát hiện ý định xóa món"""
    message_lower = user_message.lower().strip()
    
    remove_keywords = [
        "xóa món", "bỏ món", "xóa sản phẩm", "xoá món",
        "xóa cho tôi món", "xóa cho em món", "xóa giúp tôi món",
        "bỏ cho tôi món", "bỏ cho em món"
    ]
    
    is_remove = any(keyword in message_lower for keyword in remove_keywords)
    
    if not is_remove:
        if message_lower.startswith("xóa ") or message_lower.startswith("xoá "):
            is_remove = True
        else:
            return {'is_remove_product': False}
    
    patterns = [
        r'(?:xóa|xoá|bỏ)\s+(?:cho\s+(?:tôi|em)\s+)?món\s+(.+)',
        r'(?:xóa|xoá|bỏ)\s+món\s+(.+)',
        r'(?:xóa|xoá|bỏ)\s+(.+)',
    ]
    
    product_name = None
    for pattern in patterns:
        match = re.search(pattern, message_lower)
        if match:
            product_name = match.group(1).strip()
            break
    
    if product_name:
        product_name = product_name.replace("cho tôi", "").replace("cho em", "")
        product_name = product_name.replace("giúp tôi", "").strip()
        
        product_name = ' '.join(word.capitalize() for word in product_name.split())
        
        return {
            'is_remove_product': True,
            'product_name': product_name
        }
    
    return {'is_remove_product': False}

def detect_update_price_intent(user_message: str) -> dict:
    """Phát hiện ý định CẬP NHẬT GIÁ"""
    message_lower = user_message.lower().strip()
    
    if any(kw in message_lower for kw in ["bao nhiêu", "là bao nhiêu", "giá gì", "giá mấy"]):
        return {'is_update_price': False}
    
    update_keywords = [
        "cập nhật giá", "đổi giá", "sửa giá", "thay đổi giá",
        "thay giá", "chỉnh giá", "điều chỉnh giá", "muốn sửa giá"
    ]
    
    is_update = any(keyword in message_lower for keyword in update_keywords)
    
    if not is_update:
        return {'is_update_price': False}
    
    patterns = [
        r'(?:cập nhật giá|đổi giá|sửa giá|thay đổi giá|thay giá|chỉnh giá|muốn sửa giá)\s+(?:của\s+)?(?:món\s+)?(.+?)\s+(?:thành|là|về)\s+(\d+)\s*(nghìn|ngàn|k|đ)?',
        r'(.+?)\s+(?:thành|về|là)\s+(\d+)\s*(nghìn|ngàn|k|đ)?',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message_lower)
        if match:
            product_name = match.group(1).strip()
            
            product_name = product_name.replace("giá", "").replace("gia", "")
            product_name = product_name.replace("của món", "").replace("món", "")
            product_name = product_name.replace("cập nhật", "").replace("đổi", "")
            product_name = product_name.replace("sửa", "").replace("thay đổi", "")
            product_name = product_name.replace("muốn", "").strip()
            
            product_name = ' '.join(word.capitalize() for word in product_name.split())
            
            new_price = int(match.group(2))
            price_unit = match.group(3) if len(match.groups()) > 2 and match.group(3) else ""
            
            if price_unit in ['nghìn', 'ngàn', 'k']:
                new_price = new_price * 1000
            
            return {
                'is_update_price': True,
                'product_name': product_name,
                'new_price': new_price
            }
    
    return {'is_update_price': False}

def is_payment_intent(user_message: str) -> bool:
    """Kiểm tra xem có phải ý định thanh toán không"""
    message_lower = user_message.lower().strip()
    
    if any(kw in message_lower for kw in ["thêm món", "xóa món", "bỏ món", "cập nhật giá", "đổi giá"]):
        return False
    
    exclusion_patterns = [
        "thời tiết", "weather", "tin tức", "news", "bản tin",
        "địa chỉ", "ở đâu", "chỗ nào", "đường",
        "giờ", "mấy giờ", "bao giờ", "khi nào",
        "mở cửa", "đóng cửa", "làm việc",
        "giá bao nhiêu", "bao nhiêu tiền", "giá cả",
        "giá", "bán giá", "giá gì", "giá món",
        "cho biết", "cho tôi biết", "cho em biết",
        "hỏi", "là gì", "thế nào", "như thế nào", "ra sao",
        "tại sao", "vì sao", "có phải", "có đúng",
        "có bán", "có không", "bán không", "có món",
        "giới thiệu", "nói về", "kể về", "mô tả"
    ]
    
    has_exclusion = any(pattern in message_lower for pattern in exclusion_patterns)
    if has_exclusion:
        return False
    
    strong_payment_keywords = [
        "mua", "đặt", "order", "gọi món", "đặt món",
        "thanh toán", "thành toán", "tính tiền", "total", "tổng cộng"
    ]
    
    has_strong_keyword = any(keyword in message_lower for keyword in strong_payment_keywords)
    if has_strong_keyword:
        return True
    
    weak_payment_keywords = ["cho tôi", "cho em", "lấy", "cho", "em muốn", "tôi muốn"]
    has_weak_keyword = any(keyword in message_lower for keyword in weak_payment_keywords)
    
    if has_weak_keyword:
        has_number = bool(re.search(r'\d+|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười', message_lower))
        if not has_number:
            return False
        
        all_products = get_all_products()
        product_names = [p.name.lower() for p in all_products]
        has_product = any(pname in message_lower for pname in product_names)
        
        if has_product:
            return True
        else:
            return False
    
    return False

# ============================================================
# AUDIO PROCESSING
# ============================================================

async def transcribe_audio(audio_bytes):
    try:
        temp_file = f"temp_audio_{uuid.uuid4()}.wav"
        with open(temp_file, 'wb') as f:
            f.write(audio_bytes)
        
        with open(temp_file, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="vi"
            )
        
        os.remove(temp_file)
        return transcript.text
    except Exception as e:
        print(f"Lỗi transcribe audio: {e}")
        return None

# ============================================================
# ORDER MODIFICATION HANDLERS
# ============================================================

async def handle_remove_from_order(user_message: str, mac_address: str, existing_payment: dict) -> str:
    try:
        context = get_or_create_context(mac_address)
        remove_items_result = process_payment_request(user_message)

        if not remove_items_result['success'] or not remove_items_result['items']:
            return "Xin lỗi, tôi không hiểu món bạn muốn hủy. Vui lòng nói rõ hơn."

        updated_items = existing_payment['items'].copy()
        removed_something = False
        
        for remove_item in remove_items_result['items']:
            remove_product_id = remove_item['product_id']
            remove_quantity = remove_item['quantity']
            
            for existing_item in updated_items:
                if existing_item['product_id'] == remove_product_id:
                    removed_something = True
                    if existing_item['quantity'] > remove_quantity:
                        existing_item['quantity'] -= remove_quantity
                        unit_price = existing_item['subtotal'] / (existing_item['quantity'] + remove_quantity)
                        existing_item['subtotal'] = unit_price * existing_item['quantity']
                    else:
                        updated_items.remove(existing_item)
                    break

        if not removed_something:
            return "Xin lỗi, không tìm thấy món cần hủy trong đơn hàng."

        new_total = sum(item['subtotal'] for item in updated_items)
        updated_payment = {
            'success': True,
            'total_amount': new_total,
            'items': updated_items,
            'currency': 'VND'
        }
        context.set_pending_payment(updated_payment)

        if updated_items:
            order_summary = []
            for item in updated_items:
                order_summary.append(
                    f"- {item['quantity']} {item['unit']} {item['product_name']}: {format_price(item['subtotal'])}"
                )
            order_text = "\n".join(order_summary)
            total_text = format_price(new_total)
            ai_response = f"Đã hủy món thành công. Đơn hàng hiện tại:\n{order_text}\n\nTổng cộng: {total_text}\n\nAnh/chị xác nhận đơn hàng này nhé?"
        else:
            ai_response = "Đã hủy tất cả món trong đơn hàng. Đơn hàng hiện đã trống. Anh/chị muốn đặt món khác không ạ?"

        context.add_message("user", user_message)
        context.add_message("assistant", ai_response)
        return ai_response
    except Exception as e:
        print(f"Lỗi hủy món: {e}")
        return "Xin lỗi, có lỗi khi hủy món. Vui lòng thử lại."

async def handle_add_to_order(user_message: str, mac_address: str, existing_payment: dict) -> str:
    try:
        context = get_or_create_context(mac_address)
        new_items_result = process_payment_request(user_message)
        
        if not new_items_result['success']:
            return "Xin lỗi, tôi không hiểu món bạn muốn thêm. Vui lòng nói rõ hơn."
        
        merged_items = existing_payment['items'].copy()
        
        for new_item in new_items_result['items']:
            found = False
            for existing_item in merged_items:
                if existing_item['product_id'] == new_item['product_id']:
                    existing_item['quantity'] += new_item['quantity']
                    existing_item['subtotal'] += new_item['subtotal']
                    found = True
                    break
            if not found:
                merged_items.append(new_item)
        
        new_total = sum(item['subtotal'] for item in merged_items)
        updated_payment = {
            'success': True,
            'total_amount': new_total,
            'items': merged_items,
            'currency': 'VND'
        }
        
        context.set_pending_payment(updated_payment)
        
        order_summary = []
        for item in merged_items:
            order_summary.append(
                f"- {item['quantity']} {item['unit']} {item['product_name']}: {format_price(item['subtotal'])}"
            )
        
        order_text = "\n".join(order_summary)
        total_text = format_price(new_total)
        
        ai_response = f"""Dạ, cho em cập nhật đơn hàng:
{order_text}

Tổng cộng: {total_text}

Anh/chị xác nhận đơn hàng này nhé?"""
        
        context.add_message("user", user_message)
        context.add_message("assistant", ai_response)
        return ai_response
        
    except Exception as e:
        print(f"Lỗi thêm món: {e}")
        return "Xin lỗi, có lỗi khi thêm món. Vui lòng thử lại."

# ============================================================
# ✅ NEW: PAYMENT CONFIRMATION HANDLER WITH QR TIMING FIX
# ============================================================

async def handle_payment_confirmation(context, payment_data, mac_address, user_message):
    """
    ✅ FIXED: Send QR to MQTT BEFORE generating TTS
    
    Flow:
    1. Generate QR matrix
    2. Send QR via MQTT (blocking)
    3. Wait 500ms for ESP32 to receive
    4. Return text response (TTS will be generated after)
    """
    try:
        print("\n" + "="*60)
        print("💳 PAYMENT CONFIRMATION - QR TIMING FIX")
        print("="*60)
        
        # STEP 1: Generate order ID
        payment_data_with_id = {
            **payment_data,
            'order_id': generate_order_id()
        }
        
        # STEP 2: Generate QR matrix
        print("🔄 Generating QR matrix...")
        qr_matrix = generate_qr_matrix(payment_data_with_id)
        
        if not qr_matrix:
            print("❌ QR generation failed")
            response_text = f"""Cảm ơn anh/chị! Đơn hàng đã được xác nhận.

Tổng tiền: {format_price(payment_data['total_amount'])}

Xin lỗi, không thể tạo mã QR. Vui lòng thanh toán trực tiếp."""
            context.add_message("user", user_message)
            context.add_message("assistant", response_text)
            context.clear_pending_payment()
            return response_text
        
        # STEP 3: Send QR to ESP32 BEFORE TTS (CRITICAL!)
        print(f"📡 Sending QR to ESP32: {mac_address}")
        print("   ⚠️  This happens BEFORE TTS audio generation!")
        qr_sent = send_qr_to_display(mac_address, qr_matrix)
        
        if not qr_sent:
            print("❌ QR send to MQTT failed!")
            response_text = f"""Cảm ơn anh/chị! Đơn hàng đã được xác nhận.

Tổng tiền: {format_price(payment_data['total_amount'])}

Xin lỗi, không thể hiển thị mã QR. Vui lòng thanh toán trực tiếp."""
        else:
            print("✅ QR sent successfully via MQTT")
            
            # CRITICAL: Wait for ESP32 to receive and process MQTT message
            print("⏳ Waiting 500ms for ESP32 to receive QR...")
            await asyncio.sleep(0.5)
            print("✅ Wait complete - ESP32 should have QR now")
            
            # Now generate text response
            # ⚠️ Change wording to NOT mention "đang hiển thị" since it's already there
            response_text = f"""Cảm ơn anh/chị! Đơn hàng đã được xác nhận.

Tổng tiền: {format_price(payment_data['total_amount'])}

Vui lòng quét mã QR trên màn hình để thanh toán."""
        
        # STEP 4: Update context
        context.add_message("user", user_message)
        context.add_message("assistant", response_text)
        context.clear_pending_payment()
        
        print("="*60)
        print("✅ Payment confirmation complete")
        print("="*60 + "\n")
        
        return response_text
        
    except Exception as e:
        print(f"❌ Error in payment confirmation: {e}")
        import traceback
        traceback.print_exc()
        return "Xin lỗi, có lỗi xảy ra. Vui lòng thử lại."

# ============================================================
# MAIN AI RESPONSE HANDLER
# ============================================================

async def get_ai_response(user_message, mac_address, conversation_history=None):
    try:
        context = get_or_create_context(mac_address)

        # ====== ƯU TIÊN 0: Trả lời khi hỏi "bạn là ai" ======
        who_am_i_patterns = [
            r"bạn là ai", r"mày là ai", r"ai đang nói chuyện",
            r"ai trả lời", r"ai vậy", r"ai thế",
            r"trợ lý ai", r"trợ lí ai", r"trợ lý", r"trợ lí",
            r"tên bạn là gì", r"tên mày là gì", r"tên gì"
        ]
        user_message_lower = user_message.lower()
        if any(re.search(pattern, user_message_lower) for pattern in who_am_i_patterns):
            context.add_message("user", user_message)
            context.add_message("assistant", SERVER_INTRO)
            return SERVER_INTRO

        # ====== ƯU TIÊN 1: PRODUCT MANAGEMENT ======
        add_intent = detect_add_product_intent(user_message)
        if add_intent.get('is_add_product'):
            print(f"🆕 ADD PRODUCT detected: {add_intent}")
            result = add_product(
                add_intent['product_name'],
                add_intent['price'],
                add_intent['unit'],
                add_intent['category']
            )
            reload_products_module()
            response = result['message']
            context.add_message("user", user_message)
            context.add_message("assistant", response)
            return response

        remove_intent = detect_remove_product_intent(user_message)
        if remove_intent['is_remove_product']:
            print(f"🗑️ REMOVE PRODUCT detected: {remove_intent}")
            product_names_raw = remove_intent['product_name']
            product_names = re.split(r',\s*|\s+và\s+', product_names_raw)
            removed_products = []
            failed_products = []
            for pname in product_names:
                pname = pname.strip()
                if not pname:
                    continue
                result = remove_product(pname)
                if result['success']:
                    actual_name = result.get('product_name', pname)
                    removed_products.append(actual_name)
                else:
                    failed_products.append(pname)
            reload_products_module()
            if removed_products:
                response = f"Đã xóa các món sau: {', '.join(removed_products)}"
                if failed_products:
                    response += f"\n\nKhông tìm thấy để xóa: {', '.join(failed_products)}"
            else:
                response = f"Không tìm thấy món nào để xóa."
            context.add_message("user", user_message)
            context.add_message("assistant", response)
            return response

        update_intent = detect_update_price_intent(user_message)
        if update_intent['is_update_price']:
            print(f"💰 UPDATE PRICE detected: {update_intent}")
            result = update_product_price(
                update_intent['product_name'],
                update_intent['new_price']
            )
            reload_products_module()
            response = result['message']
            context.add_message("user", user_message)
            context.add_message("assistant", response)
            return response

        # ====== XEM MENU ======
        menu_keywords = [
            "menu", "thực đơn", "món gì", "bán gì", "có gì", "sản phẩm gì",
            "bán những gì", "những món", "danh sách", "xem menu", "cho xem", "xin menu"
        ]
        is_menu_request = (
            any(keyword in user_message.lower() for keyword in menu_keywords)
            and not (
                add_intent.get('is_add_product') or
                detect_remove_product_intent(user_message).get('is_remove_product') or
                detect_update_price_intent(user_message).get('is_update_price')
            )
        )
        if is_menu_request:
            return await handle_normal_chat(user_message, mac_address, context.conversation_history)

        # ====== XỬ LÝ XÁC NHẬN/HỦY THANH TOÁN ======
        confirmation_keywords = ["oke", "ok", "okay", "được", "đồng ý", "xác nhận", "chấp nhận", "đúng rồi", "vâng", "dạ"]
        message_lower = user_message.lower().strip()
        word_count = len(message_lower.split())
        is_question = any(q in message_lower for q in ["không?", "chưa?", "sao", "gì", "nào", "đâu", "bao nhiêu", "có bán", "có không", "bán không"])
        is_confirmation = word_count <= 10 and not is_question and any(keyword in message_lower for keyword in confirmation_keywords)
        cancellation_phrases = ["không lấy", "không mua", "thôi không", "hủy đơn", "cancel", "đổi ý", "thôi ạ", "thôi em"]
        is_cancellation = not is_question and any(phrase in message_lower for phrase in cancellation_phrases)
        
        if context.pending_payment and is_confirmation:
            # ✅ USE NEW PAYMENT CONFIRMATION HANDLER
            return await handle_payment_confirmation(
                context=context,
                payment_data=context.pending_payment,
                mac_address=mac_address,
                user_message=user_message
            )
            
        elif context.pending_payment and is_cancellation:
            response_text = "Dạ, tôi đã hủy đơn hàng. Anh/chị cần gì thêm không ạ?"
            context.add_message("user", user_message)
            context.add_message("assistant", response_text)
            context.clear_pending_payment()
            return response_text
        elif context.pending_payment and is_question:
            pass

        # ====== CHỈNH SỬA ĐƠN HÀNG ======
        add_more_keywords = ["thêm", "nữa", "thêm nữa", "cộng thêm", "tính thêm"]
        is_adding_more = any(keyword in user_message.lower() for keyword in add_more_keywords)
        remove_item_keywords = ["bỏ", "hủy", "loại bỏ", "không lấy", "xóa", "cancel món", "bỏ món", "hủy món"]
        is_removing_item = any(keyword in user_message.lower() for keyword in remove_item_keywords)
        
        if context.pending_payment and is_adding_more:
            return await handle_add_to_order(user_message, mac_address, context.pending_payment)
        if context.pending_payment and is_removing_item:
            return await handle_remove_from_order(user_message, mac_address, context.pending_payment)

        # ====== ĐẶT HÀNG / CHAT THÔNG THƯỜNG ======
        if is_payment_intent(user_message):
            return await handle_payment_request(user_message, mac_address)
        else:
            return await handle_normal_chat(user_message, mac_address, context.conversation_history)

    except Exception as e:
        print(f"Lỗi get AI response: {e}")
        import traceback
        traceback.print_exc()
        return "Xin lỗi, tôi không thể trả lời ngay bây giờ."

# ============================================================
# PAYMENT REQUEST HANDLER
# ============================================================

async def handle_payment_request(user_message: str, mac_address: str) -> str:
    try:
        context = get_or_create_context(mac_address)
        payment_result = process_payment_request(user_message)
        
        if not payment_result['success']:
            products_list = get_all_products()
            available_products = "\n".join([
                f"- {p.name}: {format_price(p.price)}/{p.unit}" 
                for p in products_list[:10]
            ])
            
            response_text = f"""Xin lỗi, tôi không tìm thấy sản phẩm trong yêu cầu của bạn.

📋 Một số sản phẩm có sẵn:
{available_products}

Bạn muốn mua gì ạ?"""
            context.add_message("user", user_message)
            context.add_message("assistant", response_text)
            return response_text
        
        context.set_pending_payment(payment_result)
        
        system_prompt = """Bạn là nhân viên thanh toán thông minh và thân thiện.

NHIỆM VỤ:
- Xác nhận đơn hàng của khách một cách rõ ràng, lịch sự
- Đọc từng món và số lượng
- Thông báo tổng tiền cuối cùng
- Hỏi khách xác nhận đơn hàng

PHONG CÁCH:
- Ngắn gọn, chuyên nghiệp
- Thân thiện, lịch sự
- Đọc rõ ràng từng món và giá"""

        order_summary = []
        for item in payment_result['items']:
            order_summary.append(f"{item['quantity']} {item['unit']} {item['product_name']} - {format_price(item['subtotal'])}")
        
        order_text = "\n".join(order_summary)
        total_text = format_price(payment_result['total_amount'])
        
        user_prompt = f"""Khách hàng đặt:
{order_text}

Tổng tiền: {total_text}

Hãy xác nhận đơn hàng theo phong cách chuyên nghiệp."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=3000,
            messages=messages,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content
        context.add_message("user", user_message)
        context.add_message("assistant", ai_response)
        return ai_response
        
    except Exception as e:
        print(f"Lỗi xử lý thanh toán: {e}")
        return "Xin lỗi, có lỗi xảy ra khi xử lý đơn hàng. Vui lòng thử lại."

# ============================================================
# NORMAL CHAT HANDLER
# ============================================================

async def handle_normal_chat(user_message: str, mac_address: str, conversation_history: list) -> str:
    try:
        context = get_or_create_context(mac_address)
        
        menu_keywords = ["menu", "thực đơn", "món gì", "bán gì", "có gì", "sản phẩm gì", "bán những gì", "những món", "danh sách"]
        is_asking_menu = any(keyword in user_message.lower() for keyword in menu_keywords)
        
        if is_asking_menu:
            print(f"📋 User asking for full menu: {user_message}")
            
            try:
                with open('custom_products.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    all_products = []
                    for pid, pdata in data.items():
                        all_products.append(products.Product(**pdata))
                print(f"✅ Loaded {len(all_products)} products from JSON")
            except Exception as e:
                print(f"❌ Error loading JSON: {e}")
                all_products = products.get_all_products()
            
            products_list = "\n".join([
                f"- {p.name}: {format_price(p.price)}/{p.unit}"
                for p in all_products
            ])
            
            ai_response = f"""Dạ, đây là menu của shop:

{products_list}

Anh/chị muốn đặt món nào ạ?"""
            
            context.add_message("user", user_message)
            context.add_message("assistant", ai_response)
            return ai_response
        
        # Normal chat
        system_prompt = """Bạn là trợ lý AI thông minh, thân thiện của cửa hàng.

NHIỆM VỤ:
- Trả lời câu hỏi của khách hàng
- Tư vấn sản phẩm khi được hỏi
- Hỗ trợ thanh toán khi khách muốn mua hàng

PHONG CÁCH:
- Ngắn gọn, trọng tâm (1-2 câu)
- Thân thiện, lịch sự

Trả lời bằng tiếng Việt."""

        messages = [
            {"role": "system", "content": system_prompt}
        ] + conversation_history + [
            {"role": "user", "content": user_message}
        ]
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=100
        )
        
        ai_response = response.choices[0].message.content
        context.add_message("user", user_message)
        context.add_message("assistant", ai_response)
        return ai_response
        
    except Exception as e:
        print(f"Lỗi chat: {e}")
        return "Xin lỗi, tôi không thể trả lời ngay bây giờ."

# ============================================================
# TEXT TO SPEECH
# ============================================================

async def text_to_speech(text):
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text,
            response_format="pcm",
            speed=1.0
        )
        return response.content
    except Exception as e:
        print(f"Lỗi TTS: {e}")
        return None

def pcm_to_int16_samples(pcm_data, sample_rate=24000):
    return pcm_data

# ============================================================
# WEBSOCKET HANDLERS
# ============================================================

async def handle_websocket(websocket):
    print(f"Client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            if isinstance(message, bytes):
                await handle_audio_message(websocket, message)
            else:
                await handle_text_message(websocket, message)
    except websockets.exceptions.ConnectionClosed:
        print(f"Client disconnected: {websocket.remote_address}")
    except Exception as e:
        print(f"Lỗi websocket: {e}")

async def handle_audio_message(websocket, data):
    try:
        mac_address, msg_type, msg_id, audio_data = parse_message(data)
        print(f"Nhận message: type={msg_type}, id={msg_id}, mac={mac_address}, data_len={len(audio_data)}")

        if msg_type == "START":
            session = AudioSession(msg_id, mac_address)
            active_sessions[msg_id] = session
            ack_message = create_message(mac_address, "START", msg_id, b'')
            await websocket.send(ack_message)
            print(f"Session started: {msg_id}")
            
        elif msg_type == "PROCESSING":
            if msg_id in active_sessions:
                session = active_sessions[msg_id]
                session.add_audio_chunk(audio_data)
                print(f"Received audio chunk: {len(audio_data)} bytes")
            else:
                print(f"Session không tồn tại: {msg_id}")
                
        elif msg_type == "END":
            if msg_id in active_sessions:
                session = active_sessions[msg_id]
                wav_bytes = session.get_wav_bytes()
                user_text = await transcribe_audio(wav_bytes)
                
                if user_text:
                    print(f"Transcribed: {user_text}")
                    text_response = {'type': 'transcription', 'message': user_text}
                    await websocket.send(json.dumps(text_response))
                    
                    ai_text = await get_ai_response(user_text, mac_address)
                    print(f"AI Response: {ai_text}")
                    
                    async def send_text_response():
                        ai_text_response = {'type': 'chat_response', 'message': ai_text}
                        await websocket.send(json.dumps(ai_text_response))
                    
                    async def process_and_send_audio():
                        ai_audio = await text_to_speech(ai_text)
                        if ai_audio:
                            response_id = str(uuid.uuid4())
                            print(f"Sending audio response: session_id={response_id}, size={len(ai_audio)} bytes")
                            start_msg = create_message(mac_address, "START", response_id, b'')
                            await websocket.send(start_msg)
                            print(f"Sent START message")
                            
                            chunk_size = 8192
                            audio_samples = pcm_to_int16_samples(ai_audio)
                            for i in range(0, len(audio_samples), chunk_size):
                                chunk = audio_samples[i:i+chunk_size]
                                processing_msg = create_message(mac_address, "PROCESSING", response_id, chunk)
                                await websocket.send(processing_msg)
                                await asyncio.sleep(0.01)
                            
                            end_msg = create_message(mac_address, "END", response_id, b'')
                            await websocket.send(end_msg)
                    
                    await asyncio.gather(send_text_response(), process_and_send_audio())
                
                ack_message = create_message(mac_address, "END", msg_id, b'')
                await websocket.send(ack_message)
                del active_sessions[msg_id]
                
    except Exception as e:
        print(f"Lỗi audio message: {e}")

async def handle_text_message(websocket, message):
    try:
        data = json.loads(message)
        msg_type = data.get('type')
        
        if msg_type == 'chat':
            user_message = data.get('message', '')
            mac_address = data.get('mac_address', 'web-client')
            ai_response = await get_ai_response(user_message, mac_address)
            
            async def send_text():
                response = {'type': 'chat_response', 'message': ai_response}
                await websocket.send(json.dumps(response))
            
            async def send_voice():
                if not data.get('voice_output', False):
                    return
                ai_audio = await text_to_speech(ai_response)
                if ai_audio:
                    mac_address = data.get('mac_address', 'web-client')
                    response_id = str(uuid.uuid4())
                    await websocket.send(create_message(mac_address, "START", response_id, b''))
                    
                    chunk_size = 8192
                    audio_samples = pcm_to_int16_samples(ai_audio)
                    for i in range(0, len(audio_samples), chunk_size):
                        chunk = audio_samples[i:i+chunk_size]
                        processing_msg = create_message(mac_address, "PROCESSING", response_id, chunk)
                        await websocket.send(processing_msg)
                        await asyncio.sleep(0.01)
                    
                    await websocket.send(create_message(mac_address, "END", response_id, b''))
            
            await asyncio.gather(send_text(), send_voice())
                    
    except Exception as e:
        print(f"Lỗi text message: {e}")

# ============================================================
# MAIN FUNCTION
# ============================================================

async def main():
    print("=" * 60)
    print("🚀 VOICE AI ASSISTANT + QR PAYMENT SYSTEM v2.0")
    print("=" * 60)
    print("\n📡 Server Configuration:")
    print("  - WebSocket: ws://0.0.0.0:8765")
    print("  - Local: ws://localhost:8765")
    print("  - Network: ws://<YOUR_IP>:8765")
    
    # Initialize MQTT
    print("\n📡 Initializing MQTT...")
    mac_address = os.getenv("MQTT_MAC_ADDRESS", "DC:B4:D9:13:55:C8")
    mqtt_ok = init_mqtt(mac_address)
    if mqtt_ok:
        print(f"  ✅ MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        print("  ✅ Topic Pattern: CASSOROBOT<MAC>/qr")
        print("  ⚠️  MAC format: WITH colons (DC:B4:D9:13:55:C8)")
    else:
        print("  ⚠️  MQTT initialization failed - QR display won't work")
    
    print("\n✅ DYNAMIC PRODUCT MANAGEMENT:")
    print("  📝 Add: 'thêm món [tên] giá [số]'")
    print("  🗑️  Remove: 'xóa món [tên]'")
    print("  💰 Update: 'cập nhật giá [tên] thành [số]'")
    
    print("\n💳 QR PAYMENT SYSTEM:")
    print(f"  Bank: {VIETQR_ACCOUNT['accountName']}")
    print(f"  Account: {VIETQR_ACCOUNT['accountNo']}")
    print("  QR Delivery: MQTT")
    print("  ✅ TIMING FIX: QR sent BEFORE TTS audio")
    
    print("\n💾 Data Storage:")
    print("  - custom_products.json (Product database)")
    print("  - Conversation contexts (In-memory)")
    
    print("=" * 60)
    print("\n✅ Server running and ready for connections!\n")
    
    async with websockets.serve(handle_websocket, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
