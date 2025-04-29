# core/tests.py
from django.test import TestCase
from .summarizer import Summarizer
from .models import Document, Summary
from regions.models import Region

class SummarizerTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Uganda", code="UG")
        self.document = Document.objects.create(
            title="Uganda Budget 2025",
            pdf_url="https://example.com/budget.pdf",
            region=self.region
        )
        self.summarizer = Summarizer()

    def test_summarize_document(self):
        # Mock PDF content (requires mocking requests/pdfplumber)
        summary = self.summarizer.summarize_document(self.document.pdf_url)
        self.assertTrue(len(summary) <= 100)
        self.assertTrue(isinstance(summary, str))