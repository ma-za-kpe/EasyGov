# core/tasks.py
import logging
from celery import shared_task
from django.db import transaction
import time

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_document_summaries(self, document_id):
    """
    Process document summarization asynchronously with Celery.
    
    This task:
    1. Loads the document by ID
    2. Processes summarization in both English and Swahili
    3. Generates explanations for each summary
    4. Handles errors and provides retries
    """
    from core.models import Document, Summary
    
    try:
        # Get the document - if it doesn't exist, task will fail
        document = Document.objects.get(id=document_id)
        logger.info(f"Processing document in background: {document.title}")
        
        # Skip if already processed (unless it's a manual reprocess)
        if document.summarization_processed:
            logger.info(f"Document {document_id} already processed, skipping")
            return
            
        # Import here to avoid circular imports
        from core.summarizer import Summarizer
        from core.explanation_generator import ExplanationGenerator
        
        # Initialize our processing classes
        summarizer = Summarizer()
        explanation_generator = ExplanationGenerator()
        
        # Generate summaries in supported languages
        languages = ['en', 'sw']
        
        for lang in languages:
            # Check if summary already exists for this language
            if not Summary.objects.filter(document=document, language=lang).exists():
                try:
                    # Generate summary with timeout handling to prevent hanging
                    max_retries = 3
                    summary_text = None
                    
                    for attempt in range(max_retries):
                        try:
                            # This is where the heavy processing happens
                            summary_text = summarizer.summarize_document(document.pdf_url, language=lang)
                            break
                        except Exception as e:
                            if attempt == max_retries - 1:
                                # Last attempt failed, use default text
                                logger.error(f"All {max_retries} attempts to summarize document {document_id} ({lang}) failed: {str(e)}")
                                summary_text = f"This document contains budget information for {document.title}."
                            else:
                                # Retry after a short delay
                                logger.warning(f"Attempt {attempt+1}/{max_retries} to summarize document {document_id} ({lang}) failed: {str(e)}, retrying...")
                                time.sleep(2)  # Wait 2 seconds before retrying
                    
                    # Create a new summary with the generated text
                    with transaction.atomic():
                        summary = Summary.objects.create(
                            document=document,
                            text=summary_text,
                            language=lang
                        )
                    
                    # Generate explanation for the summary
                    try:
                        # Get region name for context
                        region_name = document.region.name if document.region else ""
                        
                        # Generate the explanation
                        explanation = explanation_generator.generate_explanation(summary_text, region_name)
                        
                        # Update the summary with the explanation
                        with transaction.atomic():
                            summary.explanation = explanation
                            summary.save(update_fields=['explanation'])
                        
                    except Exception as e:
                        logger.error(f"Error generating explanation for summary {summary.id}: {str(e)}")
                        # The default explanation will be applied by the model's save method
                    
                    logger.info(f"Successfully created {lang} summary for document {document_id}")
                        
                except Exception as e:
                    logger.error(f"Error creating {lang} summary for document {document_id}: {str(e)}")
                    
                    # Create a placeholder summary with error message
                    try:
                        with transaction.atomic():
                            Summary.objects.create(
                                document=document,
                                text=f"Error generating summary: {str(e)}",
                                language=lang
                            )
                    except Exception as inner_e:
                        logger.error(f"Failed to create placeholder summary: {str(inner_e)}")
            else:
                logger.info(f"Summary for document {document_id} in {lang} already exists, skipping")
        
        # Mark the document as processed
        with transaction.atomic():
            document.summarization_processed = True
            # Use .update() to avoid triggering the post_save signal again
            Document.objects.filter(id=document.id).update(summarization_processed=True)
            
        logger.info(f"Successfully processed all summaries for document {document_id}")
        
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found, cannot process")
    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {str(e)}")
        # Retry with exponential backoff (wait 2^retry_count seconds)
        retry_in = 2 ** self.request.retries
        logger.info(f"Retrying task in {retry_in} seconds (retry #{self.request.retries+1})")
        raise self.retry(exc=e, countdown=retry_in)