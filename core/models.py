# core/models.py - Updated with fallback explanations
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from regions.models import Region
import logging

logger = logging.getLogger(__name__)

class Document(models.Model):
    title = models.CharField(max_length=255)
    pdf_url = models.URLField(max_length=500)
    source_url = models.URLField(max_length=500, blank=True, default='')
    is_verified = models.BooleanField(default=False)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    summarization_processed = models.BooleanField(default=False)

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

class Summary(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='summaries')
    text = models.TextField()
    original_text = models.TextField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=10, choices=[('en', 'English'), ('sw', 'Swahili')])
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
    summary = models.ForeignKey(Summary, on_delete=models.CASCADE, related_name='fact_checks')
    source_url = models.URLField(max_length=500)
    is_verified = models.BooleanField(default=False)
    checked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FactCheck for {self.summary}"

# Signal to auto-generate summaries when a document is created
@receiver(post_save, sender=Document)
def create_summaries(sender, instance, created, **kwargs):
    """When a document is created, automatically generate summaries in all supported languages."""
    if created or not instance.summarization_processed:
        try:
            # Avoid circular import
            from core.summarizer import Summarizer
            
            logger.info(f"Auto-generating summaries for document: {instance.title}")
            summarizer = Summarizer()
            
            # Generate summaries in supported languages
            languages = ['en', 'sw']
            
            for lang in languages:
                # Check if summary already exists
                if not Summary.objects.filter(document=instance, language=lang).exists():
                    try:
                        # Generate summary with retries and timeouts
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                summary_text = summarizer.summarize_document(instance.pdf_url, language=lang)
                                break
                            except Exception as e:
                                if attempt == max_retries - 1:
                                    # Last attempt failed, use default text
                                    logger.error(f"All attempts to summarize document {instance.id} failed: {str(e)}")
                                    summary_text = f"This document contains budget information for {instance.title}."
                                else:
                                    # Retry
                                    logger.warning(f"Attempt {attempt+1} to summarize document {instance.id} failed: {str(e)}, retrying...")
                                    continue
                        
                        # Create summary with the text (might be default if all attempts failed)
                        summary = Summary.objects.create(
                            document=instance,
                            text=summary_text,
                            language=lang
                        )
                        
                        # Generate explanation using ExplanationGenerator
                        try:
                            from core.explanation_generator import ExplanationGenerator
                            explanation_generator = ExplanationGenerator()
                            region_name = instance.region.name if instance.region else ""
                            explanation = explanation_generator.generate_explanation(summary_text, region_name)
                            
                            # Update the summary with the explanation
                            summary.explanation = explanation
                            summary.save(update_fields=['explanation'])
                            
                        except Exception as e:
                            logger.error(f"Error generating explanation for summary {summary.id}: {str(e)}")
                            # The default explanation will be created by the Summary.save() method
                            
                        logger.info(f"Created {lang} summary for {instance.title}")
                            
                    except Exception as e:
                        logger.error(f"Error creating {lang} summary for {instance.title}: {str(e)}")
                        # Create a placeholder summary with error message
                        Summary.objects.create(
                            document=instance,
                            text=f"Error generating summary: {str(e)}",
                            language=lang
                        )
            
            # Update the flag to indicate summarization has been attempted
            instance.summarization_processed = True
            instance.save(update_fields=['summarization_processed'])
            
        except Exception as e:
            logger.error(f"Failed to generate summaries for document {instance.id}: {str(e)}")