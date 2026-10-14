import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    screenshots_dir = Path("screenshots").resolve()
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    print("Launching browser with Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("Navigating to http://localhost:5173/assistant...")
        page.goto("http://localhost:5173/assistant", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        # 1. Initial State Light Mode
        page.evaluate("document.documentElement.classList.remove('dark')")
        page.wait_for_timeout(500)
        p1 = screenshots_dir / "assistant_empty_light_1440.png"
        page.screenshot(path=str(p1))
        print(f"Captured: {p1.name} ({p1.stat().st_size:,} bytes)")

        # 2. Initial State Dark Mode
        page.evaluate("document.documentElement.classList.add('dark')")
        page.wait_for_timeout(500)
        p2 = screenshots_dir / "assistant_empty_dark_1440.png"
        page.screenshot(path=str(p2))
        print(f"Captured: {p2.name} ({p2.stat().st_size:,} bytes)")

        # Switch back to light mode for conversation interactions
        page.evaluate("document.documentElement.classList.remove('dark')")
        page.wait_for_timeout(300)

        chips = [
            "What changed since yesterday?",
            "Which region lost the most Commit?",
            "Top 10 opportunities in Middle East",
            "How many deals are Pending Approval?",
            "Show history of 006Qp00000as0WCIAY",
        ]

        for chip_text in chips:
            print(f"Asking chip: '{chip_text}'...")
            # Try finding button by text
            btn = page.locator(f"button:has-text('{chip_text}')").first
            if btn.is_visible():
                btn.click()
            else:
                input_el = page.locator("#assistant-chat-input")
                input_el.fill(chip_text)
                page.locator("#assistant-chat-send").click()
            
            # Wait for response to stream and complete
            page.wait_for_timeout(4000)

        # 3. Full Conversation in Light Mode
        p3 = screenshots_dir / "assistant_conversation_light_1440.png"
        page.screenshot(path=str(p3))
        print(f"Captured: {p3.name} ({p3.stat().st_size:,} bytes)")

        # 4. Full Conversation in Dark Mode
        page.evaluate("document.documentElement.classList.add('dark')")
        page.wait_for_timeout(600)
        p4 = screenshots_dir / "assistant_conversation_dark_1440.png"
        page.screenshot(path=str(p4))
        print(f"Captured: {p4.name} ({p4.stat().st_size:,} bytes)")

        # 5. Docked Assistant Panel on Dashboard
        print("Navigating to http://localhost:5173/ to capture docked panel...")
        page.goto("http://localhost:5173/", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)

        toggle_btn = page.locator("#topbar-assistant-toggle")
        if toggle_btn.is_visible():
            toggle_btn.click()
            page.wait_for_timeout(1000)

        # Dark mode docked screenshot
        p5 = screenshots_dir / "assistant_docked_dark_1440.png"
        page.screenshot(path=str(p5))
        print(f"Captured: {p5.name} ({p5.stat().st_size:,} bytes)")

        # Light mode docked screenshot
        page.evaluate("document.documentElement.classList.remove('dark')")
        page.wait_for_timeout(500)
        p6 = screenshots_dir / "assistant_docked_light_1440.png"
        page.screenshot(path=str(p6))
        print(f"Captured: {p6.name} ({p6.stat().st_size:,} bytes)")

        browser.close()
        print("\nAll assistant screenshots successfully captured and saved!")

if __name__ == "__main__":
    main()
