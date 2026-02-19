import asyncio
import re
import requests
import io
from contextlib import redirect_stdout
from playwright.async_api import async_playwright
from telegram_alert import send_telegram_alert

URL = "http://9/Scada-LTS/"
WATCHLIST = "1"
USERNAME = "admin"
PASSWORD = "admin"

POINTS_TO_CHECK = [
    "DATA PLC1 - high_1", "DATA PLC1 - Level", "DATA PLC1 - low_1", "DATA PLC1 - overflow",
    "DATA PLC1 - Pump", "DATA PLC1 - underflow", "DATA PLC1 - Valve",
    "DATA PLC2 - high_2", "DATA PLC2 - Level", "DATA PLC2 - low_2", "DATA PLC2 - overflow",
    "DATA PLC2 - Request", "DATA PLC2 - underflow",
    "DATA PLC3 - high_3", "DATA PLC3 - Level", "DATA PLC3 - low_3", "DATA PLC3 - overflow",
    "DATA PLC3 - Pump", "DATA PLC3 - undeflow",
    "Input High 1 - 1 High Input", "Low Input 1 - 1 Low Input",
    "PLC2 - 2HighInput", "PLC2 - 2LowInput",
    "PLC3 - HIGH3", "PLC3 - LOW3"
]

POINTS_OF_INTEREST = [
    "DATA PLC1 - Level",
    "DATA PLC2 - Level",
    "DATA PLC3 - Level"
]

def check_scadabr_reachable(url=URL):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"[1] [+] SCADALTS is reachable at {url}")
            return True
        else:
            print(f"[1] [!] SCADALTS responded with status code {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"[1] [✘] Could not connect to {url} ({e})")
        return False

def attempt_scadabr_login(url=URL, username=USERNAME, password=PASSWORD):
    login_url = url + "login.htm"
    payload = {"username": username, "password": password}
    try:
        with requests.Session() as session:
            response = session.post(login_url, data=payload, timeout=5)
            if "logout" in response.text.lower():
                print(f"[2] [+] Login attempt with {username}/{password} succeeded at {login_url}")
                return True
            else:
                print(f"[2] [!] Login attempt with {username}/{password} failed")
                return False
    except requests.RequestException as e:
        print(f"[2] [✘] Could not connect to {login_url} ({e})")
        return False

def extract_points_and_values_from_text(text):
    pattern = r"(DATA PLC[^\t]+)\t([\d.]+)\t"
    matches = re.findall(pattern, text)
    return [[name.strip(), value.strip()] for name, value in matches]

async def check_points_presence(page):
    await page.wait_for_timeout(2000)
    body_text = await page.inner_text("body")
    missing = [p for p in POINTS_TO_CHECK if p not in body_text]
    if missing:
        print(f"[3] [!] Missing points:")
        for m in missing:
            print(f"    - {m}")
        return False
    else:
        print("[3] [+] All points are present on the page.")
        return True

async def read_and_compare_points(page):
    await page.wait_for_timeout(2000)
    body_text_first = await page.inner_text("body")
    points_first = extract_points_and_values_from_text(body_text_first)
    filtered_first = [row for row in points_first if row[0] in POINTS_OF_INTEREST]
    print("[4] [*] First read:")
    for p in filtered_first:
        print(f"    {p[0]} = {p[1]}")

    await asyncio.sleep(5)
    await page.reload() 
    await page.wait_for_timeout(3000)
    body_text_second = await page.inner_text("body")
    points_second = extract_points_and_values_from_text(body_text_second)
    filtered_second = [row for row in points_second if row[0] in POINTS_OF_INTEREST]
    print("[4] [*] Second read:")
    for p in filtered_second:
        print(f"    {p[0]} = {p[1]}")

    print("[4] [+] Checking for deltas:")
    any_delta = False
    for first, second in zip(filtered_first, filtered_second):
        name_first, val_first = first
        name_second, val_second = second
        if name_first == name_second:
            delta = float(val_second) - float(val_first)
            print(f"    {name_first}: {val_first} -> {val_second} (delta = {delta})")
            if delta != 0:
                any_delta = True
        else:
            print(f"    [!] Name mismatch: {name_first} != {name_second}")
            return False
    return any_delta

async def full_check_scadabr():
    if not check_scadabr_reachable():
        return False
    if not attempt_scadabr_login():
        return False
        
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            
            await page.goto(URL + "login.htm")
            await page.fill('input[name="username"]', USERNAME)
            await page.fill('input[name="password"]', PASSWORD)
            await page.press('input[name="password"]', 'Enter')
            await page.wait_for_timeout(2000)

          
            print("--- Przechodzenie do watch_list.shtm ---")
            await page.goto(URL + "watch_list.shtm")
            await page.wait_for_timeout(2000)

            await populate_watchlist(page)

            
            points_ok = await check_points_presence(page)
            if not points_ok:
                return False

            
            deltas_changed = await read_and_compare_points(page)
            if deltas_changed:
                print("[4] [+] Delta detected, returning True")
                return True
            else:
                print("[4] [!] No delta detected, returning False")
                return False

        except Exception as e:
            print(f"[✘] Error during Playwright check: {e}")
            return False
        finally:
            await browser.close()

def escape_html(text):
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


async def populate_watchlist(page):
    
    print("--- [SETUP] Watchlist (Bypass) ---")
    
    
    points_to_add = [
        "DATA PLC1 - Level",
        "DATA PLC2 - Level",
        "DATA PLC3 - Level"
    ]
    
    try:
      
        await page.wait_for_timeout(3000)
        
        for point_name in points_to_add:
            
            point_locator = page.get_by_text(point_name, exact=True).first
            
            if await point_locator.count() > 0:
                await point_locator.click()
                print(f"Sukces: Wyklikano '{point_name}'")
                
        
                await page.wait_for_timeout(800) 
            else:
                print(f"Błąd: Nie widzę punktu '{point_name}' na liście po lewej!")
                
        print("Zakończono dodawanie punktów. Czekam na stabilizację tabeli...")
        await page.wait_for_timeout(2000)
        return True
        
    except Exception as e:
        print(f"Krytyczny błąd podczas wyklikiwania punktów: {e}")
        return False
        
if __name__ == "__main__":
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = asyncio.run(full_check_scadabr())

    captured_output = buffer.getvalue()
    print(captured_output)

    if result:
        print("\n✅ FINAL RESULT: True")
    else:
        print("\n❌ FINAL RESULT: False")
        safe_output = escape_html(captured_output.strip())
        message = (
            "<b>SCADAbr ALERT</b>\n"
            "❌ <b>FINAL RESULT: False</b>\n\n"
            "<b>Output:</b>\n"
            f"<pre>{safe_output[-3500:]}</pre>"
        )
        asyncio.run(send_telegram_alert(message))
