# core/summarizer.py
import pdfplumber
import requests
from transformers import BartForConditionalGeneration, BartTokenizer
import os


class Summarizer:
    def __init__(self):
        self.model_name = "facebook/bart-large-cnn"
        self.tokenizer = BartTokenizer.from_pretrained(self.model_name, use_auth_token=os.getenv("HF_TOKEN"))
        self.model = BartForConditionalGeneration.from_pretrained(self.model_name, use_auth_token=os.getenv("HF_TOKEN"))

    def extract_text_from_pdf(self, pdf_url):
        """Download and extract text from a PDF URL."""
        response = requests.get(pdf_url)
        with open('temp.pdf', 'wb') as f:
            f.write(response.content)
        with pdfplumber.open('temp.pdf') as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() or ''
        return text

    def summarize_document(self, pdf_url, max_length=100, language='en'):
        """Summarize a budget document section, focusing on SDG 5 and 10."""
        # Extract text
        full_text = self.extract_text_from_pdf(pdf_url)
        
        # Filter for SDG 5 (gender) and SDG 10 (inequalities) keywords
        keywords = ['women', 'gender', 'equality', 'regional', 'inclusion', 'disparities']
        relevant_text = ''
        for paragraph in full_text.split('\n'):
            if any(keyword in paragraph.lower() for keyword in keywords):
                relevant_text += paragraph + ' '

        if not relevant_text:
            relevant_text = full_text[:1000]  # Fallback to first 1000 chars

        # Summarize using BART
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

        return summary