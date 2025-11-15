""" 

Playwright (sync) script to scrape Development Application (DA) records from
Shoalhaven City Council MasterView portal for date range 01/09/2025 - 30/09/2025.

Outputs CSV with exact headers:
DA_Number,Detail_URL,Description,Submitted_Date,Decision,Categories,
Property_Address,Applicant,Progress,Fees,Documents,Contact_Council

Usage:
  pip install -r requirements.txt
  playwright install
  python scrape.py

"""

import csv
import time
import logging
from pathlib import Path
from typing import Optional
import sqlite3
DB_NAME = "shoalhaven_da.db"
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

# --- Configuration ---
START_DATE = "1/09/2025"
END_DATE = "30/09/2025"
BASE_URL = "https://www3.shoalhaven.nsw.gov.au/masterviewUI/modules/ApplicationMaster/Default.aspx"
OUTPUT_CSV = "shoalhaven_DA_2025-09-01_to_2025-09-30.csv"
HEADERS = [
    "DA_Number",
    "Detail_URL",
    "Description",
    "Submitted_Date",
    "Decision",
    "Categories",
    "Property_Address",
    "Applicant",
    "Progress",
    "Fees",
    "Documents",
    "Contact_Council",
]

# Data cleaning exact-match rules (Step 6)
FEES_EXACT = "No fees recorded against this application."
CONTACT_EXACT = "Application Is Not on exhibition, please call Council on 1300 293 111 if you require assistance."

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


