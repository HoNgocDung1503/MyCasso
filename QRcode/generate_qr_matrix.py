import qrcode

# Chuỗi QR code
qr_string = '00020101021238540010A00000072701240006970415011009876487170208QRIBFTTA53037045405790005802VN62220818Ung Ho Quy Vac Xin6304CD8F'

# Tạo QR code với version 6 (41x41)
qr = qrcode.QRCode(
    version=6,  # Version 6 tạo matrix 41x41
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=1,
    border=0,
)

qr.add_data(qr_string)
qr.make(fit=False)  # fit=False để giữ nguyên version 6

# Lấy matrix
matrix = qr.get_matrix()

print(f"Matrix size: {len(matrix)}x{len(matrix[0])}")

# Lưu dạng array 2D format [[1,0,1,...],[1,0,1,...],...]
with open('qr_matrix_41x41.txt', 'w') as f:
    f.write("[")
    for i, row in enumerate(matrix):
        f.write("[")
        for j, cell in enumerate(row):
            value = 1 if cell else 0
            f.write(str(value))
            if j < len(row) - 1:
                f.write(",")
        f.write("]")
        if i < len(matrix) - 1:
            f.write(",")
    f.write("]")

print("✅ Matrix đã được lưu vào file qr_matrix_41x41.txt")

# In ra console để xem
print("\n📊 Matrix preview (1 = đen, 0 = trắng):\n")
for row in matrix:
    for cell in row:
        print("█" if cell else " ", end="")
    print()
