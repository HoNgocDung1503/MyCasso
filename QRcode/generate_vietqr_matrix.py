import requests
import qrcode
import numpy as np
import json

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

try:
    response = requests.post('https://api.vietqr.io/v2/generate', json=account_info, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    # Lấy chuỗi qrCode
    if 'data' in data and 'qrCode' in data['data']:
        qr_code_string = data['data']['qrCode']
    elif 'qrCode' in data:
        qr_code_string = data['qrCode']
    else:
        raise ValueError("Không tìm thấy qrCode trong response")
    
    print(f"QR Code String: {qr_code_string}")
    print("="*50 + "\n")
    
    # Tạo QR code từ chuỗi
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=0,
    )
    qr.add_data(qr_code_string)
    qr.make(fit=True)
    
    # Lấy ma trận
    qr_matrix = qr.get_matrix()
    qr_array = np.array(qr_matrix, dtype=int)
    
    print(f"Kích thước ma trận: {qr_array.shape}")
    
    # Chuyển ma trận thành JSON string (1 dòng)
    matrix_json = json.dumps(qr_array.tolist())
    
    print(f"Độ dài JSON string: {len(matrix_json)} ký tự\n")
    
    # Xuất ra file txt
    with open('qr_matrix.txt', 'w', encoding='utf-8') as f:
        f.write(matrix_json)
    
    print("✅ Đã xuất ma trận JSON ra file 'qr_matrix.txt'")
    print(f"\nNội dung (preview 200 ký tự đầu):")
    print(matrix_json[:200] + "...")
    
    # Kiểm tra đọc lại file
    print("\n" + "="*50)
    print("Kiểm tra đọc lại từ file:")
    with open('qr_matrix.txt', 'r', encoding='utf-8') as f:
        loaded_json = f.read()
        loaded_matrix = np.array(json.loads(loaded_json))
        print(f"Kích thước ma trận đọc lại: {loaded_matrix.shape}")
        print(f"Ma trận giống nhau? {np.array_equal(qr_array, loaded_matrix)}")
    
except requests.exceptions.RequestException as e:
    print(f"Lỗi khi gọi API: {e}")
except Exception as e:
    print(f"Lỗi: {e}")