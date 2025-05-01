import logging
import re
import tempfile
import requests
import pdfplumber
from transformers import pipeline
from django.conf import settings

logger = logging.getLogger(__name__)

class Summarizer:
    def __init__(self):
        logger.debug("Loading BART summarization model")
        self.summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        logger.info("Summarizer model loaded successfully")

    def extract_text_from_pdf(self, pdf_url):
        logger.debug(f"Extracting text from PDF: {pdf_url}")
        try:
            response = requests.get(pdf_url, timeout=60)
            response.raise_for_status()
            logger.debug(f"PDF downloaded, size={len(response.content)} bytes")
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name
            with pdfplumber.open(temp_file_path) as pdf:
                text = ''
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + '\n'
            import os
            os.unlink(temp_file_path)
            logger.debug(f"Deleted temp file: {temp_file_path}")
            if not text.strip():
                logger.warning("No text could be extracted from the PDF")
                return "No text could be extracted from the PDF."
            logger.info(f"Extracted {len(text)} characters from PDF")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_url}: {str(e)}")
            return f"Error extracting text: {str(e)}"

    def _extract_sdg_relevant_text(self, text, language='en'):
        logger.debug(f"Extracting SDG-relevant text for language={language}")
        keywords = [
            'gender', 'women', 'girls', 'female', 'maternal',
            'gender-based violence', 'gender equality', 'gender parity',
            'inequality', 'equity', 'disparity', 'marginalized', 'vulnerable',
            'inclusion', 'inclusive', 'discrimination', 'minority',
            'differently abled', 'disabilities', 'equal opportunity'
        ]
        try:
            relevant_text = ''
            for paragraph in text.split('\n'):
                if any(re.search(r'\b' + re.escape(keyword) + r'\b', paragraph.lower()) for keyword in keywords):
                    relevant_text += paragraph + '\n'
            if not relevant_text.strip():
                logger.warning("No SDG-relevant text found, using first 3000 characters")
                return text[:3000]
            logger.info(f"Found {len(relevant_text)} characters of SDG-relevant text")
            return relevant_text
        except Exception as e:
            logger.error(f"Error extracting SDG-relevant text: {str(e)}")
            return text[:3000]

    def summarize_document(self, pdf_url, language='en'):
        logger.debug(f"Summarizing document: {pdf_url}, language={language}")
        try:
            text = self.extract_text_from_pdf(pdf_url)
            if "Error extracting text" in text or "No text could be extracted" in text:
                logger.warning(f"Text extraction failed: {text}")
                return text, None
            sdg_text = self._extract_sdg_relevant_text(text, language)
            truncated_text = sdg_text[:4000]
            logger.info(f"Truncated text to {len(truncated_text)} characters for model input")
            summary = self.summarizer(
                truncated_text,
                max_length=100,
                min_length=30,
                do_sample=False
            )[0]['summary_text']
            logger.info(f"Generated {len(summary)} character summary")
            return summary, sdg_text[:4000]
        except Exception as e:
            logger.error(f"Error summarizing document {pdf_url}: {str(e)}")
            return f"Error summarizing document: {str(e)}", None
        
        
        
        
        
        
        
        
        

# import logging
# import re
# import tempfile
# import requests
# import pdfplumber
# from transformers import pipeline
# from django.conf import settings

# logger = logging.getLogger(__name__)

# class Summarizer:
#     def __init__(self):
#         logger.debug("Loading BART summarization model")
#         self.summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
#         logger.info("Summarizer model loaded successfully")

#     def extract_text_from_pdf(self, pdf_url):
#         logger.debug(f"Extracting text from PDF: {pdf_url}")
#         try:
#             response = requests.get(pdf_url, timeout=60)
#             response.raise_for_status()
#             logger.debug(f"PDF downloaded, size={len(response.content)} bytes")
#             with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
#                 temp_file.write(response.content)
#                 temp_file_path = temp_file.name
#             with pdfplumber.open(temp_file_path) as pdf:
#                 text = ''
#                 for page in pdf.pages:
#                     page_text = page.extract_text()
#                     if page_text:
#                         text += page_text + '\n'
#             import os
#             os.unlink(temp_file_path)
#             logger.debug(f"Deleted temp file: {temp_file_path}")
#             if not text.strip():
#                 logger.warning("No text could be extracted from the PDF")
#                 return "No text could be extracted from the PDF."
#             logger.info(f"Extracted {len(text)} characters from PDF")
#             return text
#         except Exception as e:
#             logger.error(f"Error extracting text from PDF {pdf_url}: {str(e)}")
#             return f"Error extracting text: {str(e)}"

#     def _extract_sdg_relevant_text(self, text, language='en'):
#         logger.debug(f"Extracting SDG-relevant text for language={language}")
#         keywords = [
#             'gender', 'women', 'girls', 'female', 'maternal',
#             'gender-based violence', 'gender equality', 'gender parity',
#             'inequality', 'equity', 'disparity', 'marginalized', 'vulnerable',
#             'inclusion', 'inclusive', 'discrimination', 'minority',
#             'differently abled', 'disabilities', 'equal opportunity'
#         ]
#         try:
#             relevant_text = ''
#             for paragraph in text.split('\n'):
#                 if any(re.search(r'\b' + re.escape(keyword) + r'\b', paragraph.lower()) for keyword in keywords):
#                     relevant_text += paragraph + '\n'
#             if not relevant_text.strip():
#                 logger.warning("No SDG-relevant text found, using first 3000 characters")
#                 return text[:3000]
#             logger.info(f"Found {len(relevant_text)} characters of SDG-relevant text")
#             return relevant_text
#         except Exception as e:
#             logger.error(f"Error extracting SDG-relevant text: {str(e)}")
#             return text[:3000]

#     def summarize_document(self, pdf_url, language='en'):
#         logger.debug(f"Summarizing document: {pdf_url}, language={language}")
#         try:
#             text = self.extract_text_from_pdf(pdf_url)
#             if "Error extracting text" in text or "No text could be extracted" in text:
#                 logger.warning(f"Text extraction failed: {text}")
#                 return text, None
#             sdg_text = self._extract_sdg_relevant_text(text, language)
#             truncated_text = sdg_text[:4000]
#             logger.info(f"Truncated text to {len(truncated_text)} characters for model input")
#             summary = self.summarizer(
#                 truncated_text,
#                 max_length=100,
#                 min_length=30,
#                 do_sample=False
#             )[0]['summary_text']
#             logger.info(f"Generated {len(summary)} character summary")
#             return summary, sdg_text[:4000]
#         except Exception as e:
#             logger.error(f"Error summarizing document {pdf_url}: {str(e)}")
#             return f"Error summarizing document: {str(e)}", None