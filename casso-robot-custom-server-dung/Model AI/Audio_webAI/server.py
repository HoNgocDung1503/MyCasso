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

# Helper để reload products module
def reload_products_module():
    """Reload products module to get latest code"""
    global products
    products = importlib.reload(products)
    print("🔄 Products module reloaded!")
    return products

# Convenience accessors
process_payment_request = lambda msg: products.process_payment_request(msg)
get_all_products = lambda: products.get_all_products()
search_products = lambda q: products.search_products(q)
format_price = lambda p: products.format_price(p)

# Load environment variables từ file .env
load_dotenv()

# Khởi tạo OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

# Lưu trữ sessions
active_sessions = {}

# Lưu trữ conversation contexts theo MAC address
conversation_contexts = {}

class ConversationContext:
    """Lưu trữ context của conversation cho mỗi user (theo MAC address)"""
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.conversation_history = []  # Lịch sử chat OpenAI format
        self.pending_payment = None  # Thông tin đơn hàng đang chờ xác nhận
        self.last_interaction = datetime.now()
        
    def add_message(self, role, content):
        """Thêm message vào conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content
        })
        # Giới hạn history (chỉ giữ 10 messages gần nhất)
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
        """Reset conversation (timeout hoặc user yêu cầu)"""
        self.conversation_history = []
        self.pending_payment = None
        self.last_interaction = datetime.now()

class AudioSession:
    def __init__(self, session_id, mac_address):
        self.session_id = session_id
        self.mac_address = mac_address
        self.audio_buffer = bytearray()
        self.sample_rate = 24000
        self.channels = 1
        self.created_at = datetime.now()
        
    def add_audio_chunk(self, audio_data):
        """Thêm audio chunk vào buffer"""
        self.audio_buffer.extend(audio_data)
        
    def get_wav_bytes(self):
        """Chuyển audio buffer thành WAV format"""
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(bytes(self.audio_buffer))
        return wav_buffer.getvalue()
    
    def clear_buffer(self):
        """Xóa audio buffer"""
        self.audio_buffer = bytearray()

def encode_length_string(text):
    """Encode string với 2 bytes length prefix (big-endian)"""
    text_bytes = text.encode('utf-8')
    length = len(text_bytes)
    return struct.pack('>H', length) + text_bytes

def decode_length_string(data, offset):
    """Decode string với 2 bytes length prefix"""
    length = struct.unpack('>H', data[offset:offset+2])[0]
    text = data[offset+2:offset+2+length].decode('utf-8')
    return text, offset + 2 + length

def create_message(mac_address, msg_type, msg_id, data=b''):
    """
    Tạo message theo Audio Message Wire Protocol
    Format: macAddress → type → id → data
    """
    message = bytearray()
    
    # 1. macAddress (variable length)
    message.extend(encode_length_string(mac_address))
    
    # 2. type (variable length)
    message.extend(encode_length_string(msg_type))
    
    # 3. id (variable length)
    message.extend(encode_length_string(msg_id))
    
    # 4. data length (4 bytes, big-endian) + data
    message.extend(struct.pack('>I', len(data)))
    message.extend(data)
    
    return bytes(message)

def parse_message(data):
    """
    Parse message theo Audio Message Wire Protocol
    Returns: (mac_address, msg_type, msg_id, audio_data)
    """
    offset = 0
    
    # Parse macAddress
    mac_address, offset = decode_length_string(data, offset)
    
    # Parse type
    msg_type, offset = decode_length_string(data, offset)
    
    # Parse id
    msg_id, offset = decode_length_string(data, offset)
    
    # Parse data
    data_length = struct.unpack('>I', data[offset:offset+4])[0]
    offset += 4
    audio_data = data[offset:offset+data_length] if data_length > 0 else b''
    
    return mac_address, msg_type, msg_id, audio_data

def get_or_create_context(mac_address):
    """Lấy hoặc tạo mới conversation context cho MAC address"""
    if mac_address not in conversation_contexts:
        conversation_contexts[mac_address] = ConversationContext(mac_address)
    
    context = conversation_contexts[mac_address]
    
    # Auto-reset nếu timeout (5 phút không tương tác)
    time_diff = (datetime.now() - context.last_interaction).total_seconds()
    if time_diff > 300:  # 5 phút
        print(f"🔄 Context timeout for {mac_address}, resetting...")
        context.reset()
    
    return context

def generate_qr_code_data(payment_data):
    """
    Tạo dữ liệu QR code cho thanh toán
    Format: JSON với thông tin đơn hàng
    """
    import hashlib
    
    # Tạo order ID unique
    order_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8].upper()
    
    qr_data = {
        "order_id": order_id,
        "total_amount": payment_data['total_amount'],
        "currency": "VND",
        "items": payment_data['items'],
        "timestamp": datetime.now().isoformat()
    }
    
    return json.dumps(qr_data, ensure_ascii=False)

async def transcribe_audio(audio_bytes):
    """Chuyển audio thành text bằng OpenAI Whisper"""
    try:
        # Lưu tạm audio
        temp_file = f"temp_audio_{uuid.uuid4()}.wav"
        with open(temp_file, 'wb') as f:
            f.write(audio_bytes)
        
        # Gọi Whisper API
        with open(temp_file, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="vi"
            )
        
        # Xóa file tạm
        os.remove(temp_file)
        
        return transcript.text
    except Exception as e:
        print(f"Lỗi transcribe audio: {e}")
        return None

async def get_ai_response(user_message, mac_address, conversation_history=None):
    """Lấy response từ OpenAI GPT - Có context awareness"""
    try:
        # Lấy conversation context
        context = get_or_create_context(mac_address)
        
        # ✅ KIỂM TRA XÁC NHẬN ĐỐI VỚI PENDING PAYMENT
        confirmation_keywords = [
            "oke", "ok", "okay", "được", "đồng ý", "xác nhận", 
            "chấp nhận", "đúng rồi", "vâng", "dạ"
        ]
        
        # ✅ SMARTER CONFIRMATION DETECTION
        message_lower = user_message.lower().strip()
        word_count = len(message_lower.split())
        
        # Detect questions (câu hỏi) - KHÔNG phải confirmation/cancellation
        is_question = any(q in message_lower for q in [
            "không?", "chưa?", "sao", "gì", "nào", "đâu", 
            "bao nhiêu", "có bán", "có không", "bán không"
        ])
        
        # Confirmation: Câu ngắn + match keyword + KHÔNG phải câu hỏi
        is_confirmation = (
            word_count <= 10 and 
            not is_question and
            any(keyword in message_lower for keyword in confirmation_keywords)
        )
        
        # ✅ SMARTER CANCELLATION DETECTION
        # CHỈ hủy nếu: có từ hủy rõ ràng + KHÔNG phải câu hỏi
        cancellation_phrases = [
            "không lấy", "không mua", "thôi không", "hủy đơn", 
            "cancel", "đổi ý", "thôi ạ", "thôi em"
        ]
        
        # Cancellation: Match cụm từ hủy + KHÔNG phải câu hỏi
        is_cancellation = (
            not is_question and
            any(phrase in message_lower for phrase in cancellation_phrases)
        )
        
        # Nếu có pending payment và user xác nhận
        if context.pending_payment and is_confirmation:
            print(f"✅ Payment confirmed for MAC {mac_address}")
            
            # Generate QR code data
            qr_data = generate_qr_code_data(context.pending_payment)
            
            # Response
            response_text = f"""Cảm ơn anh/chị! Đơn hàng đã được xác nhận.

