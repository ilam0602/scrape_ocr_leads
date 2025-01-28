import os
import re
import numpy as np
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import cv2
import google.generativeai as genai
from dotenv import load_dotenv

genai.configure()
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
print(google_api_key)

def extract_damages_with_gemini(text):
    # Configure the Gemini API client
    genai.configure(api_key=google_api_key)

    # Initialize the GenerativeModel with the specified model name
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    # Define the prompt for the Gemini model
    prompt = (
        "Analyze the following text and extract the damages the defendant is getting sued for. "
        "Return the sentence where this is found and "
        "otherwise, indicate that no such sentences were found.\n\n"
        f"Text:\n{text}"
    )

    # Generate a response using the Gemini model
    response = model.generate_content(prompt)

    # Extract and return the model's output
    return response.text


def preprocess_image_to_remove_watermark(image, output_folder, page_number):
    """
    Preprocess the image to remove lighter watermarks while keeping text,
    apply thresholding, and then make the text bolder with morphological dilation.
    Further darken the text to enhance visibility for OCR.
    """
    # Convert PIL Image to OpenCV format (grayscale)
    img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)

    # Remove lighter shades (e.g., watermark)
    watermark_removed = np.where(img > 50, 255, img).astype(np.uint8)

    # Apply adaptive thresholding to focus on text
    adaptive_threshold = cv2.adaptiveThreshold(
        watermark_removed,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2
    )

    # Save the processed image (COMMENTED OUT by default)
    # If you want to keep the individual processed images, uncomment below:
    # processed_image_path = os.path.join(output_folder, f"processed_page_{page_number}.png")
    # cv2.imwrite(processed_image_path, watermark_removed)
    
    # Convert the (currently in-memory) processed image back to PIL format for OCR
    processed_pil = Image.fromarray(watermark_removed)

    return processed_pil

def extract_text_from_pdf_with_watermark_removal(pdf_path, output_folder="processed_images"):
    """
    Extracts text from a PDF by converting pages to images, removing watermarks,
    and performing OCR. By default, does NOT keep intermediate files.
    """
    # Create output folder (COMMENTED OUT by default)
    # If you want the processed images to be saved, uncomment this:
    # os.makedirs(output_folder, exist_ok=True)

    pages = convert_from_path(pdf_path, dpi=300)
    text = ""

    for page_number, page_image in enumerate(pages, start=1):
        print(f"Processing page {page_number}...")

        # Preprocess (threshold, remove watermark noise, make text bolder)
        processed_image = preprocess_image_to_remove_watermark(page_image, output_folder, page_number)

        # Perform OCR on the preprocessed image
        page_text = pytesseract.image_to_string(processed_image)
        text += page_text + "\n\n"

    # Save the extracted text to a file (COMMENTED OUT by default)
    # If you want to keep the full OCR text, uncomment this:
    # with open("ocr_output.txt", "w", encoding="utf-8") as ocr_file:
    #     ocr_file.write(text)

    return text

def find_damages_and_value(text):
    """
    Looks for any sentence where the word 'damages' (case-insensitive) 
    is followed by a dollar amount. Returns the first such sentence found.
    """
    # Replace newlines with spaces to handle multi-line sentences
    text = text.replace('\n', ' ')
    
    # Split text into sentences by common punctuation
    sentences = re.split(r'[.!?]', text)

    # Regex pattern to match 'damages' followed by a dollar amount
    damages_dollar_pattern = re.compile(r'\bdamages\b.*?\$[\d,]+(\.\d{2})?', re.IGNORECASE)

    for sentence in sentences:
        # Check if 'damages' is followed by a dollar amount in the sentence
        if damages_dollar_pattern.search(sentence):
            return sentence.strip()

    return "No sentence found where 'damages' is followed by a dollar value."

def process_pdf_and_find_damages(pdf_path):
    """
    Main function to process the PDF, extract text, and find damages with values.
    By default, removes ALL intermediate and output files, including the original PDF.
    Uncomment lines if you wish to keep any of them.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError("PDF file not found. Please check the path.")

    print("Extracting text from PDF...")
    extracted_text = extract_text_from_pdf_with_watermark_removal(pdf_path)

    print("\nSearching for 'damages' and the associated dollar value...")
    # result = find_damages_and_value(extracted_text)
    result = extract_damages_with_gemini(extracted_text)

    # Optionally save the result to a text file (COMMENTED OUT by default)
    # If you want to keep the final search result, uncomment below:
    # with open("damages_result.txt", "w", encoding="utf-8") as result_file:
    #     result_file.write(result)

    # Cleanup: Remove the original PDF
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        print(f"Removed the PDF file: {pdf_path}")

    # Cleanup: Remove any processed images folder if created and if it exists
    # (Uncomment the "os.makedirs" in extract_text_from_pdf_with_watermark_removal if you used it)
    if os.path.exists("processed_images"):
        for file_name in os.listdir("processed_images"):
            file_path = os.path.join("processed_images", file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)
        os.rmdir("processed_images")
        print("Removed the processed_images folder.")

    # Cleanup: Remove the potential OCR output file
    if os.path.exists("ocr_output.txt"):
        os.remove("ocr_output.txt")
        print("Removed ocr_output.txt.")

    # Cleanup: Remove the potential damages result file
    if os.path.exists("damages_result.txt"):
        os.remove("damages_result.txt")
        print("Removed damages_result.txt.")

    return result

# comment/uncomment to test
# print(process_pdf_and_find_damages('/Users/isaaclam/guardian/marketing_leads_project/main/ocr/example_docs/sample.pdf'))