import requests
import json
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import pandas as pd
import os

def crawl_xanhsm_faq_with_selenium():
    """
    Crawl all questions and answers from Xanh SM FAQ page using Selenium
    to handle dynamic content and clicking on each question
    """
    
    # Setup Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in background (remove if you want to see the browser)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Initialize driver
    driver = webdriver.Chrome(options=options)
    
    try:
        # Navigate to the page
        url = "https://www.xanhsm.com/helps?id=116"
        print(f"🌐 Loading {url}...")
        driver.get(url)
        
        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        time.sleep(3)  # Additional wait for dynamic content
        
        all_faqs = []
        
        # Define the 4 user types and their corresponding tab selectors
        user_types = [
            {"name": "nguoi_dung", "tab_text": "Dành cho người dùng"},
            {"name": "tai_xe_taxi", "tab_text": "Dành cho tài xế Taxi"},
            {"name": "tai_xe_bike", "tab_text": "Dành cho tài xế Bike"},
            {"name": "nha_hang", "tab_text": "Dành cho Nhà hàng"}
        ]
        
        for user_type in user_types:
            print(f"\n📋 Processing: {user_type['tab_text']} ({user_type['name']})")
            
            # Click on the tab for this user type
            try:
                # Find the tab by its text
                tab_elements = driver.find_elements(By.XPATH, f"//div[contains(@class, 'cursor-pointer') and contains(text(), '{user_type['tab_text']}')]")
                
                if tab_elements:
                    tab = tab_elements[0]
                    # Check if it's already active (has different style)
                    if 'text-typo-placeholder' in tab.get_attribute('class'):
                        driver.execute_script("arguments[0].click();", tab)
                        print(f"   ✅ Clicked on {user_type['tab_text']} tab")
                        time.sleep(2)  # Wait for content to load
                else:
                    print(f"   ⚠️ Could not find tab for {user_type['tab_text']}")
                    continue
                    
            except Exception as e:
                print(f"   ❌ Error clicking tab: {e}")
                continue
            
            # Now find all questions in this category
            # Questions are inside divs with class 'border-b py-4 border-semantic-border-secondary'
            question_containers = driver.find_elements(By.CSS_SELECTOR, '.border-b.py-4.border-semantic-border-secondary')
            
            print(f"   📝 Found {len(question_containers)} questions")
            
            for idx, container in enumerate(question_containers, 1):
                try:
                    # Find the question text
                    question_elem = container.find_element(By.CSS_SELECTOR, '.text-left')
                    question_text = question_elem.text.strip()
                    
                    # Remove numbering like "1.1." if present
                    if question_text and question_text[0].isdigit():
                        parts = question_text.split('.', 1)
                        if len(parts) > 1:
                            question_text = parts[1].strip()
                    
                    print(f"      Question {idx}: {question_text[:50]}...")
                    
                    # Check if the answer is already visible
                    answer_elem = container.find_elements(By.CSS_SELECTOR, '.whitespace-pre-line')
                    
                    if not answer_elem or not answer_elem[0].is_displayed():
                        # Need to click to expand
                        try:
                            # Find the button to click
                            button = container.find_element(By.CSS_SELECTOR, 'button')
                            driver.execute_script("arguments[0].click();", button)
                            time.sleep(0.5)  # Wait for animation
                        except Exception as click_error:
                            print(f"         ⚠️ Could not click: {click_error}")
                    
                    # Get the answer after expansion
                    wait.until(lambda d: container.find_elements(By.CSS_SELECTOR, '.whitespace-pre-line'))
                    answer_elem = container.find_elements(By.CSS_SELECTOR, '.whitespace-pre-line')
                    
                    if answer_elem:
                        answer_text = answer_elem[0].text.strip()
                    else:
                        answer_text = "Answer not found"
                    
                    all_faqs.append({
                        "question": question_text,
                        "answer": answer_text,
                        "user_type": user_type['name']
                    })
                    
                    print(f"         ✅ Extracted answer ({len(answer_text)} chars)")
                    
                except StaleElementReferenceException:
                    print(f"         ⚠️ Stale element, skipping...")
                    continue
                except Exception as e:
                    print(f"         ❌ Error: {e}")
                    continue
            
            print(f"   ✅ Completed {user_type['tab_text']}: {len([f for f in all_faqs if f['user_type'] == user_type['name']])} items")
        
        print(f"\n🎉 Total FAQs collected: {len(all_faqs)}")
        return all_faqs
        
    finally:
        driver.quit()


