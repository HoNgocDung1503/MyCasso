#main V4 - Fixed resize with proper module sampling

import requests
import base64
from PIL import Image
import numpy as np

# Thông tin tài khoản
account_info = {
    "accountNo": "0987648717",
    "accountName": "HO NGOC DUNG",
    "acqId": 970415,
    "amount": 7000,
    "addInfo": "TEST QR CODE",
    "format": "text",
    "template": "qr_only"
}

# Gọi API VietQR
headers = {
    'x-api-key': 'we-l0v3-v1et-qr',
    'Content-Type': 'application/json'
}
response = requests.post('https://api.vietqr.io/v2/generate', json=account_info, headers=headers)
data = response.json()

# Lấy base64 PNG từ API
qr_base64 = None
if 'data' in data and 'qrDataURL' in data['data']:
    qr_base64 = data['data']['qrDataURL'].replace('data:image/png;base64,', '')
if not qr_base64:
    print('❌ Không lấy được qrDataURL từ API')
    print('Phản hồi API:', data)
    exit(1)

# Giải mã base64 và lưu ảnh gốc
with open('qr_original.png', 'wb') as f:
    f.write(base64.b64decode(qr_base64))
print('✅ Ảnh QR gốc đã lưu vào qr_original.png')

# Đọc ảnh gốc
img_original = Image.open('qr_original.png').convert('L')
print(f"📐 Kích thước ảnh gốc: {img_original.size}")

# Chuyển sang nhị phân với ngưỡng tự động
arr_original = np.array(img_original)
threshold = np.mean(arr_original)
print(f"🎯 Ngưỡng nhị phân hóa: {threshold}")

# Tạo ảnh nhị phân
img_binary = Image.fromarray(((arr_original < threshold) * 255).astype(np.uint8))
img_binary.save('qr_binary.png')
print('✅ Ảnh nhị phân đã lưu vào qr_binary.png')

# Tìm vùng QR code thực sự (bỏ padding trắng)
arr_binary = np.array(img_binary)
rows = np.any(arr_binary < 128, axis=1)
cols = np.any(arr_binary < 128, axis=0)

if not rows.any() or not cols.any():
    print("⚠️ Không tìm thấy vùng QR, sử dụng toàn bộ ảnh")
    img_cropped = img_binary
else:
    ymin, ymax = np.where(rows)[0][[0, -1]]
    xmin, xmax = np.where(cols)[0][[0, -1]]
    img_cropped = img_binary.crop((xmin, ymin, xmax+1, ymax+1))

print(f"✂️ Kích thước sau khi crop: {img_cropped.size}")
img_cropped.save('qr_cropped.png')

# FIXED: Sample đúng từng module với trung bình vùng
cropped_width, cropped_height = img_cropped.size
arr_cropped = np.array(img_cropped)

# Tính module size (kích thước mỗi ô QR)
module_size_w = cropped_width / 41
module_size_h = cropped_height / 41

print(f"📏 Module size: {module_size_w:.2f} x {module_size_h:.2f} pixels")

# Sample từng module bằng cách lấy trung bình vùng 3x3 pixels ở giữa
matrix = []
for row in range(41):
    matrix_row = []
    for col in range(41):
        # Tọa độ tâm của module
        center_y = int((row + 0.5) * module_size_h)
        center_x = int((col + 0.5) * module_size_w)
        
        # Lấy vùng 3x3 xung quanh tâm để tính trung bình (tránh noise)
        y_start = max(0, center_y - 1)
        y_end = min(cropped_height, center_y + 2)
        x_start = max(0, center_x - 1)
        x_end = min(cropped_width, center_x + 2)
        
        region = arr_cropped[y_start:y_end, x_start:x_end]
        avg_value = np.mean(region)
        
        # 1 = đen, 0 = trắng
        matrix_row.append(1 if avg_value < 128 else 0)
    
    matrix.append(matrix_row)

# Tạo ảnh 41x41 từ matrix để kiểm tra
img_41x41_check = Image.new('L', (41, 41))
pixels_check = img_41x41_check.load()
for y in range(41):
    for x in range(41):
        pixels_check[x, y] = 0 if matrix[y][x] == 1 else 255

img_41x41_check.save('qr_41x41_sampled.png')
print('✅ Ảnh QR 41x41 (sampled) đã lưu')

# Tạo ảnh lớn hơn để dễ nhìn (mỗi module = 10 pixels)
img_preview = Image.new('L', (410, 410))
pixels_preview = img_preview.load()
for y in range(41):
    for x in range(41):
        color = 0 if matrix[y][x] == 1 else 255
        for dy in range(10):
            for dx in range(10):
                pixels_preview[x*10 + dx, y*10 + dy] = color

img_preview.save('qr_preview_410x410.png')
print('✅ Ảnh preview 410x410 đã lưu')

# Lưu matrix ra file txt - DẠNG COMPACT
with open('qr_matrix_41x41.txt', 'w') as f:
    f.write("[")
    for i, row in enumerate(matrix):
        f.write("[")
        f.write(",".join(str(cell) for cell in row))
        f.write("]")
        if i < len(matrix) - 1:
            f.write(",")
    f.write("]")
print("✅ Matrix đã lưu vào qr_matrix_41x41.txt")

# In matrix ra console
print("\n📋 Matrix (copy để dùng):")
print("[", end="")
for i, row in enumerate(matrix):
    print("[", end="")
    print(",".join(str(cell) for cell in row), end="")
    print("]", end="")
    if i < len(matrix) - 1:
        print(",", end="")
print("]")

# Thống kê
black_pixels = sum(sum(row) for row in matrix)
total_pixels = 41 * 41
print(f"\n📊 Thống kê:")
print(f"   - Tổng pixels: {total_pixels}")
print(f"   - Pixels đen (1): {black_pixels} ({black_pixels/total_pixels*100:.1f}%)")
print(f"   - Pixels trắng (0): {total_pixels - black_pixels} ({(total_pixels-black_pixels)/total_pixels*100:.1f}%)")

# Kiểm tra finder patterns
def check_corner(matrix, corner):
    if corner == "top-left":
        region = [matrix[i][0:7] for i in range(7)]
    elif corner == "top-right":
        region = [matrix[i][34:41] for i in range(7)]
    elif corner == "bottom-left":
        region = [matrix[i][0:7] for i in range(34, 41)]
    else:
        return False
    
    black_count = sum(sum(row) for row in region)
    return black_count > 15

print(f"\n🔍 Kiểm tra Finder Patterns:")
print(f"   - Góc trên trái: {'✅' if check_corner(matrix, 'top-left') else '❌'}")
print(f"   - Góc trên phải: {'✅' if check_corner(matrix, 'top-right') else '❌'}")
print(f"   - Góc dưới trái: {'✅' if check_corner(matrix, 'bottom-left') else '❌'}")