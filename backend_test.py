import requests
import sys
import json
from datetime import datetime

class VidSaverAPITester:
    def __init__(self, base_url="https://clip-fetch-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def test_api_root(self):
        """Test API root endpoint"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Response: {data}"
            self.log_test("API Root", success, details)
            return success
        except Exception as e:
            self.log_test("API Root", False, str(e))
            return False

    def test_status_endpoints(self):
        """Test status check endpoints"""
        # Test POST /status
        try:
            payload = {"client_name": "test_client"}
            response = requests.post(f"{self.api_url}/status", json=payload, timeout=10)
            success = response.status_code == 200
            details = f"POST Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", ID: {data.get('id', 'N/A')}"
            self.log_test("POST Status Check", success, details)
        except Exception as e:
            self.log_test("POST Status Check", False, str(e))

        # Test GET /status
        try:
            response = requests.get(f"{self.api_url}/status", timeout=10)
            success = response.status_code == 200
            details = f"GET Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Count: {len(data)}"
            self.log_test("GET Status Check", success, details)
        except Exception as e:
            self.log_test("GET Status Check", False, str(e))

    def test_video_info(self):
        """Test video info endpoint with a real YouTube URL"""
        test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll - short video
            "https://youtu.be/dQw4w9WgXcQ"  # Short URL format
        ]
        
        for i, url in enumerate(test_urls):
            try:
                payload = {"url": url}
                response = requests.post(f"{self.api_url}/video/info", json=payload, timeout=30)
                success = response.status_code == 200
                details = f"Status: {response.status_code}"
                
                if success:
                    data = response.json()
                    details += f", Title: '{data.get('title', 'N/A')[:50]}...'"
                    details += f", Formats: {len(data.get('formats', []))}"
                    details += f", Duration: {data.get('duration', 0)}s"
                else:
                    try:
                        error_data = response.json()
                        details += f", Error: {error_data.get('detail', 'Unknown error')}"
                    except:
                        details += f", Raw response: {response.text[:100]}"
                
                self.log_test(f"Video Info Test {i+1}", success, details)
                
                # If successful, store video info for download test
                if success and i == 0:  # Use first successful result
                    self.test_video_data = data
                    return True
                    
            except Exception as e:
                self.log_test(f"Video Info Test {i+1}", False, str(e))
        
        return False

    def test_video_download(self):
        """Test video download endpoint"""
        if not hasattr(self, 'test_video_data'):
            self.log_test("Video Download", False, "No video info available for download test")
            return False
            
        try:
            # Use the first available format
            formats = self.test_video_data.get('formats', [])
            if not formats:
                self.log_test("Video Download", False, "No formats available")
                return False
                
            format_id = formats[0]['format_id']
            payload = {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "format_id": format_id
            }
            
            response = requests.post(f"{self.api_url}/video/download", json=payload, timeout=60)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if success:
                data = response.json()
                details += f", Download ID: {data.get('download_id', 'N/A')}"
                details += f", Filename: {data.get('filename', 'N/A')}"
                details += f", Status: {data.get('status', 'N/A')}"
                
                # Store filename for file serving test
                self.download_filename = data.get('filename')
            else:
                try:
                    error_data = response.json()
                    details += f", Error: {error_data.get('detail', 'Unknown error')}"
                except:
                    details += f", Raw response: {response.text[:100]}"
            
            self.log_test("Video Download", success, details)
            return success
            
        except Exception as e:
            self.log_test("Video Download", False, str(e))
            return False

    def test_file_serving(self):
        """Test file serving endpoint"""
        if not hasattr(self, 'download_filename'):
            self.log_test("File Serving", False, "No downloaded file available for serving test")
            return False
            
        try:
            response = requests.get(f"{self.api_url}/video/file/{self.download_filename}", timeout=30)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if success:
                content_length = response.headers.get('content-length', 'Unknown')
                content_type = response.headers.get('content-type', 'Unknown')
                details += f", Size: {content_length} bytes, Type: {content_type}"
            else:
                details += f", Error: File not found or server error"
            
            self.log_test("File Serving", success, details)
            return success
            
        except Exception as e:
            self.log_test("File Serving", False, str(e))
            return False

    def test_invalid_requests(self):
        """Test error handling with invalid requests"""
        # Test invalid URL for video info
        try:
            payload = {"url": "https://invalid-url.com/video"}
            response = requests.post(f"{self.api_url}/video/info", json=payload, timeout=15)
            success = response.status_code == 400  # Should return error
            details = f"Status: {response.status_code} (expected 400)"
            self.log_test("Invalid URL Handling", success, details)
        except Exception as e:
            self.log_test("Invalid URL Handling", False, str(e))

        # Test missing file
        try:
            response = requests.get(f"{self.api_url}/video/file/nonexistent.mp4", timeout=10)
            success = response.status_code == 404  # Should return not found
            details = f"Status: {response.status_code} (expected 404)"
            self.log_test("Missing File Handling", success, details)
        except Exception as e:
            self.log_test("Missing File Handling", False, str(e))

    def run_all_tests(self):
        """Run all API tests"""
        print(f"🚀 Starting VidSaver API Tests")
        print(f"📍 Testing API at: {self.api_url}")
        print("=" * 60)
        
        # Test basic connectivity
        if not self.test_api_root():
            print("❌ API root test failed - stopping further tests")
            return False
            
        # Test status endpoints
        self.test_status_endpoints()
        
        # Test video operations
        video_info_success = self.test_video_info()
        if video_info_success:
            download_success = self.test_video_download()
            if download_success:
                self.test_file_serving()
        
        # Test error handling
        self.test_invalid_requests()
        
        # Print summary
        print("=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print("⚠️  Some tests failed - check details above")
            return False

def main():
    tester = VidSaverAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": tester.tests_run,
        "passed_tests": tester.tests_passed,
        "success_rate": f"{(tester.tests_passed/tester.tests_run*100):.1f}%" if tester.tests_run > 0 else "0%",
        "test_details": tester.test_results
    }
    
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())