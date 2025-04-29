# core/summarizer.py
import pdfplumber
import requests
import tempfile
import os
import logging
import time
from transformers import BartForConditionalGeneration, BartTokenizer

logger = logging.getLogger(__name__)

class Summarizer:
    def __init__(self):
        self.model_name = "facebook/bart-large-cnn"
        try:
            # Fix for deprecated parameter warning
            self.tokenizer = BartTokenizer.from_pretrained(self.model_name, token=os.getenv("HF_TOKEN"))
            self.model = BartForConditionalGeneration.from_pretrained(self.model_name, token=os.getenv("HF_TOKEN"))
            logger.info("Summarizer model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading BART model: {str(e)}")
            self.tokenizer = None
            self.model = None

    def extract_text_from_pdf(self, pdf_url):
        """Download and extract text from a PDF URL with robust error handling."""
        try:
            logger.info(f"Extracting text from PDF: {pdf_url}")
            
            if not pdf_url or len(pdf_url.strip()) == 0:
                raise ValueError("Empty PDF URL provided")
                
            temp_file_path = None
            
            # Handle URLs vs local paths
            if pdf_url.startswith(('http://', 'https://')):
                # It's a URL, download it with retries
                max_retries = 3
                retry_delay = 2  # seconds
                last_error = None
                
                for attempt in range(max_retries):
                    try:
                        # Use a session with increased timeout
                        session = requests.Session()
                        response = session.get(pdf_url, timeout=60)  # Increased timeout to 60 seconds
                        response.raise_for_status()  # Raise exception for bad status codes
                        
                        # Create a temporary file with a .pdf extension
                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                            temp_file_path = temp_file.name
                            temp_file.write(response.content)
                            
                        # If we got here, the download was successful
                        break
                        
                    except Exception as e:
                        last_error = e
                        logger.warning(f"Attempt {attempt+1} to download PDF failed: {str(e)}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                
                # If all attempts failed, raise the last error
                if last_error and temp_file_path is None:
                    raise Exception(f"Failed to download PDF: {str(last_error)}")
                    
            else:
                # It's a local path
                if not os.path.exists(pdf_url):
                    raise FileNotFoundError(f"PDF file not found: {pdf_url}")
                temp_file_path = pdf_url
            
            # Extract text from PDF with error handling
            if temp_file_path:
                text = ""
                
                try:
                    # Use pdfplumber with error handling for problematic pages
                    with pdfplumber.open(temp_file_path) as pdf:
                        for i, page in enumerate(pdf.pages):
                            try:
                                page_text = page.extract_text() or ''
                                text += page_text + ' '
                                if i % 10 == 0:  # Log progress every 10 pages
                                    logger.debug(f"Extracted text from page {i+1}")
                            except Exception as page_error:
                                logger.warning(f"Error extracting text from page {i+1}: {str(page_error)}")
                                # Continue to next page instead of failing completely
                except Exception as pdf_error:
                    logger.error(f"Error processing PDF: {str(pdf_error)}")
                    if "CropBox missing" in str(pdf_error):
                        logger.info("Attempting alternative PDF parsing due to CropBox error")
                        # You could add an alternative parsing method here
                        # For now, we'll just return a message
                        text = "This PDF has structural issues that prevented proper text extraction."
                
                # Cleanup the temp file if we created one
                if pdf_url.startswith(('http://', 'https://')) and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.warning(f"Error deleting temporary file: {str(e)}")
                
                # Check if we got any text
                if not text or len(text.strip()) == 0:
                    return "No text could be extracted from this PDF."
                    
                return text
            
            return "Error: Unable to access PDF document."
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return f"Error extracting text: {str(e)}"

    def summarize_document(self, pdf_url, max_length=100, language='en'):
        """Summarize a budget document section, focusing on SDG 5 and SDG 10."""
        try:
            # Check if model is loaded
            if self.model is None or self.tokenizer is None:
                return "Error: Summarization model not available"
                
            # Extract text with timeouts and retries
            full_text = self.extract_text_from_pdf(pdf_url)
            
            # Check if we got error message instead of text
            if full_text.startswith("Error:") or len(full_text.strip()) < 50:
                return f"Could not generate a proper summary. {full_text}"
                
            # Create language-specific keyword sets for SDG 5 & SDG 10
            keywords = {
                'en': ['gender', 'women', 'girls', 'equality', 'equity', 'inclusion', 
                       'disparities', 'discrimination', 'marginalized', 'vulnerable'],
                'sw': ['jinsia', 'wanawake', 'wasichana', 'usawa', 'ujumuishaji', 
                       'tofauti', 'ubaguzi', 'pembezoni', 'mazingira magumu']
            }
            
            # Use appropriate keywords based on language
            lang_keywords = keywords.get(language, keywords['en'])
            
            # Find relevant sections
            relevant_text = ''
            for paragraph in full_text.split('\n'):
                if any(keyword in paragraph.lower() for keyword in lang_keywords):
                    relevant_text += paragraph + ' '

            # Use relevant text if found, otherwise use the beginning of the document
            if not relevant_text or len(relevant_text.strip()) < 100:
                relevant_text = full_text[:3000]  # Use first 3000 chars
                logger.info("No SDG-relevant text found, using first portion of document")
            else:
                logger.info(f"Found {len(relevant_text)} characters of SDG-relevant text")

            # Truncate to avoid token limits (BART has a limit of around 1024 tokens)
            if len(relevant_text) > 4000:
                relevant_text = relevant_text[:4000]
                logger.info("Truncated text to 4000 characters for model input")

            # Summarize using BART
            try:
                inputs = self.tokenizer(relevant_text, max_length=1024, return_tensors="pt", truncation=True)
                summary_ids = self.model.generate(
                    inputs["input_ids"],
                    max_length=max_length,
                    min_length=50,
                    length_penalty=2.0,
                    num_beams=4,
                    early_stopping=True
                )
                summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
                
                logger.info(f"Generated {len(summary)} character summary")
                return summary
            except Exception as e:
                logger.error(f"Error during BART summarization: {str(e)}")
                return f"Error generating summary using BART model: {str(e)}"
                
        except Exception as e:
            logger.error(f"Error summarizing document: {str(e)}")
            return f"Error summarizing document: {str(e)}"