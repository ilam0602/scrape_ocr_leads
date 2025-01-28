import os
from dotenv import load_dotenv
from scrape.harris.harris_county_scraper import HarrisCountyScraper
from ocr.ocr import process_pdf_and_find_damages
import csv

def convert_txt_to_csv(input_txt_file, output_csv_file):
    """
    Converts a text file with data separated by `"` and `,` into a CSV file.
    
    Args:
        input_txt_file (str): Path to the input .txt file.
        output_csv_file (str): Path to save the output .csv file.
    """
    with open(input_txt_file, 'r') as txt_file, open(output_csv_file, 'w', newline='') as csv_file:
        # Create a CSV writer object
        writer = csv.writer(csv_file)
        
        # Write header row to the CSV
        writer.writerow(["Name", "Address", "Case_Link", "Details"])
        
        # Read lines from the text file and process each one
        for line in txt_file:
            # Split the line on `", "` to extract fields
            fields = line.strip().split('", "')
            
            # Remove leading and trailing quotes from each field
            cleaned_fields = [field.strip('"') for field in fields]
            
            # Write the row to the CSV
            writer.writerow(cleaned_fields)

# Example usage

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
        # scraper.search_cases(days=1)
        scraper.scrape_cases()
        input_txt = '/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/defendant_data.txt'
        output_csv = '/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/defendant_data.csv'
        convert_txt_to_csv(input_txt, output_csv)
    finally:
        # Ensure the browser is closed
        scraper.quit()

if __name__ == '__main__':
    main()

