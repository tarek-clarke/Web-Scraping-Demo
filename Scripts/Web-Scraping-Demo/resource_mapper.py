import torch_directml
import requests
from bs4 import BeautifulSoup
import time

def resource_mapper(url):
    print(f"\n--- Stimulus Analysis: {url} ---")
    start_time = time.time()
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        # Added status code check
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- DEBUG SECTION ---
        page_title = soup.title.string.strip() if soup.title else "No Title Found"
        print(f"DEBUG: HTTP Status = {response.status_code}")
        print(f"DEBUG: Page Title = '{page_title}'")
        # ---------------------

        tag_count = len(soup.find_all())
        text_length = len(soup.get_text())
        density = tag_count / (text_length + 1)
        
        # Expanded checks for dynamic content
        is_dynamic = any(attr in response.text for attr in ['__NEXT_DATA__', 'root-app', 'chunk.js', 'airbnb-bootstrap'])

        print(f"Metrics: Tags={tag_count}, Text={text_length}, Density={density:.4f}")

        # LOGIC UPDATE: If text is suspiciously low (<1000 chars) for a complex URL, force GPU
        if density < 0.01 or is_dynamic or text_length < 1000:
            print("DECISION: Mapping to AMD Radeon 7900 XT (DirectML Path)")
            device = torch_directml.device()
            status = "GPU_ACCELERATED"
        else:
            print("DECISION: Mapping to CPU (BeautifulSoup Path)")
            status = "CPU_STATIC"

        exec_time = time.time() - start_time
        print(f"Infrastructure Logic complete in {exec_time:.2f}s | Status: {status}")
        return status

    except Exception as e:
        print(f"Critical Infrastructure Failure: {e}")
        return "ERROR"

if __name__ == "__main__":
    target_url = input("Enter the target URL to map: ")
    resource_mapper(target_url)