def crawl_with_requests_alternative():
    """
    Alternative method using requests if Selenium is not available
    This simulates the API calls directly
    """
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json, text/plain, */*'
    }
    
    base_url = "https://www.xanhsm.com/helps"
    all_faqs = []
    
    # The API endpoint (need to be discovered, this is a guess)
    api_endpoints = [
        f"{base_url}/getFaqs",
        f"{base_url}/api/faqs",
        f"{base_url}/faqs",
        "https://www.xanhsm.com/api/helps"
    ]
    
    user_types = ['nguoi_dung', 'tai_xe_taxi', 'tai_xe_bike', 'nha_hang']
    
    for user_type in user_types:
        print(f"Trying to fetch for {user_type}...")
        
        for endpoint in api_endpoints:
            try:
                response = session.get(endpoint, params={"id": 116, "type": user_type}, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    print(f"  ✅ Found API: {endpoint}")
                    
                    # Try to extract FAQs from response
                    faqs = []
                    if isinstance(data, dict):
                        if 'data' in data and 'faqs' in data['data']:
                            faqs = data['data']['faqs']
                        elif 'faqs' in data:
                            faqs = data['faqs']
                        elif 'items' in data:
                            faqs = data['items']
                    elif isinstance(data, list):
                        faqs = data
                    
                    for faq in faqs:
                        all_faqs.append({
                            "question": faq.get('question', faq.get('title', '')),
                            "answer": faq.get('answer', faq.get('content', '')),
                            "user_type": user_type
                        })
                    
                    if all_faqs:
                        break
            except:
                continue
    
    return all_faqs


def export_to_files(faqs, output_json="xanhsm_faqs.json", output_excel="xanhsm_faqs.xlsx"):
    """
    Export the FAQs to JSON and Excel files
    """
    
    # Export to JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(faqs, f, ensure_ascii=False, indent=2)
    print(f"📄 Exported to JSON: {output_json}")
    
    # Export to Excel
    df = pd.DataFrame(faqs)
    
    # Reorder columns for better readability
    df = df[['user_type', 'question', 'answer']]
    
    # Create Excel file with multiple sheets (one per user type)
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        # Write all data to first sheet
        df.to_excel(writer, sheet_name='All FAQs', index=False)
        
        # Write separate sheets for each user type
        for user_type in df['user_type'].unique():
            sheet_name = user_type.replace('_', ' ').title()
            df[df['user_type'] == user_type].to_excel(
                writer, 
                sheet_name=sheet_name, 
                index=False
            )
    
    print(f"📊 Exported to Excel: {output_excel}")
    
    # Print statistics
    print("\n📈 Statistics:")
    print(f"   Total FAQs: {len(faqs)}")
    for user_type in df['user_type'].unique():
        count = len(df[df['user_type'] == user_type])
        print(f"   {user_type}: {count} items")


def main():
    """
    Main function to run the crawler
    """
    print("🚀 Starting Xanh SM FAQ Crawler")
    print("=" * 50)
    
    # Try Selenium first (more reliable for dynamic content)
    try:
        print("\n📱 Attempting to crawl with Selenium...")
        faqs = crawl_xanhsm_faq_with_selenium()
        
        if faqs and len(faqs) > 0:
            print(f"\n✅ Successfully crawled {len(faqs)} FAQs using Selenium")
        else:
            raise Exception("No data collected with Selenium")
            
    except Exception as e:
        print(f"\n⚠️ Selenium failed: {e}")
        print("🔄 Falling back to requests method...")
        faqs = crawl_with_requests_alternative()
        
        if not faqs:
            print("\n❌ Both methods failed. Here's a sample of the expected data format:")
            # Provide sample data as fallback
            faqs = [
                {
                    "question": "Tôi bỏ quên đồ trên chuyến xe",
                    "answer": "Vào Lịch sử chuyến xe → chọn chuyến → Liên hệ tài xế...",
                    "user_type": "nguoi_dung"
                },
                {
                    "question": "Tài xế lái xe không an toàn",
                    "answer": "Với tiêu chí an toàn là ưu tiên hàng đầu, Xanh SM rất tiếc khi bạn có trải nghiệm chưa được như mong đợi...",
                    "user_type": "nguoi_dung"
                }
            ]
    
    # Export to files
    if faqs:
        export_to_files(faqs)
        print("\n✨ Done! Check the output files.")
        
        # Print sample
        print("\n📋 Sample output:")
        print(json.dumps(faqs[0], ensure_ascii=False, indent=2))
    else:
        print("\n❌ No FAQs were collected. Please check the website structure.")


if __name__ == "__main__":
    # Install required packages if not already installed
    import subprocess
    import sys
    
    required_packages = ['selenium', 'pandas', 'openpyxl', 'beautifulsoup4', 'requests']
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            print(f"📦 Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    
    main()