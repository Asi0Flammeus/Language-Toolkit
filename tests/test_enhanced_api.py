#!/usr/bin/env python3
"""
Test script for enhanced API with formatting preservation
"""

import requests
import json
import time
from pathlib import Path

API_BASE = "http://localhost:8000"
AUTH_TOKEN = "token_admin_abc123def456"

def test_pptx_translation():
    """Test PPTX translation with formatting preservation"""
    
    print("🧪 Testing Enhanced PPTX Translation API")
    print("=" * 50)
    
    # Check if test file exists
    test_file = Path("test-app/ECO102-FR-V001-2.1.pptx")
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return
    
    print(f"📁 Using test file: {test_file}")
    
    # 1. Submit translation request
    print("\n1️⃣ Submitting translation request...")
    try:
        with open(test_file, 'rb') as f:
            files = {'files': f}
            data = {
                'source_lang': 'en',
                'target_lang': 'fr'
            }
            headers = {'Authorization': f'Bearer {AUTH_TOKEN}'}
            
            response = requests.post(f"{API_BASE}/translate/pptx", 
                                   files=files, data=data, headers=headers)
        
        if response.status_code == 200:
            task_data = response.json()
            task_id = task_data['task_id']
            print(f"✅ Task created: {task_id}")
        else:
            print(f"❌ Failed to submit: {response.status_code} - {response.text}")
            return
            
    except Exception as e:
        print(f"❌ Error submitting request: {e}")
        return
    
    # 2. Monitor task progress
    print(f"\n2️⃣ Monitoring task progress...")
    max_wait = 300  # 5 minutes
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_BASE}/tasks/{task_id}", 
                                  headers={'Authorization': f'Bearer {AUTH_TOKEN}'})
            
            if response.status_code == 200:
                task_status = response.json()
                status = task_status['status']
                print(f"📋 Status: {status}")
                
                if status == 'completed':
                    result_files = task_status.get('result_files', [])
                    print(f"✅ Translation completed!")
                    print(f"📄 Result files: {len(result_files)}")
                    for i, file_path in enumerate(result_files):
                        print(f"   {i}: {Path(file_path).name}")
                    break
                elif status == 'failed':
                    error = task_status.get('error', 'Unknown error')
                    print(f"❌ Task failed: {error}")
                    return
                else:
                    time.sleep(5)  # Wait 5 seconds before checking again
            else:
                print(f"❌ Error checking status: {response.status_code}")
                return
                
        except Exception as e:
            print(f"❌ Error monitoring task: {e}")
            return
    else:
        print(f"⏰ Task did not complete within {max_wait} seconds")
        return
    
    # 3. Test download
    print(f"\n3️⃣ Testing download...")
    try:
        download_response = requests.get(f"{API_BASE}/download/{task_id}",
                                       headers={'Authorization': f'Bearer {AUTH_TOKEN}'},
                                       stream=True)
        
        if download_response.status_code == 200:
            content_type = download_response.headers.get('content-type', '')
            content_disposition = download_response.headers.get('content-disposition', '')
            
            print(f"📥 Download successful!")
            print(f"📋 Content-Type: {content_type}")
            print(f"📋 Content-Disposition: {content_disposition}")
            
            # Check if it's a direct PPTX file or ZIP
            if 'application/vnd.openxmlformats-officedocument.presentationml.presentation' in content_type:
                print("🎉 SUCCESS: Direct PPTX file download!")
                print("✅ Formatting preservation should be maintained")
            elif 'application/zip' in content_type:
                print("📦 ZIP file download (fallback)")
            else:
                print(f"🤔 Unexpected content type: {content_type}")
                
            # Save the file for inspection
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"')
            else:
                filename = f"result_{task_id}.pptx"
            
            with open(filename, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"💾 Saved as: {filename}")
            
        else:
            print(f"❌ Download failed: {download_response.status_code}")
            
    except Exception as e:
        print(f"❌ Error downloading: {e}")
    
    # 4. Cleanup
    print(f"\n4️⃣ Cleaning up...")
    try:
        cleanup_response = requests.delete(f"{API_BASE}/tasks/{task_id}",
                                         headers={'Authorization': f'Bearer {AUTH_TOKEN}'})
        if cleanup_response.status_code == 200:
            print("🧹 Task cleaned up successfully")
        else:
            print(f"⚠️ Cleanup warning: {cleanup_response.status_code}")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")
    
    print("\n🏁 Test completed!")

if __name__ == "__main__":
    test_pptx_translation()