from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

with sync_playwright() as p:
    # Launch browser (use headless=False if you want to see the bypass)
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    
    # Apply stealth patterns to hide 'navigator.webdriver' and mimic Chrome
    stealth_sync(page)
    
    # Navigate and wait for the page to be 'human-readable'
    page.goto('https://www.google.com/search?q=AMD+7900+XT+price')
    page.wait_for_load_state('networkidle')
    
    # Save the now-clean result to your 8TB G: Drive
    page.screenshot(path='/app/test_target.png')
    browser.close()
    print("Success! Screenshot saved without the robot screen.")