Tổng tiền: {format_price(context.pending_payment['total_amount'])}

Đây là mã QR để thanh toán. Vui lòng quét mã để hoàn tất."""
            
            # Lưu vào conversation history
            context.add_message("user", user_message)
            context.add_message("assistant", response_text)
            
            # Clear pending payment
            context.clear_pending_payment()
            
            # TODO: Gửi QR code về client (có thể thêm vào response)
            
            return response_text
        
        # Nếu có pending payment và user hủy
        elif context.pending_payment and is_cancellation:
            print(f"❌ Payment cancelled for MAC {mac_address}")
            
            response_text = "Dạ, tôi đã hủy đơn hàng. Anh/chị cần gì thêm không ạ?"
            
            context.add_message("user", user_message)
            context.add_message("assistant", response_text)
            context.clear_pending_payment()
            
            return response_text
        
        # ✅ NẾU CÓ PENDING PAYMENT VÀ USER HỎI THÊM SẢN PHẨM KHÁC
        # → Xử lý như product inquiry thay vì hủy/xác nhận
        elif context.pending_payment and is_question:
            print(f"🤔 User asking about products while having pending payment: {mac_address}")
            # Để logic chạy tiếp xuống phần product inquiry hoặc payment request
            pass
        
        # ✅ CHECK MENU REQUEST TRƯỚC (ưu tiên cao hơn payment)
        menu_keywords = [
            "menu", "thực đơn", "món gì", "bán gì", "có gì", 
            "sản phẩm gì", "bán những gì", "những món", "danh sách",
            "xem menu", "cho xem", "xin menu"
        ]
        is_menu_request = any(keyword in user_message.lower() for keyword in menu_keywords)
        
        if is_menu_request:
            # User muốn xem menu → Chuyển sang handle_normal_chat để xử lý
            return await handle_normal_chat(user_message, mac_address, context.conversation_history)
        
        # ✅ DETECT PAYMENT INTENT - Kiểm tra xem có phải yêu cầu thanh toán không
        payment_keywords = [
            "mua", "đặt", "order", 
            "thanh toán", "thành toán",  # Whisper hay transcribe sai
            "tính tiền", "bao nhiêu tiền", "bao nhiêu",
            "giá", "cho tôi", "lấy", "gọi"
        ]
        
        # ✅ DETECT "THÊM MÓN" KEYWORDS
        add_more_keywords = ["thêm", "nữa", "thêm nữa", "cộng thêm", "tính thêm"]
        is_adding_more = any(keyword in user_message.lower() for keyword in add_more_keywords)
        
        is_payment_request = any(keyword in user_message.lower() for keyword in payment_keywords)
        
        # ✅ NẾU CÓ PENDING PAYMENT VÀ USER MUỐN THÊM MÓN
        if context.pending_payment and is_adding_more:
            print(f"➕ User wants to add more items to pending order: {mac_address}")
            return await handle_add_to_order(user_message, mac_address, context.pending_payment)
        
        if is_payment_request:
            # ✅ XỬ LÝ THANH TOÁN VỚI STRUCTURED RESPONSE
            return await handle_payment_request(user_message, mac_address)
        else:
            # ✅ XỬ LÝ CHAT THÔNG THƯỜNG (với conversation history)
            return await handle_normal_chat(user_message, mac_address, context.conversation_history)
            
    except Exception as e:
        print(f"Lỗi get AI response: {e}")
        return "Xin lỗi, tôi không thể trả lời ngay bây giờ."

async def handle_payment_request(user_message: str, mac_address: str) -> str:
    """
    Xử lý yêu cầu thanh toán với OpenAI Structured Outputs
    Sử dụng system prompt chuyên biệt cho thanh toán
    """
    try:
        # Lấy conversation context
        context = get_or_create_context(mac_address)
        
        # ✅ BƯỚC 1: Lấy thông tin sản phẩm từ database
        print(f"\n🔍 DEBUG: Processing payment for: '{user_message}'")
        payment_result = process_payment_request(user_message)
        print(f"🔍 DEBUG: Payment result success={payment_result['success']}, items={len(payment_result['items'])}")
        
        if not payment_result['success']:
            # Không tìm thấy sản phẩm -> Hỏi lại user hoặc gợi ý
            products_list = get_all_products()
            available_products = "\n".join([
                f"- {p.name}: {format_price(p.price)}/{p.unit}" 
                for p in products_list[:10]  # Top 10 sản phẩm
            ])
            
            response_text = f"""Xin lỗi, tôi không tìm thấy sản phẩm trong yêu cầu của bạn.