# --- Helper functions ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS scraped_da (
            detail_url TEXT PRIMARY KEY,
            da_number TEXT,
            description TEXT,
            submitted_date TEXT,
            decision TEXT,
            categories TEXT,
            property_address TEXT,
            applicant TEXT,
            progress TEXT,
            fees TEXT,
            documents TEXT,
            contact_council TEXT
        )
    """)

    conn.commit()
    conn.close()


def is_scraped(url: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT detail_url FROM scraped_da WHERE detail_url = ?", (url,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def insert_record(record: dict):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO scraped_da (
            detail_url, da_number, description, submitted_date, decision,
            categories, property_address, applicant, progress, fees,
            documents, contact_council
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record["Detail_URL"],
        record["DA_Number"],
        record["Description"],
        record["Submitted_Date"],
        record["Decision"],
        record["Categories"],
        record["Property_Address"],
        record["Applicant"],
        record["Progress"],
        record["Fees"],
        record["Documents"],
        record["Contact_Council"],
    ))

    conn.commit()
    conn.close()

def export_to_csv():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM scraped_da")
    rows = cur.fetchall()
    conn.close()

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for row in rows:
            writer.writerow(row)


def safe_get_text(locator) -> str:
    """Return trimmed inner_text() or empty string if not found."""
    try:
        txt = locator.inner_text()
        return txt.strip()
    except PlaywrightTimeoutError:
        return ""
    except Exception:
        try:
            return (locator.text_content() or "").strip()
        except Exception:
            return ""


def normalize_fees_and_contact(fees_raw: str, contact_raw: str) -> (str, str):
    """Apply Step 6 cleaning rules (exact matches)."""
    fees_val = fees_raw
    contact_val = contact_raw
    if fees_raw.strip() == FEES_EXACT:
        fees_val = "Not required"
    if contact_raw.strip() == CONTACT_EXACT:
        contact_val = "Not required"
    return fees_val, contact_val


def click_agree(page: Page):
    """Try to click the 'Agree' button on the initial disclaimer page."""
    logging.info("Trying to click 'Agree' on disclaimer page...")
    # Try a few strategies for the Agree button
    agree_selector = '//input[@value="Agree"]'

    try:
        btn = page.locator(agree_selector).first
        if btn.count() > 0:
            btn.click(timeout=5000)
            logging.info(f"Clicked Agree using selector: {sel}")
            page.wait_for_load_state("networkidle", timeout=10000)
            return
    except Exception:
        logging.warning("Could not find 'Agree' button automatically.")
    # As fallback, try to press Enter in case focused control is Agree

    try:
        page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass

def select_50_per_page(page):
    page.click('.rcbReadOnly a') 
    time.sleep(1)
    page.locator('.rcbList').wait_for(state="visible") 
    page.click('.rcbList > li:nth-child(3)') 
    page.wait_for_load_state("networkidle")

def scrape_table(table):

    rows = table.locator('//tbody/tr[@class="rgRow" or @class="rgAltRow"]')
    row_count = rows.count()

    data = []
    baseurl = "https://www3.shoalhaven.nsw.gov.au/masterviewUI/modules/ApplicationMaster/"
    for i in range(row_count):
        row = rows.nth(i)
        print(row.locator('td').all_text_contents())
        showlink = baseurl + row.locator('td:nth-child(1) > a').first.get_attribute("href")
        application_id = row.locator('td:nth-child(2)').first.inner_text()
        date = row.locator('td:nth-child(3)').first.inner_text()
        address = row.locator('td:nth-child(4)').first.inner_text()
        cells = [showlink, application_id, date, address]

        data.append(cells)

    return data

def click_next_page(page):

    disabled = page.locator('//input[@type="button" and @title="Next Page" and starts-with(@onclick,"return false")]')
    if disabled.count()>0:
        return False

    locator = page.locator('//input[@type="button" and @title="Next Page"]')
    try:
        locator.click()
        print("Clicked Next Page button.")
        return True
    except:
        print("Next Page button Not Available.")
        return False


# --- Main scraping function ---
def scrape():

    init_db()
    records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        logging.info(f"Going to {BASE_URL}")
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)

        # Step 1: Click Agree
        click_agree(page)
        time.sleep(1)

        # Step 2: Click "DA Tracking" tab in top navigation
        logging.info("Clicking 'DA Tracking' tab...")
        selector_da_tracking = '//span[text()="DA Tracking"]/parent::a'


        try:
            el = page.locator(selector_da_tracking).first
            if el.count() > 0:
                el.click(timeout=8000)
                page.wait_for_load_state("networkidle", timeout=10000)
                logging.info(f"Clicked DA Tracking with selector: {selector_da_tracking}") 
        except Exception as e:
            logging.debug(f"selector {selector_da_tracking} failed: {e}")
            logging.warning("Could not click 'DA Tracking' tab.")

        time.sleep(1)

        # # Step 3: Click Advanced Search
        logging.info("Clicking 'Advanced Search'...")
        selector_advanced_search = '//span[text()="Advanced Search"]/ancestor::a'

        try:
            el = page.locator(selector_advanced_search).first
            if el.count() > 0:
                el.click(timeout=7000)
                page.wait_for_timeout(500)  # allow UI to reveal
                logging.info(f"Clicked Advanced Search with selector: {selector_advanced_search}")
        except Exception:
            logging.debug(f"selector {selector_advanced_search} failed: {e}")
            logging.warning("Could not click 'Advanced Search' tab.")

        time.sleep(0.8)

        # # Step 4: Set date range and Search
        logging.info(f"Setting date range From: {START_DATE} To: {END_DATE}") 
        selector_dates = '//table//input[@type="text" and @class="riTextBox riEnabled"]'
        try:  
            date_inputs = page.locator(selector_dates)
            print('Dateinputs count : ', date_inputs.count())
            if date_inputs.count() > 1: 
                date_inputs.first.fill(START_DATE, timeout=5000)
                time.sleep(1)
                page.locator("body").click()
                # date_inputs.nth(1).click()
                date_inputs.nth(1).fill(END_DATE, timeout=5000)
 
        except Exception as e:
            print(e)
            logging.debug(f"selector {selector_dates} failed: {e}")
            logging.warning(f"Date input filling encountered problems")

        time.sleep(0.8)

        # # Click the Search button
        logging.info("Clicking Search button...")
        selector_search = '//input[@title="Search For Property"]'

        try:
            button = page.locator(selector_search).first
            if button.count() > 0:
                button.click(timeout=8000)
                page.wait_for_load_state("networkidle", timeout=10000)
                logging.info(f"Clicked Search with selector: {selector_search}")
        except Exception:
            logging.debug(f"selector {selector_search} failed: {e}")
            logging.warning(f"Clicking on Search button encountered problems")

        time.sleep(2)

        try:
            select_50_per_page(page)
        except Exception as e:
            print(e)
            logging.warning('Failed to set page size to 50')

        time.sleep(5)


        next_page_present = True 
        while next_page_present:

            table = page.locator(".rgMasterTable")
            table.wait_for(state="visible") 

            records.extend(scrape_table(table))
            print(len(records))
            next_page_present = click_next_page(page)
            page.wait_for_load_state("networkidle", timeout=10000)

        
        # to check data v1
        with open('showlinks.csv', mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(records)

        for showlink, app_id, date, address in records:

            if is_scraped(showlink):
                logging.info(f"Skipping already scraped URL: {showlink}")
                continue

            detail_page = context.new_page()
            logging.info(f"Going to {showlink}")
            detail_page.goto(showlink, wait_until="domcontentloaded", timeout=30000)

            da_number = safe_get_text(detail_page.locator(".ControlHeader span[title]"))
            details = safe_get_text(detail_page.locator('//div[@class="list"]/table//div[@id="lblDetails"]'))
            lines = details.split("\n")
            for line in lines:
                if line.startswith("Description:"):
                    description = line.replace("Description:", "").strip()
                elif line.startswith("Submitted:"):
                    submitted_date = line.replace("Submitted:", "").strip()

            decision = safe_get_text(detail_page.locator('//div[@class="list"]/table//div[@id="lblDecision"]'))
            categories = safe_get_text(detail_page.locator('//div[@class="list"]/table//div[@id="lblCat"]'))
            property_address = safe_get_text(detail_page.locator('//div[@class="list"]/table//div[@id="lblProp"]'))
            applicant = safe_get_text(detail_page.locator('//div[@class="list"]/table//div[@id="lblPeople"]')).replace("Applicant:", "").strip()
            progress = safe_get_text(detail_page.locator('//div[@class="list"]/table//div[@id="lblProg"]'))
            fees_raw = safe_get_text(detail_page.locator('//div[@class="list"]/table//div[@id="lblFees"]'))
            docs = safe_get_text(detail_page.locator('//div[@class="list"]/table//div[@id="lblDocs"]'))
            contact_raw = safe_get_text(detail_page.locator('//div[@class="list"]/table//div[@id="lbl91"]'))
    
            fees, contact_council = normalize_fees_and_contact(fees_raw, contact_raw)

            record = {
                "DA_Number": da_number,
                "Detail_URL": showlink,
                "Description": description,
                "Submitted_Date": submitted_date,
                "Decision": decision,
                "Categories": categories,
                "Property_Address": property_address,
                "Applicant": applicant,
                "Progress": progress,
                "Fees": fees,
                "Documents": docs,
                "Contact_Council": contact_council,
            }
            print(record)
            insert_record(record)

            detail_page.close()
            time.sleep(2)
        
    export_to_csv()
       
if __name__ == "__main__":
    scrape()
