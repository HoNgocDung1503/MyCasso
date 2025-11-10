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

# Load environment variables từ file .env
load_dotenv()

# Khởi tạo OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

# Lưu trữ sessions
active_sessions = {}

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

async def get_ai_response(user_message, conversation_history=None):
    """Lấy response từ OpenAI GPT"""
    try:
        if conversation_history is None:
            conversation_history = []
            
        messages = [
            {
                "role": "system",
                "content": "Bạn là một trợ lý AI thông minh và thân thiện. Hãy trả lời bằng tiếng Việt một cách tự nhiên, ngắn gọn và hữu ích."
            }
        ] + conversation_history + [
            {
                "role": "user",
                "content": user_message
            }
        ]
        
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"Lỗi get AI response: {e}")
        return "Xin lỗi, tôi không thể trả lời ngay bây giờ."

async def text_to_speech(text):
    """Chuyển text thành audio bằng OpenAI TTS"""
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text,
            response_format="pcm"  # PCM format, 24kHz, 16-bit, mono, little-endian
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
                    
                    # 2. Lấy AI response
                    ai_text = await get_ai_response(user_text)
                    print(f"AI Response: {ai_text}")
                    
                    # Gửi AI text response về client (để hiển thị tin nhắn AI)
                    ai_text_response = {
                        'type': 'chat_response',
                        'message': ai_text
                    }
                    await websocket.send(json.dumps(ai_text_response))
                    
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
                        
                        # Gửi audio chunks (chia nhỏ thành chunks 4KB)
                        chunk_size = 4096
                        audio_samples = pcm_to_int16_samples(ai_audio)
                        
                        chunk_count = 0
                        for i in range(0, len(audio_samples), chunk_size):
                            chunk = audio_samples[i:i+chunk_size]
                            processing_msg = create_message(mac_address, "PROCESSING", response_id, chunk)
                            await websocket.send(processing_msg)
                            chunk_count += 1
                            await asyncio.sleep(0.03)  # Giảm từ 0.05s → 0.03s (vừa đủ cho ESP32 có PSRAM)
                        
                        print(f"Sent {chunk_count} PROCESSING chunks")
                        
                        # Gửi END response
                        end_msg = create_message(mac_address, "END", response_id, b'')
                        await websocket.send(end_msg)
                        print(f"Sent END message")
                        
                        print(f"Complete audio response sent: {len(audio_samples)} bytes total")
                
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
            conversation_history = data.get('history', [])
            
            # Lấy AI response
            ai_response = await get_ai_response(user_message, conversation_history)
            
            # Gửi text response
            response = {
                'type': 'chat_response',
                'message': ai_response
            }
            await websocket.send(json.dumps(response))
            
            # Tạo audio response (optional)
            if data.get('voice_output', False):
                ai_audio = await text_to_speech(ai_response)
                if ai_audio:
                    # Gửi audio qua binary protocol
                    mac_address = data.get('mac_address', 'web-client')
                    response_id = str(uuid.uuid4())
                    
                    print(f"Sending voice response: session_id={response_id}, size={len(ai_audio)} bytes")
                    
                    # START
                    await websocket.send(create_message(mac_address, "START", response_id, b''))
                    
                    # PROCESSING chunks
                    chunk_size = 4096
                    audio_samples = pcm_to_int16_samples(ai_audio)
                    chunk_count = 0
                    for i in range(0, len(audio_samples), chunk_size):
                        chunk = audio_samples[i:i+chunk_size]
                        processing_msg = create_message(mac_address, "PROCESSING", response_id, chunk)
                        await websocket.send(processing_msg)
                        chunk_count += 1
                        await asyncio.sleep(0.03)  # Giảm từ 0.05s → 0.03s (ESP32 đã có PSRAM)
                    
                    print(f"Sent {chunk_count} audio chunks")
                    
                    # END
                    await websocket.send(create_message(mac_address, "END", response_id, b''))
                    print(f"Voice response complete")
                    
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
