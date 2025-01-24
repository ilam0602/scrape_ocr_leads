import os
from dotenv import load_dotenv
from scrape.harris.harris_county_scraper import HarrisCountyScraper
from ocr.ocr import process_pdf_and_find_damages

# Load environment variables from .env file
load_dotenv()

def main():
    # Fetch username and password from environment variables
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    if not username or not password:
        raise ValueError("USERNAME and PASSWORD must be set in the .env file.")

    # Configure the scraper
    scraper = HarrisCountyScraper(
        username=username,
        password=password,
        download_dir='/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/downloaded_docs',
        output_file='/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/defendant_data.txt'
    )

    try:
        # Perform the scraping tasks
        scraper.login()
        scraper.search_cases(days=7)
        scraper.scrape_cases()
    finally:
        # Ensure the browser is closed
        scraper.quit()

if __name__ == '__main__':
    main()

