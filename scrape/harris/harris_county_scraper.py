import glob
import os
import re
import time
import shutil
import requests
from datetime import datetime, timedelta

from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from ocr.ocr import process_pdf_and_find_damages

# -----------------------
# Utility function
# -----------------------
def append_to_last_line(file_path, text_to_append):
    """
    Appends the given text to the last line of the file.
    If the file is empty, it creates a new line with the text.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if lines:
        # Remove any trailing newline from the last line before appending
        lines[-1] = lines[-1].rstrip('\n') + text_to_append + '\n'
    else:
        # File is empty, so just write the text in a new line
        lines.append(text_to_append + '\n')

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

# -----------------------
# HarrisCountyScraper Class
# -----------------------
class HarrisCountyScraper:
    def __init__(self, username, password, download_dir, output_file):
        self.username = username
        self.password = password
        self.download_dir = download_dir
        self.output_file = output_file
        self.driver = None
        self.wait = None

        # Ensure the directories exist
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)

        # Configure Chrome options
        chrome_options = webdriver.ChromeOptions()
        prefs = {
            'download.default_directory': self.download_dir,
            'plugins.always_open_pdf_externally': True,
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'safebrowsing.enabled': True,
        }
        chrome_options.add_experimental_option('prefs', prefs)
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

        # Configurable wait variables for downloads
        self.download_wait_timeout = 300  # seconds
        self.download_poll_interval = 5   # seconds

    def wait_until_download_dir_empty(self, timeout=None, poll_interval=None):
        """
        Wait until the download directory is empty (i.e. contains no PDF files).
        If the directory is still not empty after the timeout period, delete everything in the folder.
        
        Returns True once the directory is empty.
        """
        if timeout is None:
            timeout = self.download_wait_timeout
        if poll_interval is None:
            poll_interval = self.download_poll_interval

        start_time = time.time()
        while time.time() - start_time < timeout:
            pdf_files = glob.glob(os.path.join(self.download_dir, "*.pdf"))
            if not pdf_files:
                return True
            time.sleep(poll_interval)

        # Timeout reached: delete all files and folders in the download directory.
        for filename in os.listdir(self.download_dir):
            file_path = os.path.join(self.download_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)  # remove the file or link
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)  # remove the directory and its contents
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

        return True

    def login(self):
        self.driver.get(
            'https://www.cclerk.hctx.net/Applications/WebSearch/Registration/Login.aspx?ReturnUrl=%2fApplications%2fWebSearch%2fCourtSearch.aspx%3fCaseType%3dCivil'
        )
        username_field = self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_Login1_UserName')))
        password_field = self.driver.find_element(By.ID, 'ctl00_ContentPlaceHolder1_Login1_Password')

        username_field.send_keys(self.username)
        password_field.send_keys(self.password)
        password_field.send_keys(Keys.RETURN)
        self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_txtFrom')))

    def search_cases(self, days=7):
        today = datetime.today()
        past_date = today - timedelta(days=days)
        from_date_str = past_date.strftime('%m/%d/%Y')
        today_str = today.strftime('%m/%d/%Y')

        from_date_field = self.driver.find_element(By.ID, 'ctl00_ContentPlaceHolder1_txtFrom')
        to_date_field = self.driver.find_element(By.ID, 'ctl00_ContentPlaceHolder1_txtTo')
        from_date_field.send_keys(from_date_str)
        to_date_field.send_keys(today_str)

        search_button = self.driver.find_element(By.ID, 'ctl00_ContentPlaceHolder1_btnSearchCase')
        search_button.click()
        self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_ListViewCases_itemContainer')))

    def extract_defendant_and_plaintiff_details(self):
        """
        Extracts defendant details and plaintiff details from the 'Parties' screen.
        Returns the extracted text (defendant_details) with specific formatting:
        - Defendant: "{defendant_name}", "{defendant_address}"
        - Plaintiff and Attorney Info: "{plaintiff_name}", "{plaintiff_attorney_info}"
        """
        try:
            # Extract defendant details
            defendant_row = self.driver.find_element(
                By.XPATH,
                "//td[text()='Defendant']/following-sibling::td/span[contains(@id, 'lblStyle')]"
            )
            raw_text = defendant_row.text.strip()
            lines = raw_text.split('\n')

            # Detect the address starting line (assumes it starts with digits)
            address_idx = None
            for i, line in enumerate(lines):
                if re.match(r'^\d+', line.strip()):
                    address_idx = i
                    break

            if address_idx is not None:
                name_lines = lines[:address_idx]
                address_lines = lines[address_idx:]
                name_str = ', '.join(name_lines)
                address_str = ' '.join(address_lines)
                defendant_details = f'"{name_str}", "{address_str}"'
            else:
                defendant_details = f'"{", ".join(lines)}"'

            # Extract plaintiff and attorney details
            plaintiff_row = self.driver.find_element(
                By.XPATH,
                "//td[text()='Plaintiff']/following-sibling::td/span[contains(@id, 'lblStyle')]"
            )
            plaintiff_name = plaintiff_row.text.strip()

            plaintiff_attorney_row = self.driver.find_element(
                By.XPATH,
                "//td[text()='Plaintiff']/following-sibling::td[2]//span[contains(@id, 'lblStyle')]"
            )

            plaintiff_attorney_raw = plaintiff_attorney_row.text.strip()
            plaintiff_attorney_lines = plaintiff_attorney_raw.split('<br>')

            # Clean and join attorney details
            plaintiff_attorney_info = ' '.join(
                [re.sub(r'\s+', ' ', line.strip()) for line in plaintiff_attorney_lines]
            )

            # Combine everything into the desired format
            combined_details = f'{defendant_details}, "{plaintiff_name}", "{plaintiff_attorney_info}"'

            print(f'Combined details: {combined_details}')
            return combined_details.replace("\n", "")

        except Exception as e:
            print(f"Error extracting details: {e}")
            return ""

    def scrape_cases(self):
        processed_cases = set()
        while True:
            # Ensure the download directory is empty before processing the next case
            print("Ensuring download directory is empty before processing the next case...")
            self.wait_until_download_dir_empty()

            # Refresh the list of cases on the current results page
            cases = self.driver.find_elements(By.XPATH, "//tr[contains(@class, 'even') or contains(@class, 'odd')]")
            
            # Build a list of unprocessed cases (as tuples of (case_element, case_number))
            unprocessed_cases = []
            for case in cases:
                try:
                    link_element = case.find_element(By.XPATH, ".//a[@class='doclinks']")
                    case_number = link_element.text.strip()
                except NoSuchElementException:
                    case_number = "unknown_case_number"
                if case_number not in processed_cases:
                    unprocessed_cases.append((case, case_number))
            if not unprocessed_cases:
        # No unprocessed cases on the current page; check for a Next button
                try:
                    next_button = self.driver.find_element(By.XPATH, "//a[text()='Next']")
                    if next_button.get_attribute('disabled') is None:
                        try:
                            next_button.click()
                        except ElementClickInterceptedException as e:
                            print(f"ElementClickInterceptedException encountered: {e}. Continuing to next iteration.")
                            # Optionally, you can add a small wait here if needed:
                            # time.sleep(1)
                            continue  # Skip this iteration if click is intercepted
                        # Wait until the next page's element is present
                        self.wait.until(EC.presence_of_element_located(
                            (By.ID, 'ctl00_ContentPlaceHolder1_ListViewCases_itemContainer')
                        ))
                        continue  # Continue processing the new page
                    else:
                        print("Reached the last page.")
                        break
                except NoSuchElementException:
                    print("No 'Next' button found. Assuming last page reached.")
                    break # No 'Next' button found; assume last page reached

            # Always process the first unprocessed case
            case, case_number = unprocessed_cases[0]
            try:
                # (Re)extract the case number to be sure
                try:
                    link_element = case.find_element(By.XPATH, ".//a[@class='doclinks']")
                    case_number = link_element.text.strip()
                except NoSuchElementException:
                    case_number = "unknown_case_number"

                # Check case type (assuming it's in the 6th column)
                type_desc = case.find_element(By.XPATH, ".//td[6]").text
                if 'CONTRACT - CONSUMER/COMMERCIAL/DEBT' in type_desc:
                    print(f'Processing case number: {case_number}...')

                    # Click the case to view its details
                    case_link = case.find_element(By.XPATH, ".//a[@class='doclinks']")
                    case_link.click()
                    self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_gridViewEvents')))

                    # Grab all documents from the "Events" (Nested_ChildGrid)
                    documents = self.driver.find_elements(By.XPATH, "//table[@class='Nested_ChildGrid']//tr")
                    document_downloaded = False
                    download_link = None
                    doc_titles = []

                    # First, try to find a document that matches your criteria
                    for doc in documents:
                        doc_desc = doc.find_element(By.XPATH, ".//span[contains(@id, 'lblDocDesc')]").text
                        doc_titles.append(doc_desc)
                        doc_desc_cleaned = doc_desc.replace(" ", "").replace("'", "").lower()
                        if ("plaintiffsoriginalpetition" in doc_desc_cleaned or 
                            "filing_package" in doc_desc_cleaned):
                            download_element = doc.find_element(By.XPATH, ".//a[contains(@id, 'HyperLinkFCEC')]")
                            download_link = download_element.get_attribute('href')
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Downloading - {doc_desc} to {self.download_dir}")
                            download_element.click()
                            time.sleep(5)  # Pause for download to initiate
                            document_downloaded = True
                            break

                    # If no document matched the criteria, choose the largest document by file size
                    # If no document matched the criteria, choose the document with the most pages instead
                    if not document_downloaded:
                        print('document matching criteria not found; attempting to download the document with the most pages.')
                        no_docs_path = '/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/cases_with_no_matching_docs.txt'
                        with open(no_docs_path, 'a', encoding='utf-8') as no_docs_file:
                            doc_titles_str = " | ".join(doc_titles)
                            print(f'Adding case_number: {case_number} to no-match log.')
                            no_docs_file.write(f"{doc_titles_str}, case_number: {case_number}\n")
                        
                        largest_pages = 0
                        largest_doc = None
                        # Loop through each document row in the Nested_ChildGrid table
                        for doc in documents:
                            try:
                                # Assume the page count is in the 5th <td> element of the row.
                                # Adjust the XPath if your table structure is different.
                                page_count_td = doc.find_element(By.XPATH, ".//td[5]")
                                page_count_str = page_count_td.text.strip()
                                page_count = int(page_count_str) if page_count_str.isdigit() else 0
                                if page_count > largest_pages:
                                    largest_pages = page_count
                                    largest_doc = doc
                            except Exception as e:
                                print(f"Error processing document for page count: {e}")
                        
                        if largest_doc is not None:
                            download_element = largest_doc.find_element(By.XPATH, ".//a[contains(@id, 'HyperLinkFCEC')]")
                            download_link = download_element.get_attribute('href')
                            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Downloading document with {largest_pages} pages to {self.download_dir}")
                            download_element.click()
                            time.sleep(5)  # Pause for download to initiate
                            document_downloaded = True
                        else:
                            print("No documents available for download.")

                    # if not document_downloaded:
                    #     print('Document matching criteria not found; attempting to download the largest available document.')
                    #     no_docs_path = '/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/cases_with_no_matching_docs.txt'
                    #     with open(no_docs_path, 'a', encoding='utf-8') as no_docs_file:
                    #         doc_titles_str = " | ".join(doc_titles)
                    #         print(f'Adding case_number: {case_number} to no-match log.')
                    #         no_docs_file.write(f"{doc_titles_str}, case_number: {case_number}\n")
                        
                    #     # Create a requests.Session and add Selenium cookies so that HEAD requests are authenticated
                    #     session = requests.Session()
                    #     for cookie in self.driver.get_cookies():
                    #         session.cookies.set(cookie['name'], cookie['value'])
                        
                    #     largest_size = 0
                    #     largest_doc = None
                    #     for doc in documents:
                    #         try:
                    #             download_element = doc.find_element(By.XPATH, ".//a[contains(@id, 'HyperLinkFCEC')]")
                    #             link = download_element.get_attribute('href')
                    #             response = session.head(link, allow_redirects=True, timeout=10)
                    #             if response.status_code == 200:
                    #                 content_length = response.headers.get("Content-Length")
                    #                 if content_length is not None:
                    #                     size = int(content_length)
                    #                     if size > largest_size:
                    #                         largest_size = size
                    #                         largest_doc = doc
                    #             else:
                    #                 print(f"HEAD request for {link} returned status code {response.status_code}")
                    #         except Exception as e:
                    #             print(f"Error processing document for size: {e}")
                        # if largest_doc is not None:
                        #     download_element = largest_doc.find_element(By.XPATH, ".//a[contains(@id, 'HyperLinkFCEC')]")
                        #     download_link = download_element.get_attribute('href')
                        #     print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Downloading largest document (size: {largest_size} bytes) to {self.download_dir}")
                        #     download_element.click()
                        #     time.sleep(5)  # Pause for download
                        #     document_downloaded = True
                        # else:
                        #     print("No documents available for download.")

                    # After downloading, wait for the PDF to appear
                    if document_downloaded and download_link:
                        time.sleep(5)
                        start_time = time.time()
                        pdf_files = glob.glob(os.path.join(self.download_dir, "*.pdf"))
                        while not pdf_files and (time.time() - start_time < self.download_wait_timeout):
                            time.sleep(self.download_poll_interval)
                            pdf_files = glob.glob(os.path.join(self.download_dir, "*.pdf"))

                        # Click the Parties link to extract defendant/plaintiff details
                        try:
                            parties_link = self.driver.find_element(
                                By.XPATH, 
                                "//a[@href=\"javascript:__doPostBack('ctl00$ContentPlaceHolder1$gridViewCase','Parties$0')\"]"
                            )
                            parties_link.click()
                            self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_GridViewParties')))
                            defendant_details = self.extract_defendant_and_plaintiff_details()
                            self.driver.back()
                            with open(self.output_file, 'a', encoding='utf-8') as file:
                                file.write(f"{defendant_details}, \"{download_link}\"\n")
                        except Exception as e:
                            print(f"Error clicking or returning from Parties link: {e}")
                            defendant_details = ""
                        
                        # If a PDF file was found, process it for damages
                        if pdf_files:
                            most_recent_pdf = max(pdf_files, key=os.path.getctime)
                            try:
                                damages_result = process_pdf_and_find_damages(most_recent_pdf)
                                if damages_result:
                                    append_to_last_line(self.output_file, f", {damages_result}")
                            except Exception as ocr_err:
                                print(f"Error performing OCR on {most_recent_pdf}: {ocr_err}")
                        else:
                            print(f"No PDF found in the download directory after waiting up to {self.download_wait_timeout} seconds.")
                    else:
                        print("Document was not downloaded successfully.")
                else:
                    print(f"Skipping case number: {case_number} (type: {type_desc})")
                
                # Mark this case as processed regardless of outcome
                processed_cases.add(case_number)
                
                # Navigate back to the search results page if not already there.
                if "ctl00_ContentPlaceHolder1_ListViewCases_itemContainer" not in self.driver.page_source:
                    print('Navigating back to search results...')
                    self.driver.back()
                    self.wait.until(EC.presence_of_element_located(
                        (By.ID, 'ctl00_ContentPlaceHolder1_ListViewCases_itemContainer')
                    ))
            except Exception as e:
                print(f"Error processing case: {e}")
                self.driver.execute_script("window.history.go(-1)")
                self.wait.until(EC.presence_of_element_located(
                    (By.ID, 'ctl00_ContentPlaceHolder1_ListViewCases_itemContainer')
                ))
                continue
            # The loop will now refresh the case list and process the next unprocessed case.
 
    def quit(self):
        self.driver.quit()

# -----------------------
# Main execution (if run standalone)
# -----------------------
if __name__ == '__main__':
    scraper = HarrisCountyScraper(
        username='temp_user',
        password='temp_pass',
        download_dir='/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/downloaded_docs',
        output_file='/Users/isaaclam/guardian/marketing_leads_project/main/out/harris/defendant_data.txt'
    )
    try:
        scraper.login()
        scraper.search_cases(days=7)
        scraper.scrape_cases()
    finally:
        scraper.quit()