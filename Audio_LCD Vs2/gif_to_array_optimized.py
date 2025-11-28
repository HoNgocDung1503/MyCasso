"""
Chuyển đổi GIF thành mảng C++ cho ESP32 ST7789 (BẢN TỐI ƯU)
Sử dụng: python gif_to_array_optimized.py <file.gif> [--max-size 64] [--max-frames 20]
"""

from PIL import Image
import sys
import os
import argparse

def rgb_to_rgb565(r, g, b):
    """Chuyển đổi RGB888 sang RGB565"""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def gif_to_cpp_array(gif_path, output_name=None, max_size=64, max_frames=20, skip_frames=1):
    """
    Chuyển đổi GIF thành mảng C++ với tối ưu cho ESP32
    
    Args:
        gif_path: Đường dẫn file GIF
        output_name: Tên biến trong C++
        max_size: Kích thước tối đa (pixels) - sẽ giữ tỷ lệ
        max_frames: Số frames tối đa
        skip_frames: Bỏ qua mỗi N frames (1=giữ tất cả, 2=bỏ 1 giữ 1)
    """
    
    if not os.path.exists(gif_path):
        print(f"❌ Không tìm thấy file: {gif_path}")
        return
    
    # Mở GIF
    img = Image.open(gif_path)
    
    if output_name is None:
        output_name = os.path.splitext(os.path.basename(gif_path))[0]
        # Loại bỏ ký tự đặc biệt
        output_name = output_name.replace(' ', '_').replace('-', '_')
    
    # Lấy kích thước gốc
    orig_width, orig_height = img.size
    
    # Resize nếu cần (giữ tỷ lệ)
    if max(orig_width, orig_height) > max_size:
        ratio = max_size / max(orig_width, orig_height)
        new_width = int(orig_width * ratio)
        new_height = int(orig_height * ratio)
        print(f"📏 Resize từ {orig_width}x{orig_height} → {new_width}x{new_height}")
    else:
        new_width, new_height = orig_width, orig_height
    
    frames = []
    frame_count = 0
    durations = []
    total_frames = 0
    
    try:
        while True:
            # Đếm tổng số frames
            total_frames += 1
            
            # Skip frames nếu cần
            if (total_frames - 1) % skip_frames != 0:
                img.seek(img.tell() + 1)
                continue
            
            # Giới hạn số frames
            if frame_count >= max_frames:
                break
            
            # Lấy thông tin frame
            duration = img.info.get('duration', 100)
            durations.append(duration * skip_frames)  # Điều chỉnh duration
            
            # Resize và chuyển sang RGB
            frame = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            frame = frame.convert('RGB')
            pixels = []
            
            # Chuyển đổi từng pixel sang RGB565
            for y in range(new_height):
                for x in range(new_width):
                    r, g, b = frame.getpixel((x, y))
                    rgb565 = rgb_to_rgb565(r, g, b)
                    pixels.append(rgb565)
            
            frames.append(pixels)
            frame_count += 1
            
            # Chuyển sang frame tiếp theo
            img.seek(img.tell() + 1)
            
    except EOFError:
        pass  # Hết frames
    
    # Tính toán dung lượng
    size_bytes = new_width * new_height * frame_count * 2
    size_kb = size_bytes / 1024
    
    print(f"📊 Thông tin:")
    print(f"   - Kích thước: {new_width}x{new_height}")
    print(f"   - Frames: {frame_count}/{total_frames} (skip={skip_frames})")
    print(f"   - Dung lượng: ~{size_kb:.1f} KB ({size_bytes:,} bytes)")
    
    # Cảnh báo nếu quá lớn
    if size_kb > 500:
        print(f"⚠️  CẢNH BÁO: File quá lớn cho ESP32!")
        print(f"   Đề xuất: giảm --max-size hoặc --max-frames")
        response = input("   Vẫn muốn tạo file? (y/N): ")
        if response.lower() != 'y':
            print("❌ Đã hủy")
            return None
    
    # Tạo file header C++
    output_h = f"{output_name}_frames.h"
    
    print(f"⏳ Đang ghi file {output_h}...")
    
    with open(output_h, 'w', encoding='utf-8') as f:
        f.write(f"// Auto-generated from {os.path.basename(gif_path)}\n")
        f.write(f"// {frame_count} frames, {new_width}x{new_height} pixels\n")
        f.write(f"// Size: ~{size_kb:.1f} KB\n\n")
        f.write(f"#ifndef {output_name.upper()}_FRAMES_H\n")
        f.write(f"#define {output_name.upper()}_FRAMES_H\n\n")
        f.write("#include <Arduino.h>\n\n")
        
        # Thông tin
        f.write(f"const int {output_name}_WIDTH = {new_width};\n")
        f.write(f"const int {output_name}_HEIGHT = {new_height};\n")
        f.write(f"const int {output_name}_FRAMES = {frame_count};\n\n")
        
        # Durations
        f.write(f"const int {output_name}_durations[{frame_count}] = {{\n  ")
        f.write(", ".join(map(str, durations)))
        f.write("\n};\n\n")
        
        # Frames data
        f.write(f"const uint16_t PROGMEM {output_name}_frames[{frame_count}][{new_width * new_height}] = {{\n")
        
        for i, frame_data in enumerate(frames):
            f.write(f"  {{ // Frame {i}\n    ")
            
            # Ghi 12 pixels mỗi dòng
            for j, pixel in enumerate(frame_data):
                f.write(f"0x{pixel:04X}")
                if j < len(frame_data) - 1:
                    f.write(",")
                    if (j + 1) % 12 == 0:
                        f.write("\n    ")
                    else:
                        f.write(" ")
            
            f.write("\n  }")
            if i < len(frames) - 1:
                f.write(",")
            f.write("\n")
        
        f.write("};\n\n")
        f.write(f"#endif // {output_name.upper()}_FRAMES_H\n")
    
    print(f"✅ Đã tạo {output_h} thành công!")
    
    return output_h

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Chuyển đổi GIF sang mảng C++ cho ESP32')
    parser.add_argument('gif_file', help='File GIF cần chuyển đổi')
    parser.add_argument('--max-size', type=int, default=64, help='Kích thước tối đa (pixels, mặc định: 64)')
    parser.add_argument('--max-frames', type=int, default=20, help='Số frames tối đa (mặc định: 20)')
    parser.add_argument('--skip-frames', type=int, default=1, help='Bỏ qua frames (1=giữ tất cả, 2=bỏ 1 giữ 1)')
    parser.add_argument('--output', help='Tên biến output (mặc định: tên file)')
    
    args = parser.parse_args()
    
    if not args.gif_file.lower().endswith('.gif'):
        print("❌ File phải có đuôi .gif")
        sys.exit(1)
    
    print(f"\n🎬 Đang xử lý: {args.gif_file}")
    print(f"   - Max size: {args.max_size}x{args.max_size}")
    print(f"   - Max frames: {args.max_frames}")
    print(f"   - Skip frames: {args.skip_frames}\n")
    
    gif_to_cpp_array(
        args.gif_file,
        output_name=args.output,
        max_size=args.max_size,
        max_frames=args.max_frames,
        skip_frames=args.skip_frames
    )
