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
import glob


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

    def scrape_cases(self):
        while True:
            # Re-locate the cases on the page
            cases = self.driver.find_elements(By.XPATH, "//tr[contains(@class, 'even') or contains(@class, 'odd')]")
            for index in range(len(cases)):
                try:
                    # Re-locate the cases again for each iteration
                    cases = self.driver.find_elements(By.XPATH, "//tr[contains(@class, 'even') or contains(@class, 'odd')]")
                    case = cases[index]

                    # Get the case type description
                    type_desc = case.find_element(By.XPATH, ".//td[6]").text
                    if 'CONTRACT - CONSUMER/COMMERCIAL/DEBT' in type_desc:
                        print('Processing case...')
                        case_link = case.find_element(By.XPATH, ".//a[@class='doclinks']")
                        case_link.click()

                        # Wait for the events table to load
                        self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_gridViewEvents')))

                        # Navigate to the "Parties" page to extract defendant details
                        parties_link = self.driver.find_element(
                            By.XPATH,
                            "//a[@href=\"javascript:__doPostBack('ctl00$ContentPlaceHolder1$gridViewCase','Parties$0')\"]"
                        )
                        parties_link.click()

                        self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_GridViewParties')))

                        # Extract the defendant's name
                        defendant_row = self.driver.find_element(
                            By.XPATH,
                            "//td[text()='Defendant']/following-sibling::td/span[contains(@id, 'lblStyle')]"
                        )
                        defendant_details = defendant_row.text.strip().replace('\n', ', ')
                        first_last_name = defendant_details.split(',')[0]  # Assuming "Last, First" format
                        file_safe_name = first_last_name.replace(' ', '_').replace(',', '')
                        print(f"Defendant name extracted: {first_last_name}")

                        # Return to the case page
                        self.driver.back()
                        self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_gridViewEvents')))

                        # Search for the document to download
                        documents = self.driver.find_elements(By.XPATH, "//table[@class='Nested_ChildGrid']//tr")
                        for doc in documents:
                            doc_desc = doc.find_element(By.XPATH, ".//span[contains(@id, 'lblDocDesc')]").text
                            if 'Plaintiff\'s Original Petition' in doc_desc or 'filing_package' in doc_desc:
                                download_element = doc.find_element(By.XPATH, ".//a[contains(@id, 'HyperLinkFCEC')]")
                                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Downloading - {doc_desc}")
                                download_element.click()

                                # Wait for the file to download
                                time.sleep(5)  # Adjust based on actual download time

                                # Identify the most recent file in the download directory
                                downloaded_files = glob.glob(f"{self.download_dir}/*")
                                latest_file = max(downloaded_files, key=os.path.getctime)

                                # Rename the file with the defendant's name
                                renamed_path = os.path.join(self.download_dir, f"{file_safe_name}.pdf")
                                os.rename(latest_file, renamed_path)
                                print(f"File downloaded and renamed to: {renamed_path}")

                                # Save the details to the output file
                                with open(self.output_file, 'a') as file:
                                    file.write(f"{defendant_details}, {renamed_path}\n")
                                print(f"Saved details to output file: {defendant_details}, {renamed_path}")
                                break

                        print('Navigating back to search results...')
                        self.driver.back()
                        self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_ListViewCases_itemContainer')))

                except Exception as e:
                    print(f"Error processing case: {e}")
                    # Navigate back and refresh case list
                    self.driver.execute_script("window.history.go(-1)")
                    self.wait.until(EC.presence_of_element_located((By.ID, 'ctl00_ContentPlaceHolder1_ListViewCases_itemContainer')))
                    continue

            # Check for the "Next" button to paginate
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