📋 Một số sản phẩm có sẵn:
{available_products}

Bạn muốn mua gì ạ?"""
            
            # Lưu vào history
            context.add_message("user", user_message)
            context.add_message("assistant", response_text)
            
            return response_text
        
        # ✅ BƯỚC 2: Lưu pending payment vào context
        context.set_pending_payment(payment_result)
        
        # ✅ BƯỚC 3: Sử dụng OpenAI để format response tự nhiên hơn
        # System prompt chuyên biệt cho thanh toán
        system_prompt = """Bạn là nhân viên thanh toán thông minh và thân thiện.

NHIỆM VỤ:
- Xác nhận đơn hàng của khách một cách rõ ràng, lịch sự
- Đọc từng món và số lượng
- Thông báo tổng tiền cuối cùng
- Hỏi khách xác nhận đơn hàng

PHONG CÁCH:
- Ngắn gọn, chuyên nghiệp
- Thân thiện, lịch sự
- Đọc rõ ràng từng món và giá

CÁCH TRẢ LỜI:
Dạ, cho em xác nhận đơn hàng:
[liệt kê từng món + số lượng + giá]
Tổng cộng: [tổng tiền]

Anh/chị xác nhận đơn hàng này nhé?"""

        # Chuẩn bị thông tin đơn hàng
        order_summary = []
        for item in payment_result['items']:
            order_summary.append(
                f"{item['quantity']} {item['unit']} {item['product_name']} - {format_price(item['subtotal'])}"
            )
        
        order_text = "\n".join(order_summary)
        total_text = format_price(payment_result['total_amount'])
        
        user_prompt = f"""Khách hàng đặt:
{order_text}

