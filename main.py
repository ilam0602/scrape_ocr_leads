import os
import re
import csv
import string
from dotenv import load_dotenv
from scrape.harris.harris_county_scraper import HarrisCountyScraper
from ocr.ocr import process_pdf_and_find_damages

def convert_txt_to_csv(input_txt_file, output_csv_file):
    """
    Converts a text file with data separated by `"` and `,` into a CSV file.
    Adds a DOLLAR_AMOUNT column by parsing the Details column for the first token that starts with '$'.
    Adds a COURT_NAME column extracted from the last field.
    
    The final CSV columns (in order) will be:
      Name, ADDRESS, PLAINTIFF_NAME, PLAINTIFF_ATTORNEY, DOLLAR_AMOUNT, COURT_NAME, CASE_LINK, DETAILS
    
    Args:
        input_txt_file (str): Path to the input .txt file.
        output_csv_file (str): Path to save the output .csv file.
    """
    with open(input_txt_file, 'r', encoding='utf-8') as txt_file, \
         open(output_csv_file, 'w', newline='', encoding='utf-8') as csv_file:
        
        writer = csv.writer(csv_file)
        
        # Write header with the new columns included
        writer.writerow([
            "Name",
            "ADDRESS",
            "PLAINTIFF_NAME",
            "PLAINTIFF_ATTORNEY",
            "DOLLAR_AMOUNT",
            "COURT_NAME",
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
            court_name = cleaned_fields[6] if len(cleaned_fields) > 6 else ""
            
            # Default if no dollar amount is found
            dollar_amount = ""
            
            # Split details on whitespace and look for the first token that starts with '$'
            for word in details.split():
                if word.startswith('$'):
                    # Strip trailing punctuation (but keep the initial '$')
                    dollar_amount = word.rstrip(string.punctuation)
                    break
            
            # Write the row in the new order (with DOLLAR_AMOUNT and COURT_NAME included)
            writer.writerow([
                name,
                address,
                plaintiff_name,
                plaintiff_attorney,
                dollar_amount,
                court_name,
                case_link,
                details
            ])



def verify_csv(input_csv_file, verified_csv_file, filtered_csv_file):
    """
    Reads the CSV file produced by convert_txt_to_csv, examines each row, and appends a new column 'flag'
    as the first column in the output CSV.
    
    A row's flag is set to 1 if:
      - The DOLLAR_AMOUNT column is empty, OR
      - The DOLLAR_AMOUNT column equals '$250,000.00' or '$250,000', OR
      - The COURT_NAME column does NOT contain a court number between 1 and 4 (inclusive), OR
      - The first column (from defendant_data.csv) contains 'c/o' (case-insensitive).
        
    Otherwise, the flag is set to 0.
    
    Additionally, a second file is created which contains only the rows with flag == 0.
    
    Args:
        input_csv_file (str): Path to the input CSV file.
        verified_csv_file (str): Path to save the verified CSV file (with all rows).
        filtered_csv_file (str): Path to save the CSV file that only includes rows where flag == 0.
    """
    # Regex to capture the court number from the COURT_NAME.
    pattern = re.compile(r'^Harris County - County Civil Court at Law No\. (\d+)$')
    
    with open(input_csv_file, 'r', encoding='utf-8') as infile, \
         open(verified_csv_file, 'w', newline='', encoding='utf-8') as verified_outfile, \
         open(filtered_csv_file, 'w', newline='', encoding='utf-8') as filtered_outfile:
        
        reader = csv.DictReader(infile)
        # Create new fieldnames with 'flag' as the first column.
        new_fieldnames = ['flag'] + reader.fieldnames
        
        verified_writer = csv.DictWriter(verified_outfile, fieldnames=new_fieldnames)
        verified_writer.writeheader()
        
        filtered_writer = csv.DictWriter(filtered_outfile, fieldnames=new_fieldnames)
        filtered_writer.writeheader()
        
        for row in reader:
            flag = 0
            
            # Get the DOLLAR_AMOUNT field and strip extra whitespace.
            dollar_amount = row.get('DOLLAR_AMOUNT', '').strip()
            # Flag if DOLLAR_AMOUNT is empty or equals '$250,000.00' or '$250,000'
            if not dollar_amount or dollar_amount in ('$250,000.00', '$250,000','$100,000'):
                flag = 1
            else:
                # Retrieve and strip the COURT_NAME field.
                court_name = row.get('COURT_NAME', '').strip()
                match = pattern.match(court_name)
                if match:
                    # Extract the court number and convert it to an integer.
                    court_number = int(match.group(1))
                    # Set flag to 1 if the court number is NOT between 1 and 4 (i.e., out-of-range)
                    if not (1 <= court_number <= 4):
                        flag = 1
                    else:
                        flag = 0
                else:
                    # If the COURT_NAME doesn't match the expected pattern, consider it out-of-range.
                    flag = 1
            
            # Additional check: if 'c/o' (case-insensitive) is found in the first column, flag the row.
            first_field = reader.fieldnames[0]
            first_col_value = row.get(first_field, '').strip()
            if "c/o" in first_col_value.lower():
                flag = 1
            
            # Add the flag to the row and write to the verified CSV.
            row['flag'] = flag
            verified_writer.writerow(row)
            
            # Write only rows that are NOT flagged (flag == 0) to the filtered CSV.
            if flag == 0:
                filtered_writer.writerow(row)
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
        
        # Convert the TXT data to CSV
        input_txt = '/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/defendant_data.txt'
        output_csv = '/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/defendant_data.csv'
        convert_txt_to_csv(input_txt, output_csv)
        
        # Define the output file paths for verified CSV and filtered (non-flagged) CSV.
        verified_csv = '/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/defendant_data_verified.csv'
        filtered_csv = '/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/defendant_data_verified_filtered.csv'
        
        # Verify the CSV, add the 'flag' column, and create an additional file that excludes flagged rows.
        verify_csv(output_csv, verified_csv, filtered_csv)
        
        print(f"CSV conversion complete.\nVerified CSV saved to {verified_csv}\nFiltered CSV (non-flagged rows) saved to {filtered_csv}")
        
    finally:
        # Ensure the browser is closed
        scraper.quit()

if __name__ == '__main__':
    main()
