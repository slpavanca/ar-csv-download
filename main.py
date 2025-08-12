#!/usr/bin/env python3
import os
import re
import shutil
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

def run():
    LOGIN = os.environ.get("AR_LOGIN")
    PASSWORD = os.environ.get("AR_PASSWORD")

    # Direct artifacts folder for GitHub Actions
    SAVE_DIR = os.path.abspath("./artifacts")
    TEMP_DIR = os.path.abspath("./downloads")  # Temporary download location
    HEADLESS = os.environ.get("HEADLESS", "1") != "0"

    if not LOGIN or not PASSWORD:
        print("ERROR: set AR_LOGIN and AR_PASSWORD environment variables in GitHub repo Secrets")
        return

    # Create folders
    os.makedirs(SAVE_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            # --- Login ---
            page.goto("https://arll.artravels.in/")
            page.fill('input[name="login"]', LOGIN)
            page.fill('input[name="password"]', PASSWORD)
            page.click('input#login_button')
            page.wait_for_load_state("networkidle")

            # --- Navigate to Report ---
            page.click('a.header-menu-bar')
            page.click('a#reports_id')
            page.click('a[id="3"]')

            page.evaluate("""
                () => {
                    const el = document.querySelector('#report_id');
                    el.value = '147';
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """)
            page.evaluate("""
                () => {
                    const el = document.querySelector('#report_service_all');
                    el.value = '-1';
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """)
            page.wait_for_function("""
                () => {
                    const el = document.querySelector('#report_coach_id');
                    return el && el.options.length > 1;
                }
            """)
            page.click("#report_coach_id_chosen .chosen-single")
            page.locator("ul.chosen-results li", has_text="- All -").click()

            page.wait_for_function("""
                () => {
                    const el = document.querySelector('#hub_options');
                    return el && el.options.length > 1;
                }
            """)
            page.evaluate("""
                () => {
                    const el = document.querySelector('#hub_options');
                    el.value = '1';
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            """)
            page.wait_for_function("""
                () => {
                    const el = document.querySelector('#report_date_range');
                    return el && el.options.length > 1;
                }
            """)
            page.click("#report_date_range_chosen .chosen-single")
            page.locator("ul.chosen-results li", has_text="Yesterday").click()
            page.wait_for_timeout(2000)

            # --- Run report & download CSV ---
            page.click('input[type="submit"][value="Run Report"]')
            page.wait_for_selector("table#report_results", timeout=15000)
            page.wait_for_selector("a.btn.btn-primary.hide_for_print", timeout=15000)

            with page.expect_download() as detailed_download:
                page.locator("a.btn.btn-primary.hide_for_print", has_text="Show Detailed View (CSV)").click()
            download = detailed_download.value

            original_filename = download.suggested_filename
            temp_path = os.path.join(TEMP_DIR, original_filename)
            download.save_as(temp_path)
            print("📥 Downloaded to temp folder:", temp_path)

            # --- Rename and move to artifacts ---
            match = re.search(r"([A-Za-z]+) (\d{4}) (\d{2})", original_filename)
            if match:
                month_str, year_str, day_str = match.groups()
                try:
                    original_date = datetime.strptime(f"{day_str} {month_str} {year_str}", "%d %B %Y")
                    new_date = original_date - timedelta(days=1)
                    new_date_str = new_date.strftime("%B %Y %d")
                    old_date_str = f"{month_str} {year_str} {day_str}"
                    new_filename = original_filename.replace(old_date_str, new_date_str)
                    new_filename = f"AR {new_filename}"
                    final_path = os.path.join(SAVE_DIR, new_filename)
                    shutil.move(temp_path, final_path)
                    print(f"✅ Renamed and moved to artifacts: {final_path}")
                except Exception as e:
                    print("❌ Failed to parse date or rename:", e)
                    shutil.move(temp_path, os.path.join(SAVE_DIR, original_filename))
            else:
                print("❌ Date not found in filename. Moving with original name.")
                shutil.move(temp_path, os.path.join(SAVE_DIR, original_filename))

        except Exception as e:
            print("ERROR during run:", str(e))
        finally:
            browser.close()

if __name__ == "__main__":
    run()