Tổng tiền: {total_text}

Hãy xác nhận đơn hàng theo phong cách chuyên nghiệp."""

        # ✅ Call OpenAI với system prompt
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=200
        )
        
        ai_response = response.choices[0].message.content
        
        # ✅ Lưu vào conversation history
        context.add_message("user", user_message)
        context.add_message("assistant", ai_response)
        
        # ✅ Log payment info
        print(f"\n💰 PAYMENT REQUEST")
        print(f"   User: {user_message}")
        print(f"   Items: {len(payment_result['items'])}")
        print(f"   Total: {total_text}")
        print(f"   AI Response: {ai_response[:100]}...")
        print(f"   ⏳ Pending confirmation...")
        
        return ai_response
        
    except Exception as e:
        print(f"Lỗi xử lý thanh toán: {e}")
        import traceback
        traceback.print_exc()
        return "Xin lỗi, có lỗi xảy ra khi xử lý đơn hàng. Vui lòng thử lại."

async def handle_add_to_order(user_message: str, mac_address: str, existing_payment: dict) -> str:
    """
    Xử lý thêm món vào đơn hàng đang pending
    """
    try:
        context = get_or_create_context(mac_address)
        
        print(f"\n➕ DEBUG: Adding items to existing order: '{user_message}'")
        
        # Parse món mới từ user message
        new_items_result = process_payment_request(user_message)
        
        if not new_items_result['success']:
            return "Xin lỗi, tôi không hiểu món bạn muốn thêm. Vui lòng nói rõ hơn."
        
        # ✅ MERGE items: Đơn cũ + Món mới
        merged_items = existing_payment['items'].copy()
        
        for new_item in new_items_result['items']:
            # Check xem món đã có trong đơn chưa
            found = False
            for existing_item in merged_items:
                if existing_item['product_id'] == new_item['product_id']:
                    # Món đã có → Cộng dồn số lượng
                    existing_item['quantity'] += new_item['quantity']
                    existing_item['subtotal'] += new_item['subtotal']
                    found = True
                    break
            
            if not found:
                # Món mới → Thêm vào list
                merged_items.append(new_item)
        
        # Tính tổng tiền mới
        new_total = sum(item['subtotal'] for item in merged_items)
        
        # ✅ Update pending payment
        updated_payment = {
            'success': True,
            'total_amount': new_total,
            'items': merged_items,
            'currency': 'VND'
        }
        
        context.set_pending_payment(updated_payment)
        
        # ✅ Format response
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
        
        # Lưu vào history
        context.add_message("user", user_message)
        context.add_message("assistant", ai_response)
        
        print(f"✅ Order updated: {len(merged_items)} items, Total: {total_text}")
        
        return ai_response
        
    except Exception as e:
        print(f"Lỗi thêm món: {e}")
        import traceback
        traceback.print_exc()
        return "Xin lỗi, có lỗi khi thêm món. Vui lòng thử lại."

async def handle_normal_chat(user_message: str, mac_address: str, conversation_history: list) -> str:
    """
    Xử lý chat thông thường với system prompt mặc định
    """
    try:
        # Lấy context
        context = get_or_create_context(mac_address)
        
        # ✅ KIỂM TRA XEM USER CÓ HỎI VỀ SẢN PHẨM KHÔNG
        product_inquiry_keywords = [
            "có", "bán", "có bán", "có không", "bao nhiêu",
            "giá", "giá bao nhiêu", "menu", "món gì", 
            "món ăn", "đồ uống", "sản phẩm"
        ]
        
        # ✅ CHECK XEM CÓ PHẢI HỎI MENU TỔNG QUÁT KHÔNG
        menu_keywords = [
            "menu", "thực đơn", "món gì", "bán gì", "có gì", 
            "sản phẩm gì", "bán những gì", "những món", "danh sách"
        ]
        is_asking_menu = any(keyword in user_message.lower() for keyword in menu_keywords)
        
        # Nếu hỏi menu tổng quát → Hiển thị tất cả
        if is_asking_menu:
            print(f"📋 User asking for full menu: {user_message}")
            
            all_products = get_all_products()
            products_list = "\n".join([
                f"- {p.name}: {format_price(p.price)}/{p.unit}"
                for p in all_products[:15]  # Top 15 sản phẩm
            ])
            
            ai_response = f"""Dạ, đây là menu của shop:

