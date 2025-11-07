"""
Test client cho Audio Message Wire Protocol
Dùng để test kết nối và giao thức trước khi dùng web client
"""

import asyncio
import websockets
import struct
import uuid

def encode_length_string(text):
    """Encode string với 2 bytes length prefix (big-endian)"""
    text_bytes = text.encode('utf-8')
    length = len(text_bytes)
    return struct.pack('>H', length) + text_bytes

def create_message(mac_address, msg_type, msg_id, data=b''):
    """Tạo message theo Audio Message Wire Protocol"""
    message = bytearray()
    
    # 1. macAddress
    message.extend(encode_length_string(mac_address))
    
    # 2. type
    message.extend(encode_length_string(msg_type))
    
    # 3. id
    message.extend(encode_length_string(msg_id))
    
    # 4. data
    message.extend(struct.pack('>I', len(data)))
    message.extend(data)
    
    return bytes(message)

async def test_text_chat():
    """Test text chat qua WebSocket"""
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket server")
            
            # Gửi text message
            message = {
                "type": "chat",
                "message": "Xin chào, bạn có khỏe không?",
                "history": [],
                "voice_output": False,
                "mac_address": "test-client-001"
            }
            
            import json
            await websocket.send(json.dumps(message))
            print(f"📤 Sent: {message['message']}")
            
            # Nhận response
            response = await websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get('type') == 'chat_response':
                print(f"📥 Received: {response_data['message']}")
            else:
                print(f"❓ Unknown response: {response_data}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

async def test_audio_protocol():
    """Test Audio Wire Protocol"""
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket server")
            
            mac_address = "test-client-002"
            session_id = str(uuid.uuid4())
            
            # 1. Gửi START
            start_msg = create_message(mac_address, "START", session_id, b'')
            await websocket.send(start_msg)
            print(f"📤 Sent START (id={session_id})")
            
            # Đợi START acknowledgment
            ack = await websocket.recv()
            print(f"📥 Received START acknowledgment")
            
            # 2. Gửi fake audio data (silence)
            # Tạo 1 giây audio silence (24000 samples * 2 bytes)
            fake_audio = b'\x00' * (24000 * 2)
            
            # Chia thành chunks 4KB
            chunk_size = 4096
            for i in range(0, len(fake_audio), chunk_size):
                chunk = fake_audio[i:i+chunk_size]
                proc_msg = create_message(mac_address, "PROCESSING", session_id, chunk)
                await websocket.send(proc_msg)
                print(f"📤 Sent PROCESSING chunk {i//chunk_size + 1} ({len(chunk)} bytes)")
                await asyncio.sleep(0.01)
            
            # 3. Gửi END
            end_msg = create_message(mac_address, "END", session_id, b'')
            await websocket.send(end_msg)
            print(f"📤 Sent END (id={session_id})")
            
            # Đợi response
            print("⏳ Waiting for server response...")
            
            # Server sẽ gửi response audio messages
            response_count = 0
            while response_count < 10:  # Giới hạn số lượng để tránh vòng lặp vô hạn
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    response_count += 1
                    
                    if isinstance(response, bytes):
                        # Parse response
                        # (Simplified - chỉ check type)
                        print(f"📥 Received binary response ({len(response)} bytes)")
                        
                        # Kiểm tra nếu là END acknowledgment thì dừng
                        # Note: Cần parse đầy đủ để check, nhưng để đơn giản ta dừng sau vài message
                        if response_count >= 5:
                            break
                    else:
                        print(f"📥 Received text response: {response}")
                        
                except asyncio.TimeoutError:
                    print("⏱️ Response timeout")
                    break
                    
            print("✅ Test completed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function"""
    print("=" * 50)
    print("Audio Message Wire Protocol - Test Client")
    print("=" * 50)
    
    while True:
        print("\nChọn test:")
        print("1. Test Text Chat")
        print("2. Test Audio Protocol")
        print("3. Exit")
        
        choice = input("\nNhập lựa chọn (1-3): ").strip()
        
        if choice == "1":
            await test_text_chat()
        elif choice == "2":
            await test_audio_protocol()
        elif choice == "3":
            print("Bye!")
            break
        else:
            print("❌ Lựa chọn không hợp lệ")
        
        print("\n" + "=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
