import os
from dotenv import load_dotenv
from scrape.harris.harris_county_scraper import HarrisCountyScraper
from ocr.ocr import process_pdf_and_find_damages
import csv
import string

import csv
import string

def convert_txt_to_csv(input_txt_file, output_csv_file):
    """
    Converts a text file with data separated by `"` and `,` into a CSV file.
    Adds a DOLLAR_AMOUNT column by parsing the Details column
    for the first token that starts with '$'.
    Adds a COURT_NAME column extracted from the last field.

    The final CSV columns (in order) will be:
      Name, Address, Plaintiff_Name, Plaintiff_Attorney, DOLLAR_AMOUNT, COURT_NAME, Case_Link, Details
    
    Args:
        input_txt_file (str): Path to the input .txt file.
        output_csv_file (str): Path to save the output .csv file.
    """
    with open(input_txt_file, 'r', encoding='utf-8') as txt_file, \
         open(output_csv_file, 'w', newline='', encoding='utf-8') as csv_file:
        
        writer = csv.writer(csv_file)
        
        # Adjust the header to include COURT_NAME after DOLLAR_AMOUNT
        writer.writerow([
            "Name",
            "ADDRESS",
            "PLAINTIFF_NAME",
            "PLAINTIFF_ATTORNEY",
            "DOLLAR_AMOUNT",  # Inserted here
            "COURT_NAME",     # New column
            "CASE_LINK",
            "DETAILS"
        ])
        
        for line in txt_file:
            # Split the line on `", "` to extract fields
            fields = line.strip().split('", "')
            
            # Remove any surrounding quotes from each field
            cleaned_fields = [field.strip('"') for field in fields]
            
            # Safely extract each field by index
            name = cleaned_fields[0] if len(cleaned_fields) > 0 else ""
            address = cleaned_fields[1] if len(cleaned_fields) > 1 else ""
            plaintiff_name = cleaned_fields[2] if len(cleaned_fields) > 2 else ""
            plaintiff_attorney = cleaned_fields[3] if len(cleaned_fields) > 3 else ""
            case_link = cleaned_fields[4] if len(cleaned_fields) > 4 else ""
            details = cleaned_fields[5] if len(cleaned_fields) > 5 else ""
            court_name = cleaned_fields[6] if len(cleaned_fields) > 6 else ""  # New field
            
            # Default if no dollar amount is found
            dollar_amount = ""
            
            # Split details on whitespace and look for the first token that starts with '$'
            for word in details.split():
                if word.startswith('$'):
                    # Strip trailing punctuation (but keep the initial '$')
                    dollar_amount = word.rstrip(string.punctuation)
                    break
            
            # Write the row in the new order (DOLLAR_AMOUNT and COURT_NAME included)
            writer.writerow([
                name,
                address,
                plaintiff_name,
                plaintiff_attorney,
                dollar_amount,  # Inserted here
                court_name,     # New column
                case_link,
                details
            ])


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

