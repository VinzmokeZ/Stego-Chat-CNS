#!/usr/bin/env python3
"""
StegoChat Backend API Test Suite
Tests all backend endpoints comprehensively including the complete steganography workflow.
"""

import requests
import base64
import json
import io
from PIL import Image
import os
import sys
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = "https://hidden-messaging.preview.emergentagent.com/api"

class StegoTestResults:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def add_result(self, test_name, passed, message="", details=""):
        self.results.append({
            "test": test_name,
            "passed": passed,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def print_summary(self):
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Tests: {len(self.results)}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {(self.passed/len(self.results)*100):.1f}%")
        
        if self.failed > 0:
            print(f"\n{'='*60}")
            print("FAILED TESTS:")
            print(f"{'='*60}")
            for result in self.results:
                if not result["passed"]:
                    print(f"❌ {result['test']}: {result['message']}")
                    if result["details"]:
                        print(f"   Details: {result['details']}")

def create_test_image():
    """Create a simple test image for steganography testing"""
    # Create a 100x100 RGB image with some pattern
    img = Image.new('RGB', (100, 100), color='white')
    pixels = []
    for y in range(100):
        for x in range(100):
            # Create a simple gradient pattern
            r = min(255, x * 2 + y)
            g = min(255, y * 2)
            b = min(255, (x + y) % 255)
            pixels.append((r, g, b))
    
    img.putdata(pixels)
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()

def test_basic_connectivity(results):
    """Test basic API connectivity"""
    try:
        response = requests.get(f"{BACKEND_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "message" in data and "StegoChat" in data["message"]:
                results.add_result("Basic Connectivity", True, "API is accessible and responding")
            else:
                results.add_result("Basic Connectivity", False, "API responding but unexpected message", str(data))
        else:
            results.add_result("Basic Connectivity", False, f"HTTP {response.status_code}", response.text)
    except Exception as e:
        results.add_result("Basic Connectivity", False, "Connection failed", str(e))

def test_aes_encryption(results):
    """Test AES encryption endpoint"""
    try:
        test_message = "Hello, this is a secret message for testing AES encryption!"
        
        response = requests.post(
            f"{BACKEND_URL}/crypto/encrypt",
            json={"plaintext": test_message},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "ciphertext" in data and "key" in data:
                # Verify we got base64 encoded data
                try:
                    base64.b64decode(data["ciphertext"])
                    base64.b64decode(data["key"])
                    results.add_result("AES Encryption", True, "Successfully encrypted message")
                    return data  # Return for use in decryption test
                except Exception as e:
                    results.add_result("AES Encryption", False, "Invalid base64 in response", str(e))
            else:
                results.add_result("AES Encryption", False, "Missing ciphertext or key in response", str(data))
        else:
            results.add_result("AES Encryption", False, f"HTTP {response.status_code}", response.text)
    except Exception as e:
        results.add_result("AES Encryption", False, "Request failed", str(e))
    
    return None

def test_aes_decryption(results, encryption_data):
    """Test AES decryption endpoint"""
    if not encryption_data:
        results.add_result("AES Decryption", False, "No encryption data available", "Encryption test failed")
        return
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/crypto/decrypt",
            json={
                "ciphertext": encryption_data["ciphertext"],
                "key": encryption_data["key"]
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "plaintext" in data:
                expected_message = "Hello, this is a secret message for testing AES encryption!"
                if data["plaintext"] == expected_message:
                    results.add_result("AES Decryption", True, "Successfully decrypted message")
                else:
                    results.add_result("AES Decryption", False, "Decrypted message doesn't match original", 
                                     f"Expected: {expected_message}, Got: {data['plaintext']}")
            else:
                results.add_result("AES Decryption", False, "Missing plaintext in response", str(data))
        else:
            results.add_result("AES Decryption", False, f"HTTP {response.status_code}", response.text)
    except Exception as e:
        results.add_result("AES Decryption", False, "Request failed", str(e))

def test_aes_invalid_key(results):
    """Test AES decryption with invalid key"""
    try:
        # Use invalid key
        invalid_key = base64.b64encode(b"invalid_key_data").decode()
        fake_ciphertext = base64.b64encode(b"fake_cipher_data").decode()
        
        response = requests.post(
            f"{BACKEND_URL}/crypto/decrypt",
            json={
                "ciphertext": fake_ciphertext,
                "key": invalid_key
            },
            timeout=10
        )
        
        if response.status_code == 500:
            results.add_result("AES Invalid Key Handling", True, "Correctly rejected invalid key")
        else:
            results.add_result("AES Invalid Key Handling", False, 
                             f"Expected HTTP 500, got {response.status_code}", response.text)
    except Exception as e:
        results.add_result("AES Invalid Key Handling", False, "Request failed", str(e))

def test_steganography_embed(results, test_image_b64):
    """Test steganography embedding endpoint"""
    try:
        test_message = "This is a hidden message embedded using LSB steganography!"
        
        response = requests.post(
            f"{BACKEND_URL}/stego/embed",
            json={
                "image_data": test_image_b64,
                "message": test_message
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if "stego_image" in data:
                # Verify we got valid base64 image data
                try:
                    stego_image_bytes = base64.b64decode(data["stego_image"])
                    # Try to open as image to verify it's valid
                    Image.open(io.BytesIO(stego_image_bytes))
                    results.add_result("Steganography Embed", True, "Successfully embedded message in image")
                    return data["stego_image"]  # Return for extraction test
                except Exception as e:
                    results.add_result("Steganography Embed", False, "Invalid image data in response", str(e))
            else:
                results.add_result("Steganography Embed", False, "Missing stego_image in response", str(data))
        else:
            results.add_result("Steganography Embed", False, f"HTTP {response.status_code}", response.text)
    except Exception as e:
        results.add_result("Steganography Embed", False, "Request failed", str(e))
    
    return None

def test_steganography_extract(results, stego_image_b64):
    """Test steganography extraction endpoint"""
    if not stego_image_b64:
        results.add_result("Steganography Extract", False, "No stego image available", "Embed test failed")
        return
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/stego/extract",
            json={"image_data": stego_image_b64},
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            if "hidden_message" in data:
                expected_message = "This is a hidden message embedded using LSB steganography!"
                if data["hidden_message"] == expected_message:
                    results.add_result("Steganography Extract", True, "Successfully extracted hidden message")
                else:
                    results.add_result("Steganography Extract", False, "Extracted message doesn't match original",
                                     f"Expected: {expected_message}, Got: {data['hidden_message']}")
            else:
                results.add_result("Steganography Extract", False, "Missing hidden_message in response", str(data))
        else:
            results.add_result("Steganography Extract", False, f"HTTP {response.status_code}", response.text)
    except Exception as e:
        results.add_result("Steganography Extract", False, "Request failed", str(e))

def test_steganography_large_message(results, test_image_b64):
    """Test steganography with a large message"""
    try:
        # Create a message that might be too large for a 100x100 image
        large_message = "A" * 5000  # 5000 characters
        
        response = requests.post(
            f"{BACKEND_URL}/stego/embed",
            json={
                "image_data": test_image_b64,
                "message": large_message
            },
            timeout=15
        )
        
        if response.status_code == 500:
            results.add_result("Steganography Large Message Handling", True, "Correctly rejected message too large for image")
        else:
            results.add_result("Steganography Large Message Handling", False, 
                             f"Expected HTTP 500, got {response.status_code}", response.text)
    except Exception as e:
        results.add_result("Steganography Large Message Handling", False, "Request failed", str(e))

def test_user_login(results):
    """Test user login endpoint"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/users/login",
            json={
                "username": "TestUser123",
                "avatar": None
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "user" in data and "message" in data:
                user = data["user"]
                if "id" in user and "username" in user and user["username"] == "TestUser123":
                    results.add_result("User Login", True, "Successfully logged in user")
                    return user["id"]  # Return user ID for chat tests
                else:
                    results.add_result("User Login", False, "Invalid user data in response", str(data))
            else:
                results.add_result("User Login", False, "Missing user or message in response", str(data))
        else:
            results.add_result("User Login", False, f"HTTP {response.status_code}", response.text)
    except Exception as e:
        results.add_result("User Login", False, "Request failed", str(e))
    
    return None

def test_get_users(results):
    """Test get users endpoint"""
    try:
        response = requests.get(f"{BACKEND_URL}/users/users", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                # Check if we have the expected demo users
                usernames = [user.get("username") for user in data]
                expected_users = ["Alice", "Bob", "Charlie"]
                if all(user in usernames for user in expected_users):
                    results.add_result("Get Users", True, f"Successfully retrieved {len(data)} users")
                else:
                    results.add_result("Get Users", False, "Missing expected demo users", f"Got: {usernames}")
            else:
                results.add_result("Get Users", False, "Invalid users list in response", str(data))
        else:
            results.add_result("Get Users", False, f"HTTP {response.status_code}", response.text)
    except Exception as e:
        results.add_result("Get Users", False, "Request failed", str(e))

def test_send_message(results, user_id):
    """Test sending a chat message"""
    if not user_id:
        results.add_result("Send Message", False, "No user ID available", "Login test failed")
        return
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat/messages",
            json={
                "sender_id": user_id,
                "receiver_id": "user1",  # Alice from demo users
                "content": "Hello Alice! This is a test message.",
                "message_type": "text"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "id" in data and "content" in data and data["content"] == "Hello Alice! This is a test message.":
                results.add_result("Send Message", True, "Successfully sent message")
                return data["id"]  # Return message ID
            else:
                results.add_result("Send Message", False, "Invalid message data in response", str(data))
        else:
            results.add_result("Send Message", False, f"HTTP {response.status_code}", response.text)
    except Exception as e:
        results.add_result("Send Message", False, "Request failed", str(e))
    
    return None

def test_get_chat_history(results, user_id):
    """Test getting chat history"""
    if not user_id:
        results.add_result("Get Chat History", False, "No user ID available", "Login test failed")
        return
    
    try:
        response = requests.get(f"{BACKEND_URL}/chat/messages/{user_id}/user1", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "messages" in data and "total_count" in data:
                messages = data["messages"]
                if len(messages) > 0:
                    results.add_result("Get Chat History", True, f"Successfully retrieved {len(messages)} messages")
                else:
                    results.add_result("Get Chat History", True, "Successfully retrieved empty chat history")
            else:
                results.add_result("Get Chat History", False, "Invalid chat history format", str(data))
        else:
            results.add_result("Get Chat History", False, f"HTTP {response.status_code}", response.text)
    except Exception as e:
        results.add_result("Get Chat History", False, "Request failed", str(e))

def test_complete_workflow(results):
    """Test the complete steganography + encryption workflow"""
    try:
        print("\n🔄 Testing Complete Workflow: Encrypt → Embed → Extract → Decrypt")
        
        # Step 1: Create test message and encrypt it
        original_message = "Secret mission: Meet at the old oak tree at midnight! 🌙"
        
        # Encrypt the message
        encrypt_response = requests.post(
            f"{BACKEND_URL}/crypto/encrypt",
            json={"plaintext": original_message},
            timeout=10
        )
        
        if encrypt_response.status_code != 200:
            results.add_result("Complete Workflow", False, "Encryption step failed", encrypt_response.text)
            return
        
        encrypt_data = encrypt_response.json()
        encrypted_message = encrypt_data["ciphertext"]
        encryption_key = encrypt_data["key"]
        
        # Step 2: Create test image and embed encrypted message
        test_image = create_test_image()
        
        embed_response = requests.post(
            f"{BACKEND_URL}/stego/embed",
            json={
                "image_data": test_image,
                "message": encrypted_message
            },
            timeout=15
        )
        
        if embed_response.status_code != 200:
            results.add_result("Complete Workflow", False, "Embedding step failed", embed_response.text)
            return
        
        embed_data = embed_response.json()
        stego_image = embed_data["stego_image"]
        
        # Step 3: Extract message from stego image
        extract_response = requests.post(
            f"{BACKEND_URL}/stego/extract",
            json={"image_data": stego_image},
            timeout=15
        )
        
        if extract_response.status_code != 200:
            results.add_result("Complete Workflow", False, "Extraction step failed", extract_response.text)
            return
        
        extract_data = extract_response.json()
        extracted_encrypted_message = extract_data["hidden_message"]
        
        # Step 4: Decrypt the extracted message
        decrypt_response = requests.post(
            f"{BACKEND_URL}/crypto/decrypt",
            json={
                "ciphertext": extracted_encrypted_message,
                "key": encryption_key
            },
            timeout=10
        )
        
        if decrypt_response.status_code != 200:
            results.add_result("Complete Workflow", False, "Decryption step failed", decrypt_response.text)
            return
        
        decrypt_data = decrypt_response.json()
        final_message = decrypt_data["plaintext"]
        
        # Verify the complete workflow
        if final_message == original_message:
            results.add_result("Complete Workflow", True, 
                             "Successfully completed encrypt→embed→extract→decrypt workflow")
        else:
            results.add_result("Complete Workflow", False, 
                             "Workflow completed but message corrupted",
                             f"Original: {original_message}, Final: {final_message}")
        
    except Exception as e:
        results.add_result("Complete Workflow", False, "Workflow failed", str(e))

def main():
    """Run all backend tests"""
    print("🚀 Starting StegoChat Backend API Tests")
    print(f"Backend URL: {BACKEND_URL}")
    print("="*60)
    
    results = StegoTestResults()
    
    # Test basic connectivity
    print("1. Testing basic connectivity...")
    test_basic_connectivity(results)
    
    # Test AES encryption/decryption
    print("2. Testing AES encryption...")
    encryption_data = test_aes_encryption(results)
    
    print("3. Testing AES decryption...")
    test_aes_decryption(results, encryption_data)
    
    print("4. Testing AES error handling...")
    test_aes_invalid_key(results)
    
    # Test steganography
    print("5. Creating test image...")
    test_image_b64 = create_test_image()
    
    print("6. Testing steganography embedding...")
    stego_image_b64 = test_steganography_embed(results, test_image_b64)
    
    print("7. Testing steganography extraction...")
    test_steganography_extract(results, stego_image_b64)
    
    print("8. Testing steganography error handling...")
    test_steganography_large_message(results, test_image_b64)
    
    # Test user management
    print("9. Testing user login...")
    user_id = test_user_login(results)
    
    print("10. Testing get users...")
    test_get_users(results)
    
    # Test chat functionality
    print("11. Testing send message...")
    message_id = test_send_message(results, user_id)
    
    print("12. Testing get chat history...")
    test_get_chat_history(results, user_id)
    
    # Test complete workflow
    print("13. Testing complete workflow...")
    test_complete_workflow(results)
    
    # Print results
    results.print_summary()
    
    # Return exit code based on results
    return 0 if results.failed == 0 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)