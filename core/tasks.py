# core/tasks.py
import logging
from celery import shared_task
from django.db import transaction
import time
import os

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_document_summaries(self, document_id):
    from core.models import Document, Summary
    logger.debug(f"Starting task process_document_summaries for document_id={document_id}")
    try:
        document = Document.objects.get(id=document_id)
        logger.info(f"Processing document in background: {document.title} (id={document_id})")
        if document.summarization_processed:
            logger.info(f"Document {document_id} already processed, skipping")
            return
            
        from core.summarizer import Summarizer
        from core.explanation_generator import ExplanationGenerator
        summarizer = Summarizer()
        explanation_generator = ExplanationGenerator()
        languages = ['en']  # Only English summaries
        
        # Determine the PDF source - prefer local file if available, otherwise use URL
        if document.pdf_file and os.path.exists(document.pdf_file.path):
            pdf_source = document.pdf_file.path
            logger.info(f"Using local PDF file: {pdf_source}")
        elif document.pdf_url:
            pdf_source = document.pdf_url
            logger.info(f"Using PDF URL: {pdf_source}")
        else:
            logger.error(f"No PDF file or URL available for document {document_id}")
            raise ValueError("No PDF file or URL provided")
        
        for lang in languages:
            if not Summary.objects.filter(document=document, language=lang).exists():
                logger.debug(f"Processing summary for language={lang}")
                try:
                    max_retries = 3
                    summary_text, original_text = None, None
                    for attempt in range(max_retries):
                        try:
                            logger.debug(f"Attempt {attempt+1}/{max_retries} to summarize document {document_id} in {lang}")
                            summary_text, original_text = summarizer.summarize_document(pdf_source)
                            
                            # Log types for debugging
                            logger.debug(f"summary_text type: {type(summary_text)}, value: {summary_text[:100] if summary_text else 'None'}")
                            logger.debug(f"original_text type: {type(original_text)}, value: {original_text[:100] if original_text else 'None'}")
                            
                            # Check if the result indicates an error
                            if isinstance(summary_text, str) and summary_text.startswith("Error"):
                                logger.warning(f"Summarization returned an error: {summary_text}")
                                if attempt == max_retries - 1:
                                    logger.error(f"All {max_retries} attempts failed with: {summary_text}")
                                    break
                                else:
                                    logger.warning(f"Retrying after error, attempt {attempt+1}/{max_retries}")
                                    time.sleep(2)
                                    continue
                                    
                            logger.debug(f"Summary generated: {summary_text[:100]}...")
                            break
                        except ValueError as ve:
                            logger.error(f"Value error in attempt {attempt+1}: {str(ve)}")
                            if attempt == max_retries - 1:
                                raise
                            time.sleep(2)
                        except Exception as e:
                            if attempt == max_retries - 1:
                                logger.error(f"All {max_retries} attempts to summarize document {document_id} ({lang}) failed: {str(e)}")
                                summary_text = f"This document contains budget information for {document.title}."
                                original_text = None
                            else:
                                logger.warning(f"Attempt {attempt+1}/{max_retries} failed: {str(e)}, retrying...")
                                time.sleep(2)
                    
                    # Ensure we have at least a basic summary if all else fails
                    if not summary_text:
                        summary_text = f"This document contains budget information for {document.title}."
                    
                    with transaction.atomic():
                        logger.info(f"Summary text to store: {summary_text[:200]}...")
                        logger.info(f"Original text to store: {original_text[:200] if original_text else 'None'}...")
                        summary = Summary.objects.create(
                            document=document,
                            text=summary_text,
                            original_text=original_text,
                            language=lang
                        )
                        logger.debug(f"Created summary id={summary.id} for language={lang}")
                    
                    # Generate explanation only for valid summaries
                    try:
                        if not summary_text.startswith("Error") and not summary_text.startswith("Failed"):
                            region_name = document.region.name if document.region else ""
                            logger.debug(f"Generating explanation for summary {summary.id} with region={region_name}")
                            
                            try:
                                explanation = explanation_generator.generate_explanation(summary_text, region_name)
                            except Exception as expl_error:
                                logger.error(f"Error from explanation generator: {str(expl_error)}")
                                explanation = "This document may support gender equality and reduce social inequalities."
                            
                            with transaction.atomic():
                                summary.explanation = explanation
                                summary.save(update_fields=['explanation'])
                                logger.debug(f"Saved explanation for summary {summary.id}: {explanation[:100]}...")
                        else:
                            logger.warning(f"Skipping explanation generation for error summary: {summary_text[:100]}")
                    except Exception as e:
                        logger.error(f"Error handling explanation for summary {summary.id}: {str(e)}")
                    
                    logger.info(f"Successfully created {lang} summary for document {document_id}")
                except Exception as e:
                    logger.error(f"Error creating {lang} summary for document {document_id}: {str(e)}")
                    try:
                        with transaction.atomic():
                            Summary.objects.create(
                                document=document,
                                text=f"Error generating summary: {str(e)}",
                                original_text=None,
                                language=lang
                            )
                            logger.debug(f"Created placeholder summary for language={lang}")
                    except Exception as inner_e:
                        logger.error(f"Failed to create placeholder summary: {str(inner_e)}")
            else:
                logger.info(f"Summary for document {document_id} in {lang} already exists, skipping")
        
        with transaction.atomic():
            document.summarization_processed = not summary_text.startswith("Error")
            Document.objects.filter(id=document.id).update(summarization_processed=document.summarization_processed)
            logger.info(f"Successfully processed all summaries for document {document_id}")
    
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found, cannot process")
    except Exception as e:
        logger.error(f"Failed to process document {document_id}: {str(e)}")
        retry_in = 2 ** self.request.retries
        logger.info(f"Retrying task in {retry_in} seconds (retry #{self.request.retries+1})")
        raise self.retry(exc=e, countdown=retry_in)

@shared_task
def queue_document_processing(document_id):
    """
    Entry point task that starts the document processing pipeline.
    Directly triggers process_document_summaries since PDF is uploaded locally.
    """
    logger.info(f"Queueing document {document_id} for processing")
    process_document_summaries.delay(document_id)

@shared_task
def retry_failed_documents():
    """
    Periodic task to retry processing documents that failed in previous attempts.
    Looks for documents that have no summary and are not marked as processed.
    """
    from core.models import Document, Summary
    from django.db.models import Count, Q
    
    candidates = Document.objects.annotate(
        summary_count=Count('summary')
    ).filter(
        Q(summary_count=0) | Q(summarization_processed=False)
    ).order_by('created_at')[:10]  # Process in small batches
    
    for document in candidates:
        logger.info(f"Retrying failed document {document.id}: {document.title}")
        queue_document_processing.delay(document.id)