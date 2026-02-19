import time
import io
import asyncio
from contextlib import redirect_stdout
from playwright.sync_api import sync_playwright

from telegram_alert import send_telegram_alert

URL = "http://" 

STATUS_TARGETS = [
    "#status-text-PLC1-\\(T-201-Control\\)", 
    "#card-PLC2-\\(T-202-Monitor\\)",       
    "#card-PLC3-\\(T-203-Control\\)"        
]

LEVEL_TARGETS = [
    "#data-container-PLC1-\\(T-201-Control\\)", # Index 0
    "#data-container-PLC2-\\(T-202-Monitor\\)", # Index 1
    "#data-container-PLC3-\\(T-203-Control\\)"  # Index 2
]



def escape_html(text):
    """Zabezpiecza logi, aby nie psuły formatowania HTML w Telegramie"""
    if text:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return ""

def check_connected(page):
    print("--- [CHECK] Connection Status ---")
    all_connected = True
    
    for selector in STATUS_TARGETS:
        if page.locator(selector).count() == 0:
            print(f"Error: Could not find element {selector}")
            all_connected = False
            continue
        
        text_content = page.inner_text(selector)
        if "Connected" not in text_content:
            print(f"Error: Element {selector} has status '{text_content}'")
            all_connected = False
            
    if all_connected:
        print("Status: All tanks are CONNECTED.")
        return True
    else:
        print("Status: Connection ERROR.")
        return False

def check_level(page):
    print("\n--- [CHECK] Water Level ---")
    levels_list = []

    for i, selector in enumerate(LEVEL_TARGETS):
        tank_index = i + 1 
        current_val = -1  
        container = page.locator(selector)
        
        if container.count() > 0:
            value_locator = container.get_by_text("Water Level").locator("xpath=following-sibling::span")
            
            if value_locator.count() > 0:
                raw_text = value_locator.inner_text() 
                try:
                    if "/" in raw_text:
                        current_val = int(raw_text.split('/')[0].strip())
                    else:
                        current_val = int(raw_text.strip())
                        
                    print(f"Tank {tank_index}: {current_val}%")
                except ValueError:
                    print(f"Tank {tank_index}: Conversion error ('{raw_text}')")
            else:
                print(f"Tank {tank_index}: Could not find value span")
        else:
            print(f"Tank {tank_index}: Could not find tank container")
        
        levels_list.append(current_val)
            
    return levels_list

def check_delta(t1, t2):
    print("\n--- [CHECK] Flow Delta ---")
    if len(t1) != 3 or len(t2) != 3:
        print("Error: Table length mismatch")
        return False
    
    if t1 == t2:
        print(f"WARNING: No water flow detected! Values static: {t1}")
        return False
    else:
        print(f"Flow detected. Change: {t1} -> {t2}")
        return True


def run_checks():
    """Wykonuje testy i zwraca True (Sukces) lub False (Awaria)"""
    final_status = False
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            print(f"Connecting to {URL}...")
            page.goto(URL, timeout=10000)
            page.wait_for_timeout(2000) 
            
            if not check_connected(page):
                return False 
            
            water_levels_0 = check_level(page)
    
            print("Waiting 5 seconds for data update...")
            time.sleep(5)
            
            water_levels_1 = check_level(page)
        
            if check_delta(water_levels_0, water_levels_1):
                final_status = True
            else:
                final_status = False
                
        except Exception as e:
            print(f"CRITICAL EXCEPTION: {e}")
            final_status = False
        finally:
            browser.close()
            
    return final_status


def main():
    buffer = io.StringIO()
    
    with redirect_stdout(buffer):
        success = run_checks()
        
    captured_output = buffer.getvalue()
    
    print(captured_output)

    if not success:
        print("\n❌ SYSTEM FAILURE - Sending Telegram Alert...")
       
        safe_logs = escape_html(captured_output.strip())
        short_logs = safe_logs[-3000:] 
        
        message = (
            "<b>🚨 ICS HONEYPOT ALERT 🚨</b>\n"
            "❌ <b>Result: FAIL</b>\n"
            "System detected an anomaly (Disconnection or Static Water Level).\n\n"
            "<b>Logs:</b>\n"
            f"<pre>{short_logs}</pre>"
        )
        try:
            asyncio.run(send_telegram_alert(message))
        except Exception as e:
            print(f"Failed to run async telegram alert: {e}")
            
    else:
        print("\n✅ SYSTEM HEALTHY - No alert needed.")

if __name__ == "__main__":
    main()