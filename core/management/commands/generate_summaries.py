from django.core.management.base import BaseCommand
from core.models import Document
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate summaries for all existing documents that have not been processed'

    def handle(self, *args, **kwargs):
        docs = Document.objects.filter(summarization_processed=False)
        self.stdout.write(f"Found {docs.count()} documents without summaries")
        
        for i, doc in enumerate(docs):
            self.stdout.write(f"Processing document {i+1}/{docs.count()}: {doc.title}")
            # The post_save signal will handle the summary generation
            doc.summarization_processed = False
            doc.save()
            
        self.stdout.write(self.style.SUCCESS('Successfully processed all documents'))