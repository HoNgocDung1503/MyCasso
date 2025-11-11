"""
Test cancellation detection - Fix bug nhầm câu hỏi với hủy đơn
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_cancellation_logic():
    print("\n" + "="*70)
    print("🧪 TESTING: Smart Cancellation Detection")
    print("="*70)
    
    # Test cases
    test_cases = [
        # TRUE CANCELLATION (should cancel)
        ("không lấy", True, "Clear cancellation"),
        ("thôi không mua", True, "Cancel order"),
        ("hủy đơn", True, "Explicit cancel"),
        ("đổi ý rồi", True, "Change mind"),
        ("thôi ạ", True, "Polite cancel"),
        
        # QUESTIONS (should NOT cancel)
        ("Cửa hàng có bán trà sữa không?", False, "Product question"),
        ("Ngoài bánh mì, có bán gì không?", False, "Other products question"),
        ("Có bán cà phê không?", False, "Coffee question"),
        ("Món này bao nhiêu tiền?", False, "Price question"),
        ("Shop có mấy chi nhánh?", False, "Branch question"),
    ]
    
    for user_input, expected_cancel, desc in test_cases:
        message_lower = user_input.lower().strip()
        
        # Detect questions
        is_question = any(q in message_lower for q in [
            "không?", "chưa?", "sao", "gì", "nào", "đâu", 
            "bao nhiêu", "có bán", "có không", "bán không"
        ])
        
        # Cancellation phrases
        cancellation_phrases = [
            "không lấy", "không mua", "thôi không", "hủy đơn", 
            "cancel", "đổi ý", "thôi ạ", "thôi em"
        ]
        
        is_cancellation = (
            not is_question and
            any(phrase in message_lower for phrase in cancellation_phrases)
        )
        
        status = "✅ PASS" if is_cancellation == expected_cancel else "❌ FAIL"
        
        print(f"\n{status} | {desc}")
        print(f"   Input: '{user_input}'")
        print(f"   Is question: {is_question}")
        print(f"   Detected as cancellation: {is_cancellation} (expected: {expected_cancel})")
    
    print("\n" + "="*70)
    print("✅ LOGIC TEST COMPLETED")
    print("="*70 + "\n")

if __name__ == "__main__":
    test_cancellation_logic()
