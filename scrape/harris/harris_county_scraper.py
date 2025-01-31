from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta
import time
import os
from ocr.ocr import process_pdf_and_find_damages
import glob
import re

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
        while True:
            cases = self.driver.find_elements(By.XPATH, "//tr[contains(@class, 'even') or contains(@class, 'odd')]")
            for index, case in enumerate(cases):
                try:
                    # Re-locate 'cases' for each iteration to avoid stale element issues
                    cases = self.driver.find_elements(By.XPATH, "//tr[contains(@class, 'even') or contains(@class, 'odd')]")
                    case = cases[index]

                    type_desc = case.find_element(By.XPATH, ".//td[6]").text
                    if 'CONTRACT - CONSUMER/COMMERCIAL/DEBT' in type_desc:
                        print('Processing case...')
                        case_link = case.find_element(By.XPATH, ".//a[@class='doclinks']")
                        case_link.click()

                        self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_gridViewEvents')))

                        documents = self.driver.find_elements(By.XPATH, "//table[@class='Nested_ChildGrid']//tr")
                        document_downloaded = False
                        download_link = None

                        for doc in documents:
                            doc_desc = doc.find_element(By.XPATH, ".//span[contains(@id, 'lblDocDesc')]").text
                            if 'Plaintiff\'s Original Petition' in doc_desc or 'filing_package' in doc_desc:
                                download_element = doc.find_element(By.XPATH, ".//a[contains(@id, 'HyperLinkFCEC')]")
                                download_link = download_element.get_attribute('href')
                                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Downloading - {doc_desc} to {self.download_dir}")
                                download_element.click()
                                time.sleep(2.4)  # brief wait for the download to start
                                document_downloaded = True
                                break

                        if document_downloaded and download_link:
                            # Short initial wait
                            time.sleep(2)

                            # Now poll for up to 300 seconds in 5-second intervals
                            timeout_seconds = 300
                            poll_interval = 5
                            start_time = time.time()

                            pdf_files = glob.glob(os.path.join(self.download_dir, "*.pdf"))
                            while not pdf_files and (time.time() - start_time < timeout_seconds):
                                time.sleep(poll_interval)
                                pdf_files = glob.glob(os.path.join(self.download_dir, "*.pdf"))

                            # ---------------------------------------
                            # Now handle 'Parties' link regardless of whether we found a PDF
                            # ---------------------------------------
                            try:
                                parties_link = self.driver.find_element(
                                    By.XPATH,
                                    "//a[@href=\"javascript:__doPostBack('ctl00$ContentPlaceHolder1$gridViewCase','Parties$0')\"]"
                                )
                                parties_link.click()

                                self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_GridViewParties')))
                                defendant_details = self.extract_defendant_and_plaintiff_details()
                                self.driver.back()

                                # 1) Write the defendant details and download link to the output file immediately
                                with open(self.output_file, 'a', encoding='utf-8') as file:
                                    file.write(f"{defendant_details}, \"{download_link}\"\n")

                            except Exception as e:
                                print(f"Error clicking or returning from Parties link: {e}")
                                defendant_details = ""

                            # -------------------------------------------------------
                            # 2) If we found a PDF in the download directory, pick the most recent one
                            # -------------------------------------------------------
                            if pdf_files:
                                most_recent_pdf = max(pdf_files, key=os.path.getctime)

                                # ---------------------------------------------------
                                # 3) Perform OCR on that PDF file
                                # ---------------------------------------------------
                                try:
                                    damages_result = process_pdf_and_find_damages(most_recent_pdf)
                                    # Instead of printing, append the damages result to the last line of output_file
                                    if damages_result:
                                        append_to_last_line(self.output_file, f", {damages_result}")
                                except Exception as ocr_err:
                                    print(f"Error performing OCR on {most_recent_pdf}: {ocr_err}")
                            else:
                                print(f"No PDF found in the download directory after waiting up to {timeout_seconds} seconds.")
                        else:
                            print('Document matching criteria not found or not downloaded.')

                        print('Navigating back to search results...')
                        self.driver.back()
                        self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_ListViewCases_itemContainer')))

                except Exception as e:
                    print(f"Error processing case: {e}")
                    # Go back and continue
                    self.driver.execute_script("window.history.go(-1)")
                    self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_ListViewCases_itemContainer')))
                    continue

            # Attempt to move to the next page
            try:
                next_button = self.driver.find_element(By.XPATH, "//a[text()='Next']")
                if next_button.get_attribute('disabled') is None:
                    next_button.click()
                    self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_ListViewCases_itemContainer')))
                else:
                    print("Reached the last page.")
                    break
            except NoSuchElementException:
                print("No 'Next' button found. Assuming last page reached.")
                break
    


    def quit(self):
        self.driver.quit()

# Allow this script to be imported or run standalone
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
