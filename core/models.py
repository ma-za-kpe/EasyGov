# core/models.py - Updated with Celery integration
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from regions.models import Region
import logging

logger = logging.getLogger(__name__)

class Document(models.Model):
    """
    Document model representing a government document (PDF) that needs to be summarized.
    
    The document processing pipeline:
    1. Admin adds a document via the admin interface 
    2. The post_save signal triggers a Celery task
    3. Summaries are generated asynchronously in different languages
    4. FactChecks are added to verify the document's authenticity
    """
    title = models.CharField(max_length=255)
    pdf_url = models.URLField(max_length=500)
    source_url = models.URLField(max_length=500, blank=True, default='')
    is_verified = models.BooleanField(default=False)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # Flag indicating if summarization has been processed (prevents re-processing)
    summarization_processed = models.BooleanField(default=False)
    
    # Added to defer summarization
    should_summarize = models.BooleanField(default=True, help_text="Uncheck to add document without auto-summarization")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Track if is_verified has changed
        if self.pk:
            try:
                old_instance = Document.objects.get(pk=self.pk)
                verification_changed = (
                    old_instance.is_verified != self.is_verified or 
                    old_instance.source_url != self.source_url
                )
            except Document.DoesNotExist:
                verification_changed = True
        else:
            verification_changed = True
            
        # Save the document
        super().save(*args, **kwargs)
        
        # If verification status changed, sync to fact checks
        if verification_changed:
            self.sync_verification_to_fact_checks()
            
    def sync_verification_to_fact_checks(self):
        """Sync verification status from document to all related fact checks"""
        try:
            # Get all summaries for this document
            summaries = Summary.objects.filter(document=self)
            
            for summary in summaries:
                # Get or create fact check
                fact_check, created = FactCheck.objects.get_or_create(
                    summary=summary,
                    defaults={
                        'source_url': self.source_url,
                        'is_verified': self.is_verified
                    }
                )
                
                # Update existing fact check if not newly created
                if not created:
                    fact_check.source_url = self.source_url
                    fact_check.is_verified = self.is_verified
                    fact_check.save()
                    
            logger.info(f"Synced verification status for document {self.id}: {self.is_verified}")
        except Exception as e:
            logger.error(f"Error syncing verification status for document {self.id}: {str(e)}")

    def trigger_summarization(self):
        """
        Manually trigger the summarization process via Celery task.
        """
        from core.tasks import process_document_summaries
        process_document_summaries.delay(self.id)
        logger.info(f"Manually triggered summarization for document {self.id}")


class Summary(models.Model):
    """
    Summary model representing a simplified version of a document.
    Each document can have multiple summaries in different languages.
    
    Includes:
    - Main summary text
    - Original text (optional excerpt from the document)
    - Explanation (how this affects women and marginalized groups)
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='summaries')
    text = models.TextField()
    original_text = models.TextField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=10, choices=[('en', 'English')], default='en')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Summary for {self.document.title} ({self.language})"
    
    def save(self, *args, **kwargs):
        # Ensure we have at least default text if fields are empty
        if not self.text or len(self.text.strip()) < 10:
            self.text = f"This document describes budget allocations related to {self.document.title}."
            
        if not self.explanation:
            # Create a default explanation based on the document title and region
            region_name = self.document.region.name if self.document.region else ""
            self.explanation = self._get_default_explanation(region_name)
            
        super().save(*args, **kwargs)
    
    def _get_default_explanation(self, region_name=""):
        """Generate a default explanation focused on SDG 5 and SDG 10"""
        region_text = f" in {region_name}" if region_name else ""
        
        if self.language == 'sw':  # Swahili
            return (
                f"Bajeti hii{region_text} inalenga kushughulikia usawa wa kijinsia na kupunguza tofauti za kijamii. "
                f"Inaweza kuathiri ufikiaji wa huduma za afya, elimu, na fursa za kiuchumi kwa wanawake. "
                f"Pia inaweza kuboresha maisha ya makundi yaliyotengwa na kusaidia jamii zilizo katika mazingira magumu."
            )
        else:  # Default to English
            return (
                f"This budget{region_text} addresses gender equality and reducing social inequalities. "
                f"It may affect women's access to healthcare, education, and economic opportunities. "
                f"It could also improve conditions for marginalized groups and support vulnerable communities."
            )
    
    class Meta:
        unique_together = ('document', 'language')


class FactCheck(models.Model):
    """
    FactCheck model representing verification information for a summary.
    
    Used to track whether a summary has been verified for accuracy and
    to provide source URLs for verification.
    """
    summary = models.ForeignKey(Summary, on_delete=models.CASCADE, related_name='fact_checks')
    source_url = models.URLField(max_length=500)
    is_verified = models.BooleanField(default=False)
    checked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FactCheck for {self.summary}"


# Signal to queue Celery task when a document is created
@receiver(post_save, sender=Document)
def queue_document_processing(sender, instance, created, **kwargs):
    """
    When a document is created, queue a Celery task to generate summaries asynchronously.
    This prevents the admin interface from hanging during document creation.
    """
    # Skip if document should not be summarized
    if hasattr(instance, 'should_summarize') and not instance.should_summarize:
        logger.info(f"Skipping summarization for document {instance.id} as requested")
        return
    
    # Skip if this is marked to skip task queuing (to avoid infinite loops)
    if kwargs.get('skip_task', False):
        return
        
    # Only process if document is new or needs reprocessing
    if created or not instance.summarization_processed:
        # Import here to avoid circular imports
        from core.tasks import process_document_summaries
        
        # Queue the task
        process_document_summaries.delay(instance.id)
        logger.info(f"Queued document {instance.id} for background processing")