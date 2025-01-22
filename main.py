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
        scraper.search_cases(days=1)
        scraper.scrape_cases()
    finally:
        # Ensure the browser is closed
        scraper.quit()

    # Directory where downloaded files are stored
    download_dir = "./out/harris/downloaded_docs"
    print(f"Checking downloaded files in {download_dir}")
    print(os.listdir(download_dir))  # List all files in the directory

    # Loop through all files in the directory
    for file_name in os.listdir(download_dir):
        if file_name.endswith(".pdf"):  # Check for PDF files
            pdf_path = os.path.join(download_dir, file_name)
            print(f"\nProcessing OCR for file: {pdf_path}")

            try:
                result = process_pdf_and_find_damages(pdf_path)
                print("\n--- Result ---\n")
                print(result)

                # Save results for each file in a separate text file
                result_file_path = os.path.join(download_dir, f"{file_name}_damages_result.txt")
                with open(result_file_path, "w", encoding="utf-8") as result_file:
                    result_file.write(result)
                print(f"Saved OCR results to: {result_file_path}")
            except FileNotFoundError as e:
                print(f"File not found: {e}")
            except Exception as e:
                print(f"Error processing file {file_name}: {e}")

if __name__ == '__main__':
    main()

