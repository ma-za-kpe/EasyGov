# core/models.py
from django.db import models
from regions.models import Region

class Document(models.Model):
    title = models.CharField(max_length=255)
    pdf_url = models.URLField(max_length=500)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Summary(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='summaries')
    text = models.TextField()
    language = models.CharField(max_length=10, choices=[('en', 'English'), ('sw', 'Swahili')])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Summary for {self.document.title} ({self.language})"

class FactCheck(models.Model):
    summary = models.ForeignKey(Summary, on_delete=models.CASCADE, related_name='fact_checks')
    source_url = models.URLField(max_length=500)
    is_verified = models.BooleanField(default=False)
    checked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FactCheck for {self.summary}"