{products_list}

Anh/chị muốn đặt món nào ạ?"""
            
            context.add_message("user", user_message)
            context.add_message("assistant", ai_response)
            
            return ai_response
        
        is_product_inquiry = any(keyword in user_message.lower() for keyword in product_inquiry_keywords)
        
        if is_product_inquiry:
            # ✅ SEARCH DATABASE để tìm sản phẩm
            # Trích xuất từ khóa sản phẩm từ câu hỏi
            words = user_message.lower().split()
            found_products = []
            
            # Loại bỏ stop words
            stop_words = {"có", "bán", "không", "giá", "bao", "nhiêu", "của", "cửa", "hàng", "shop", "ạ", "à", "thì"}
            
            # Tìm trong database với từ khóa quan trọng
            important_words = [w for w in words if w not in stop_words and len(w) > 2]
            
            # Ưu tiên tìm cụm từ (2-3 words) trước
            for i in range(len(important_words) - 1, 0, -1):
                for j in range(len(important_words) - i + 1):
                    phrase = " ".join(important_words[j:j+i+1])
                    products_found = search_products(phrase)
                    for p in products_found:
                        if p not in found_products:
                            found_products.append(p)
            
            # Nếu chưa tìm thấy, tìm từng từ đơn
            if not found_products:
                for word in important_words:
                    products_found = search_products(word)
                    for p in products_found:
                        if p not in found_products:
                            found_products.append(p)
            
            # Nếu tìm thấy sản phẩm → Trả lời có
            if found_products:
                print(f"🔍 Found {len(found_products)} products for inquiry: {user_message}")
                
                # Format danh sách sản phẩm
                products_list = "\n".join([
                    f"- {p.name}: {format_price(p.price)}/{p.unit}"
                    for p in found_products[:5]  # Max 5 sản phẩm
                ])
                
                if len(found_products) == 1:
                    # Chỉ 1 sản phẩm → Trả lời ngắn gọn
                    p = found_products[0]
                    ai_response = f"Dạ có ạ! {p.name} giá {format_price(p.price)}/{p.unit}. Anh/chị muốn đặt không ạ?"
                else:
                    # Nhiều sản phẩm → Liệt kê
                    ai_response = f"Dạ có ạ! Shop có các món:\n{products_list}\n\nAnh/chị muốn đặt món nào ạ?"
                
                # Lưu vào history
                context.add_message("user", user_message)
                context.add_message("assistant", ai_response)
                
                return ai_response
            else:
                # ✅ KHÔNG TÌM THẤY SẢN PHẨM → Trả lời không có
                print(f"❌ No products found for inquiry: {user_message}")
                
                # Gợi ý một số sản phẩm có sẵn
                all_products = get_all_products()
                suggestions = "\n".join([
                    f"- {p.name}: {format_price(p.price)}/{p.unit}"
                    for p in all_products[:8]  # Top 8 sản phẩm
                ])
                
                ai_response = f"""Xin lỗi, shop hiện chưa có món đó ạ.

