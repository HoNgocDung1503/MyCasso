"""
Quick test - Confirmation logic only (no OpenAI calls)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_confirmation_logic():
    print("\n" + "="*70)
    print("🧪 TESTING: Confirmation Detection Logic")
    print("="*70)
    
    # Simulate confirmation detection logic
    confirmation_keywords = [
        "oke", "ok", "okay", "được", "đồng ý", "xác nhận", 
        "chấp nhận", "đúng rồi", "vâng", "dạ"
    ]
    
    test_cases = [
        ("oke", True, "Simple confirmation"),
        ("được", True, "Single word confirmation"),
        ("xác nhận", True, "Explicit confirmation"),
        ("Cửa hàng có bán bánh mì không?", False, "Product inquiry - NOT confirmation"),
        ("Có bán trà sữa không?", False, "Question with 'có'"),
        ("Bao nhiêu tiền một tô phở?", False, "Price inquiry"),
        ("dạ được ạ", True, "Polite confirmation"),
        ("có shop ở đâu", False, "Location question"),
        ("shop có mấy chi nhánh", False, "Branch question"),
    ]
    
    for user_input, expected_confirm, desc in test_cases:
        message_lower = user_input.lower().strip()
        word_count = len(message_lower.split())
        is_question = any(q in message_lower for q in ["không", "không?", "chưa", "sao", "gì", "nào", "đâu", "bao nhiêu", "có bán", "có không"])
        
        is_confirmation = (
            word_count <= 10 and 
            not is_question and
            any(keyword in message_lower for keyword in confirmation_keywords)
        )
        
        status = "✅ PASS" if is_confirmation == expected_confirm else "❌ FAIL"
        
        print(f"\n{status} | {desc}")
        print(f"   Input: '{user_input}'")
        print(f"   Words: {word_count}, Is question: {is_question}")
        print(f"   Detected as confirmation: {is_confirmation} (expected: {expected_confirm})")
    
    print("\n" + "="*70)
    print("✅ LOGIC TEST COMPLETED")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_confirmation_logic()
