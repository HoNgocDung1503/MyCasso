# migrate_to_json_only.py
import json

# Tất cả sản phẩm hiện có (chuyển is_custom = True)
all_products = {
    "banh_mi": {
        "id": "banh_mi",
        "name": "Bánh mì",
        "price": 15000.0,
        "unit": "cái",
        "category": "Thức ăn",
        "available": True,
        "is_custom": True
    },
    "banh_mi_thit": {
        "id": "banh_mi_thit",
        "name": "Bánh mì thịt",
        "price": 20000.0,
        "unit": "cái",
        "category": "Thức ăn",
        "available": True,
        "is_custom": True
    },
    "banh_mi_trung": {
        "id": "banh_mi_trung",
        "name": "Bánh mì trứng",
        "price": 18000.0,
        "unit": "cái",
        "category": "Thức ăn",
        "available": True,
        "is_custom": True
    },
    "banh_mi_sua": {
        "id": "banh_mi_sua",
        "name": "Bánh mì sữa",
        "price": 22000.0,
        "unit": "cái",
        "category": "Thức ăn",
        "available": True,
        "is_custom": True
    },
    "pho": {
        "id": "pho",
        "name": "Phở",
        "price": 45000.0,
        "unit": "tô",
        "category": "Thức ăn",
        "available": True,
        "is_custom": True
    },
    "bun_bo": {
        "id": "bun_bo",
        "name": "Bún bò",
        "price": 40000.0,
        "unit": "tô",
        "category": "Thức ăn",
        "available": True,
        "is_custom": True
    },
    "sua": {
        "id": "sua",
        "name": "Sữa",
        "price": 12000.0,
        "unit": "hộp",
        "category": "Đồ uống",
        "available": True,
        "is_custom": True
    },
    "sua_dau_nanh": {
        "id": "sua_dau_nanh",
        "name": "Sữa đậu nành",
        "price": 10000.0,
        "unit": "hộp",
        "category": "Đồ uống",
        "available": True,
        "is_custom": True
    },
    "nuoc_ngot": {
        "id": "nuoc_ngot",
        "name": "Nước ngọt",
        "price": 15000.0,
        "unit": "chai",
        "category": "Đồ uống",
        "available": True,
        "is_custom": True
    },
    "tra_sua": {
        "id": "tra_sua",
        "name": "Trà sữa",
        "price": 30000.0,
        "unit": "ly",
        "category": "Đồ uống",
        "available": True,
        "is_custom": True
    },
    "ca_phe": {
        "id": "ca_phe",
        "name": "Cà phê",
        "price": 25000.0,
        "unit": "ly",
        "category": "Đồ uống",
        "available": True,
        "is_custom": True
    },
    "nuoc_suoi": {
        "id": "nuoc_suoi",
        "name": "Nước suối",
        "price": 8000.0,
        "unit": "chai",
        "category": "Đồ uống",
        "available": True,
        "is_custom": True
    },
    "snack": {
        "id": "snack",
        "name": "Snack",
        "price": 10000.0,
        "unit": "gói",
        "category": "Snack",
        "available": True,
        "is_custom": True
    },
    "keo": {
        "id": "keo",
        "name": "Kẹo",
        "price": 5000.0,
        "unit": "gói",
        "category": "Snack",
        "available": True,
        "is_custom": True
    },
    "banh_quy": {
        "id": "banh_quy",
        "name": "Bánh quy",
        "price": 20000.0,
        "unit": "hộp",
        "category": "Snack",
        "available": True,
        "is_custom": True
    },
    "tao": {
        "id": "tao",
        "name": "Táo",
        "price": 30000.0,
        "unit": "kg",
        "category": "Trái cây",
        "available": True,
        "is_custom": True
    },
    "chuoi": {
        "id": "chuoi",
        "name": "Chuối",
        "price": 15000.0,
        "unit": "kg",
        "category": "Trái cây",
        "available": True,
        "is_custom": True
    },
    "cam": {
        "id": "cam",
        "name": "Cam",
        "price": 40000.0,
        "unit": "kg",
        "category": "Trái cây",
        "available": True,
        "is_custom": True
    },
    "rau": {
        "id": "rau",
        "name": "Rau",
        "price": 10000.0,
        "unit": "bó",
        "category": "Rau củ",
        "available": True,
        "is_custom": True
    },
    "khoai_tay": {
        "id": "khoai_tay",
        "name": "Khoai tây",
        "price": 20000.0,
        "unit": "kg",
        "category": "Rau củ",
        "available": True,
        "is_custom": True
    }
}

# Load custom hiện tại và merge
try:
    with open('custom_products.json', 'r', encoding='utf-8') as f:
        existing = json.load(f)
        # Merge: giữ custom nếu trùng ID
        for pid, pdata in existing.items():
            if pid in all_products:
                # Giữ giá custom nếu đã cập nhật
                all_products[pid] = pdata
            else:
                # Thêm món custom mới
                all_products[pid] = pdata
except:
    pass

# Save toàn bộ
with open('custom_products.json', 'w', encoding='utf-8') as f:
    json.dump(all_products, f, ensure_ascii=False, indent=2)

print(f"✅ Migrated {len(all_products)} products to JSON-only mode")
print("✅ All products are now is_custom=True")
print("🎉 You can now delete products without them coming back after restart!")