📋 Một số món shop có sẵn:
{suggestions}

Anh/chị muốn thử món nào không ạ?"""
                
                # Lưu vào history
                context.add_message("user", user_message)
                context.add_message("assistant", ai_response)
                
                return ai_response
        
        # ✅ NORMAL CHAT (không phải hỏi sản phẩm cụ thể)
        system_prompt = """Bạn là trợ lý AI thông minh, thân thiện của cửa hàng.

NHIỆM VỤ:
- Trả lời câu hỏi của khách hàng
- Tư vấn sản phẩm khi được hỏi
- Hỗ trợ thanh toán khi khách muốn mua hàng
- Giải đáp thắc mắc

PHONG CÁCH:
- Ngắn gọn, trọng tâm (1-2 câu)
- Thân thiện, lịch sự
- Nhanh chóng, chính xác

QUAN TRỌNG:
- KHÔNG TỰ Ý suy đoán về sản phẩm
- Nếu không chắc chắn, hãy gợi ý khách hỏi cụ thể hơn

Trả lời bằng tiếng Việt."""

        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ] + conversation_history + [
            {
                "role": "user",
                "content": user_message
            }
        ]
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=100
        )
        
        ai_response = response.choices[0].message.content
        
        # ✅ Lưu vào conversation history
        context.add_message("user", user_message)
        context.add_message("assistant", ai_response)
        
        return ai_response
        
    except Exception as e:
        print(f"Lỗi chat thông thường: {e}")
        return "Xin lỗi, tôi không thể trả lời ngay bây giờ."

async def text_to_speech(text):
    """Chuyển text thành audio bằng OpenAI TTS - Tối ưu cho realtime"""
    try:
        response = client.audio.speech.create(
            model="tts-1",  # tts-1 nhanh hơn tts-1-hd (~2x speed)
            voice="nova",
            input=text,
            response_format="pcm",  # PCM format, 24kHz, 16-bit, mono, little-endian
            speed=1.1  # Tăng tốc độ đọc 10% - vừa đủ nhanh mà không mất tự nhiên
        )
        
        # Đọc audio data
        audio_data = response.content
        print(f"TTS generated: {len(audio_data)} bytes PCM audio")
        
        return audio_data
    except Exception as e:
        print(f"Lỗi TTS: {e}")
        return None

def pcm_to_int16_samples(pcm_data, sample_rate=24000):
    """
    Chuyển PCM data thành int16 samples (little-endian per sample)
    OpenAI TTS trả về PCM 24kHz, 16-bit, mono
    """
    # PCM data đã là int16 little-endian từ OpenAI
    # Chỉ cần đảm bảo format đúng
    return pcm_data

async def handle_websocket(websocket):
    """Xử lý WebSocket connection"""
    print(f"Client connected: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            if isinstance(message, bytes):
                # Binary message - Audio protocol
                await handle_audio_message(websocket, message)
            else:
                # Text message - JSON protocol
                await handle_text_message(websocket, message)
                
    except websockets.exceptions.ConnectionClosed:
        print(f"Client disconnected: {websocket.remote_address}")
    except Exception as e:
        print(f"Lỗi xử lý websocket: {e}")
        import traceback
        traceback.print_exc()

async def handle_audio_message(websocket, data):
    """Xử lý audio message theo Wire Protocol"""
    try:
        # Parse message
        mac_address, msg_type, msg_id, audio_data = parse_message(data)
        
        print(f"Nhận message: type={msg_type}, id={msg_id}, mac={mac_address}, data_len={len(audio_data)}")
        
        if msg_type == "START":
            # Bắt đầu session mới
            session = AudioSession(msg_id, mac_address)
            active_sessions[msg_id] = session
            
            # Gửi START acknowledgment
            ack_message = create_message(mac_address, "START", msg_id, b'')
            await websocket.send(ack_message)
            print(f"Session started: {msg_id}")
            
        elif msg_type == "PROCESSING":
            # Nhận audio chunks
            if msg_id in active_sessions:
                session = active_sessions[msg_id]
                session.add_audio_chunk(audio_data)
                print(f"Received audio chunk: {len(audio_data)} bytes")
            else:
                print(f"Session không tồn tại: {msg_id}")
                
        elif msg_type == "END":
            # Kết thúc session, xử lý audio
            if msg_id in active_sessions:
                session = active_sessions[msg_id]
                
                # 1. Transcribe audio
                wav_bytes = session.get_wav_bytes()
                user_text = await transcribe_audio(wav_bytes)
                
                if user_text:
                    print(f"Transcribed: {user_text}")
                    
                    # Gửi transcribed text về client (để hiển thị tin nhắn user)
                    text_response = {
                        'type': 'transcription',
                        'message': user_text
                    }
                    await websocket.send(json.dumps(text_response))
                    
                    # 2. Lấy AI response (với MAC address để track conversation)
                    ai_text = await get_ai_response(user_text, mac_address)
                    print(f"AI Response: {ai_text}")
                    
                    # ✅ XỬ LÝ SONG SONG: Gửi text và bắt đầu TTS cùng lúc
                    # Tạo tasks song song thay vì chờ tuần tự
                    async def send_text_response():
                        ai_text_response = {
                            'type': 'chat_response',
                            'message': ai_text
                        }
                        await websocket.send(json.dumps(ai_text_response))
                    
                    async def process_and_send_audio():
                        # 3. Convert to speech
                        ai_audio = await text_to_speech(ai_text)
                        
                        if ai_audio:
                            # 4. Gửi response về client
                            response_id = str(uuid.uuid4())
                            
                            print(f"Sending audio response: session_id={response_id}, size={len(ai_audio)} bytes")
                            
                            # Gửi START response
                            start_msg = create_message(mac_address, "START", response_id, b'')
                            await websocket.send(start_msg)
                            print(f"Sent START message")
                            
                            # Gửi audio chunks (chia nhỏ thành chunks 8KB)
                            chunk_size = 8192  # Tăng từ 4KB → 8KB để giảm overhead
                            audio_samples = pcm_to_int16_samples(ai_audio)
                            
                            chunk_count = 0
                            for i in range(0, len(audio_samples), chunk_size):
                                chunk = audio_samples[i:i+chunk_size]
                                processing_msg = create_message(mac_address, "PROCESSING", response_id, chunk)
                                await websocket.send(processing_msg)
                                chunk_count += 1
                                await asyncio.sleep(0.005)  # Giảm từ 0.03s → 0.005s để gửi nhanh hơn
                            
                            print(f"Sent {chunk_count} PROCESSING chunks")
                            
                            # Gửi END response
                            end_msg = create_message(mac_address, "END", response_id, b'')
                            await websocket.send(end_msg)
                            print(f"Sent END message")
                            
                            print(f"Complete audio response sent: {len(audio_samples)} bytes total")
                    
                    # Chạy cả 2 tasks song song (text gửi trước, audio xử lý ngay)
                    await asyncio.gather(
                        send_text_response(),
                        process_and_send_audio()
                    )
                
                # Gửi END acknowledgment
                ack_message = create_message(mac_address, "END", msg_id, b'')
                await websocket.send(ack_message)
                
                # Xóa session
                del active_sessions[msg_id]
                print(f"Session ended: {msg_id}")
            else:
                print(f"Session không tồn tại: {msg_id}")
                
    except Exception as e:
        print(f"Lỗi xử lý audio message: {e}")
        import traceback
        traceback.print_exc()

async def handle_text_message(websocket, message):
    """Xử lý text message (JSON)"""
    try:
        data = json.loads(message)
        msg_type = data.get('type')
        
        if msg_type == 'chat':
            # Chat text message
            user_message = data.get('message', '')
            mac_address = data.get('mac_address', 'web-client')
            
            # Lấy AI response (với MAC address)
            ai_response = await get_ai_response(user_message, mac_address)
            
            # ✅ XỬ LÝ SONG SONG: Gửi text và TTS cùng lúc
            async def send_text():
                response = {
                    'type': 'chat_response',
                    'message': ai_response
                }
                await websocket.send(json.dumps(response))
            
            async def send_voice():
                if not data.get('voice_output', False):
                    return
                    
                ai_audio = await text_to_speech(ai_response)
                if ai_audio:
                    # Gửi audio qua binary protocol
                    mac_address = data.get('mac_address', 'web-client')
                    response_id = str(uuid.uuid4())
                    
                    print(f"Sending voice response: session_id={response_id}, size={len(ai_audio)} bytes")
                    
                    # START
                    await websocket.send(create_message(mac_address, "START", response_id, b''))
                    
                    # PROCESSING chunks
                    chunk_size = 8192  # Tăng từ 4KB → 8KB để giảm overhead
                    audio_samples = pcm_to_int16_samples(ai_audio)
                    chunk_count = 0
                    for i in range(0, len(audio_samples), chunk_size):
                        chunk = audio_samples[i:i+chunk_size]
                        processing_msg = create_message(mac_address, "PROCESSING", response_id, chunk)
                        await websocket.send(processing_msg)
                        chunk_count += 1
                        await asyncio.sleep(0.005)  # Giảm từ 0.03s → 0.005s để gửi nhanh hơn
                    
                    print(f"Sent {chunk_count} audio chunks")
                    
                    # END
                    await websocket.send(create_message(mac_address, "END", response_id, b''))
                    print(f"Voice response complete")
            
            # Chạy song song text và voice
            await asyncio.gather(send_text(), send_voice())
                    
    except Exception as e:
        print(f"Lỗi xử lý text message: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main server"""
    print("Starting WebSocket server on ws://0.0.0.0:8765")
    print("Server accessible at:")
    print("  - ws://localhost:8765 (local browser)")
    print("  - ws://192.168.1.185:8765 (ESP32 and other devices)")
    print("\nĐảm bảo đã set OPENAI_API_KEY trong environment variables")
    
    async with websockets.serve(handle_websocket, "0.0.0.0", 8765):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())