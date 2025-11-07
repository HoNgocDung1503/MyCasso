"""
Chuyển đổi GIF thành mảng C++ cho ESP32 ST7789
Sử dụng: python gif_to_array.py <file.gif>
"""

from PIL import Image
import sys
import os

def rgb_to_rgb565(r, g, b):
    """Chuyển đổi RGB888 sang RGB565"""
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def gif_to_cpp_array(gif_path, output_name=None):
    """Chuyển đổi GIF thành mảng C++"""
    
    if not os.path.exists(gif_path):
        print(f"Không tìm thấy file: {gif_path}")
        return
    
    # Mở GIF
    img = Image.open(gif_path)
    
    if output_name is None:
        output_name = os.path.splitext(os.path.basename(gif_path))[0]
    
    frames = []
    frame_count = 0
    durations = []
    
    try:
        while True:
            # Lấy thông tin frame
            width, height = img.size
            duration = img.info.get('duration', 100)  # ms
            durations.append(duration)
            
            # Chuyển sang RGB
            frame = img.convert('RGB')
            pixels = []
            
            # Chuyển đổi từng pixel sang RGB565
            for y in range(height):
                for x in range(width):
                    r, g, b = frame.getpixel((x, y))
                    rgb565 = rgb_to_rgb565(r, g, b)
                    pixels.append(rgb565)
            
            frames.append(pixels)
            frame_count += 1
            
            # Chuyển sang frame tiếp theo
            img.seek(img.tell() + 1)
            
    except EOFError:
        pass  # Hết frames
    
    # Tạo file header C++
    output_h = f"{output_name}_frames.h"
    
    with open(output_h, 'w', encoding='utf-8') as f:
        f.write(f"// Auto-generated from {os.path.basename(gif_path)}\n")
        f.write(f"// {frame_count} frames, {width}x{height} pixels\n\n")
        f.write(f"#ifndef {output_name.upper()}_FRAMES_H\n")
        f.write(f"#define {output_name.upper()}_FRAMES_H\n\n")
        f.write("#include <Arduino.h>\n\n")
        
        # Thông tin
        f.write(f"const int {output_name}_WIDTH = {width};\n")
        f.write(f"const int {output_name}_HEIGHT = {height};\n")
        f.write(f"const int {output_name}_FRAMES = {frame_count};\n\n")
        
        # Durations
        f.write(f"const int {output_name}_durations[{frame_count}] = {{\n  ")
        f.write(", ".join(map(str, durations)))
        f.write("\n};\n\n")
        
        # Frames data
        f.write(f"const uint16_t PROGMEM {output_name}_frames[{frame_count}][{width * height}] = {{\n")
        
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
    
    print(f"✓ Đã tạo {output_h}")
    print(f"  - Kích thước: {width}x{height}")
    print(f"  - Số frames: {frame_count}")
    print(f"  - Dung lượng: ~{(width * height * frame_count * 2) / 1024:.1f} KB")
    
    return output_h

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python gif_to_array.py <file.gif>")
        print("\nHoặc để chuyển đổi tất cả GIF trong thư mục:")
        print("python gif_to_array.py *.gif")
        sys.exit(1)
    
    # Chuyển đổi từng file
    for gif_file in sys.argv[1:]:
        if gif_file.lower().endswith('.gif'):
            print(f"\nĐang xử lý: {gif_file}")
            gif_to_cpp_array(gif_file)
        else:
            print(f"Bỏ qua: {gif_file} (không phải file GIF)")
