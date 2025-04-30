# core/api_views.py - Updated for English-only summaries with thorough logging
from rest_framework import viewsets
from rest_framework.response import Response
from .models import Document, Summary, FactCheck
from regions.models import Region
from .api_serializers import RegionSerializer
from .explanation_generator import ExplanationGenerator
import logging

logger = logging.getLogger(__name__)

class SummaryViewSet(viewsets.ViewSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.debug("Initializing SummaryViewSet with ExplanationGenerator")
        self.explanation_generator = ExplanationGenerator()
        logger.info("ExplanationGenerator initialized successfully")

    def list(self, request):
        logger.debug("Entering SummaryViewSet.list")
        region_code = request.query_params.get('region', 'UG')
        language = request.query_params.get('language', 'en')
        
        if language != 'en':
            logger.warning(f"Only English summaries are supported, received language={language}")
            return Response({'error': 'Only English summaries are supported'}, status=400)
        
        logger.info(f"Fetching summaries for region_code={region_code}, language={language}")

        try:
            logger.debug(f"Querying Region with code={region_code}")
            region = Region.objects.get(code=region_code)
            logger.debug(f"Found Region: id={region.id}, name={region.name}")
        except Region.DoesNotExist:
            logger.warning(f"Region not found: code={region_code}")
            return Response({'error': 'Region not found'}, status=404)

        logger.debug(f"Querying Summaries for region_id={region.id}, language={language}")
        summaries = Summary.objects.filter(
            document__region=region, 
            language=language
        ).select_related('document').order_by('document__id')
        logger.info(f"Retrieved {summaries.count()} summaries")

        unique_documents = set()
        unique_summaries = []
        for summary in summaries:
            if summary.document.id not in unique_documents:
                unique_documents.add(summary.document.id)
                unique_summaries.append(summary)
                logger.debug(f"Added unique summary: id={summary.id}, document_id={summary.document.id}")
        
        logger.info(f"Found {len(unique_summaries)} unique summaries for region_code={region_code}, language={language}")
        
        response_data = []
        for summary in unique_summaries:
            logger.debug(f"Processing summary: id={summary.id}, document_title={summary.document.title}")
            
            fact_check_data = self._get_fact_check_data(summary)
            logger.debug(f"Fact check data for summary {summary.id}: {fact_check_data}")
            
            original_text = self._get_original_excerpt(summary)
            logger.debug(f"Original text for summary {summary.id}: {original_text[:100]}...")
            
            explanation = self._get_real_explanation(summary, region.name)
            logger.debug(f"Explanation for summary {summary.id}: {explanation[:100]}...")
            
            response_data.append({
                'id': summary.id,
                'document_title': summary.document.title,
                'text': summary.text,
                'original_text': original_text,
                'explanation': explanation,
                'language': summary.language,
                'created_at': summary.created_at,
                'factCheck': fact_check_data,
                'region_name': region.name
            })
            logger.debug(f"Added response data for summary {summary.id}")
            
        logger.info(f"Returning response with {len(response_data)} summaries")
        logger.debug("Exiting SummaryViewSet.list")
        return Response(response_data)
    
    def _get_fact_check_data(self, summary):
        logger.debug(f"Entering _get_fact_check_data for summary {summary.id}")
        try:
            logger.debug(f"Querying FactCheck for summary {summary.id}")
            fact_check = FactCheck.objects.filter(summary=summary).first()
            if fact_check:
                logger.debug(f"Found FactCheck: source_url={fact_check.source_url}, is_verified={fact_check.is_verified}")
                return {
                    'source_url': fact_check.source_url,
                    'is_verified': fact_check.is_verified
                }
        except Exception as e:
            logger.error(f"Error fetching fact check for summary {summary.id}: {str(e)}")
        
        try:
            document = summary.document
            logger.debug(f"Using document verification info for document {document.id}")
            if hasattr(document, 'is_verified'):
                logger.debug(f"Document verification: source_url={document.source_url}, is_verified={document.is_verified}")
                return {
                    'source_url': document.source_url or '',
                    'is_verified': document.is_verified
                }
        except Exception as e:
            logger.error(f"Error accessing document verification info for summary {summary.id}: {str(e)}")
        
        logger.warning(f"No fact check or document verification info for summary {summary.id}, returning defaults")
        logger.debug("Exiting _get_fact_check_data")
        return {
            'source_url': '',
            'is_verified': False
        }
    
    def _get_original_excerpt(self, summary):
        logger.debug(f"Entering _get_original_excerpt for summary {summary.id}")
        try:
            if hasattr(summary, 'original_text') and summary.original_text:
                logger.debug(f"Using stored original_text for summary {summary.id}: {summary.original_text[:100]}...")
                return summary.original_text
                
            sdg_keywords = [
                'gender', 'women', 'girls', 'female', 'maternal', 
                'gender-based violence', 'gender equality', 'gender parity',
                'inequality', 'equity', 'disparity', 'marginalized', 'vulnerable',
                'inclusion', 'inclusive', 'discrimination', 'minority',
                'differently abled', 'disabilities', 'equal opportunity'
            ]
            logger.debug(f"Using SDG keywords: {sdg_keywords}")
            
            document = summary.document
            if not document.pdf_url:
                logger.warning(f"No PDF URL for document {document.id}")
                return "PDF document not available."
                
            import pdfplumber
            import tempfile
            import requests
            import re
            logger.debug(f"Downloading PDF: {document.pdf_url}")
            
            if document.pdf_url.startswith(('http://', 'https://')):
                response = requests.get(document.pdf_url, timeout=30)
                response.raise_for_status()
                logger.debug(f"PDF downloaded successfully, size={len(response.content)} bytes")
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                    temp_file_path = temp_file.name
                    temp_file.write(response.content)
            else:
                temp_file_path = document.pdf_url
                logger.debug(f"Using local PDF path: {temp_file_path}")
                
            excerpts = []
            with pdfplumber.open(temp_file_path) as pdf:
                logger.debug(f"Processing PDF with {len(pdf.pages)} pages")
                for i, page in enumerate(pdf.pages[:20]):
                    page_text = page.extract_text() or ''
                    if not page_text:
                        logger.debug(f"Page {i+1} has no text")
                        continue
                        
                    paragraphs = page_text.split('\n\n')
                    logger.debug(f"Page {i+1} has {len(paragraphs)} paragraphs")
                    
                    for paragraph in paragraphs:
                        paragraph = paragraph.strip()
                        if not paragraph or len(paragraph) < 20:
                            logger.debug(f"Skipping short/empty paragraph: {paragraph[:50]}...")
                            continue
                            
                        if any(keyword.lower() in paragraph.lower() for keyword in sdg_keywords):
                            cleaned = re.sub(r'\s+', ' ', paragraph).strip()
                            excerpts.append(cleaned)
                            logger.debug(f"Found SDG-relevant paragraph: {cleaned[:100]}...")
            
            if document.pdf_url.startswith(('http://', 'https://')) and temp_file_path:
                import os
                try:
                    os.unlink(temp_file_path)
                    logger.debug(f"Deleted temp file: {temp_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file_path}: {str(e)}")
                    
            if excerpts:
                result = '\n\n'.join(excerpts[:3])
                logger.info(f"Extracted {len(result)} characters of original text for summary {summary.id}")
                
                if hasattr(summary, 'original_text'):
                    summary.original_text = result
                    summary.save(update_fields=['original_text'])
                    logger.debug(f"Saved original_text to summary {summary.id}")
                    
                logger.debug("Exiting _get_original_excerpt with result")
                return result
                
            logger.warning(f"No SDG-relevant text found in document {document.id}")
            logger.debug("Exiting _get_original_excerpt with fallback")
            return "No specific text related to gender equality or inequality reduction found in the document."
            
        except Exception as e:
            logger.error(f"Error extracting original text for summary {summary.id}: {str(e)}")
            logger.debug("Exiting _get_original_excerpt with error")
            return f"Error extracting original text: {str(e)}"
    
    def _get_real_explanation(self, summary, region_name=None):
        logger.debug(f"Entering _get_real_explanation for summary {summary.id}")
        try:
            if hasattr(summary, 'explanation') and summary.explanation:
                logger.debug(f"Using stored explanation for summary {summary.id}: {summary.explanation[:100]}...")
                return summary.explanation
                
            region_context = region_name or getattr(summary.document.region, 'name', '')
            logger.debug(f"Generating explanation with region_context={region_context}")
            explanation = self.explanation_generator.generate_explanation(summary.text, region_context)
            
            if not explanation or len(explanation) < 50 or "Be specific about both positive and negative impacts" in explanation:
                logger.warning(f"Invalid explanation for summary {summary.id}: {explanation[:100]}...")
                explanation = self.explanation_generator._get_fallback_explanation(region_context)
                logger.debug(f"Using fallback explanation: {explanation[:100]}...")
            
            if explanation and hasattr(summary, 'explanation'):
                summary.explanation = explanation
                summary.save(update_fields=['explanation'])
                logger.debug(f"Saved explanation to summary {summary.id}")
                
            logger.info(f"Generated explanation for summary {summary.id}: {explanation[:100]}...")
            logger.debug("Exiting _get_real_explanation")
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating explanation for summary {summary.id}: {str(e)}")
            region_context = region_name or getattr(summary.document.region, 'name', '')
            fallback = self.explanation_generator._get_fallback_explanation(region_context)
            logger.debug(f"Using fallback explanation due to error: {fallback[:100]}...")
            logger.debug("Exiting _get_real_explanation with fallback")
            return fallback


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    logger.debug("Entering RegionViewSet")
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    lookup_field = 'code'
    logger.debug("Exiting RegionViewSet initialization")

# # core/api_views.py - Updated for English-only summaries with thorough logging
# from rest_framework import viewsets
# from rest_framework.response import Response
# from .models import Document, Summary, FactCheck
# from regions.models import Region
# from .api_serializers import RegionSerializer
# from .explanation_generator import ExplanationGenerator
# import logging

# logger = logging.getLogger(__name__)

# class SummaryViewSet(viewsets.ViewSet):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         logger.debug("Initializing SummaryViewSet with ExplanationGenerator")
#         self.explanation_generator = ExplanationGenerator()
#         logger.info("ExplanationGenerator initialized successfully")

#     def list(self, request):
#         logger.debug("Entering SummaryViewSet.list")
#         region_code = request.query_params.get('region', 'UG')
#         language = request.query_params.get('language', 'en')
        
#         if language != 'en':
#             logger.warning(f"Only English summaries are supported, received language={language}")
#             return Response({'error': 'Only English summaries are supported'}, status=400)
        
#         logger.info(f"Fetching summaries for region_code={region_code}, language={language}")

#         try:
#             logger.debug(f"Querying Region with code={region_code}")
#             region = Region.objects.get(code=region_code)
#             logger.debug(f"Found Region: id={region.id}, name={region.name}")
#         except Region.DoesNotExist:
#             logger.warning(f"Region not found: code={region_code}")
#             return Response({'error': 'Region not found'}, status=404)

#         logger.debug(f"Querying Summaries for region_id={region.id}, language={language}")
#         summaries = Summary.objects.filter(
#             document__region=region, 
#             language=language
#         ).select_related('document').order_by('document__id')
#         logger.info(f"Retrieved {summaries.count()} summaries")

#         unique_documents = set()
#         unique_summaries = []
#         for summary in summaries:
#             if summary.document.id not in unique_documents:
#                 unique_documents.add(summary.document.id)
#                 unique_summaries.append(summary)
#                 logger.debug(f"Added unique summary: id={summary.id}, document_id={summary.document.id}")
        
#         logger.info(f"Found {len(unique_summaries)} unique summaries for region_code={region_code}, language={language}")
        
#         response_data = []
#         for summary in unique_summaries:
#             logger.debug(f"Processing summary: id={summary.id}, document_title={summary.document.title}")
            
#             fact_check_data = self._get_fact_check_data(summary)
#             logger.debug(f"Fact check data for summary {summary.id}: {fact_check_data}")
            
#             original_text = self._get_original_excerpt(summary)
#             logger.debug(f"Original text for summary {summary.id}: {original_text[:100]}...")
            
#             explanation = self._get_real_explanation(summary, region.name)
#             logger.debug(f"Explanation for summary {summary.id}: {explanation[:100]}...")
            
#             response_data.append({
#                 'id': summary.id,
#                 'document_title': summary.document.title,
#                 'text': summary.text,
#                 'original_text': original_text,
#                 'explanation': explanation,
#                 'language': summary.language,
#                 'created_at': summary.created_at,
#                 'factCheck': fact_check_data,
#                 'region_name': region.name
#             })
#             logger.debug(f"Added response data for summary {summary.id}")
            
#         logger.info(f"Returning response with {len(response_data)} summaries")
#         logger.debug("Exiting SummaryViewSet.list")
#         return Response(response_data)
    
#     def _get_fact_check_data(self, summary):
#         logger.debug(f"Entering _get_fact_check_data for summary {summary.id}")
#         try:
#             logger.debug(f"Querying FactCheck for summary {summary.id}")
#             fact_check = FactCheck.objects.filter(summary=summary).first()
#             if fact_check:
#                 logger.debug(f"Found FactCheck: source_url={fact_check.source_url}, is_verified={fact_check.is_verified}")
#                 return {
#                     'source_url': fact_check.source_url,
#                     'is_verified': fact_check.is_verified
#                 }
#         except Exception as e:
#             logger.error(f"Error fetching fact check for summary {summary.id}: {str(e)}")
        
#         try:
#             document = summary.document
#             logger.debug(f"Using document verification info for document {document.id}")
#             if hasattr(document, 'is_verified'):
#                 logger.debug(f"Document verification: source_url={document.source_url}, is_verified={document.is_verified}")
#                 return {
#                     'source_url': document.source_url or '',
#                     'is_verified': document.is_verified
#                 }
#         except Exception as e:
#             logger.error(f"Error accessing document verification info for summary {summary.id}: {str(e)}")
        
#         logger.warning(f"No fact check or document verification info for summary {summary.id}, returning defaults")
#         logger.debug("Exiting _get_fact_check_data")
#         return {
#             'source_url': '',
#             'is_verified': False
#         }
    
#     def _get_original_excerpt(self, summary):
#         logger.debug(f"Entering _get_original_excerpt for summary {summary.id}")
#         try:
#             if hasattr(summary, 'original_text') and summary.original_text:
#                 logger.debug(f"Using stored original_text for summary {summary.id}: {summary.original_text[:100]}...")
#                 return summary.original_text
                
#             sdg_keywords = [
#                 'gender', 'women', 'girls', 'female', 'maternal', 
#                 'gender-based violence', 'gender equality', 'gender parity',
#                 'inequality', 'equity', 'disparity', 'marginalized', 'vulnerable',
#                 'inclusion', 'inclusive', 'discrimination', 'minority',
#                 'differently abled', 'disabilities', 'equal opportunity'
#             ]
#             logger.debug(f"Using SDG keywords: {sdg_keywords}")
            
#             document = summary.document
#             if not document.pdf_url:
#                 logger.warning(f"No PDF URL for document {document.id}")
#                 return "PDF document not available."
                
#             import pdfplumber
#             import tempfile
#             import requests
#             import re
#             logger.debug(f"Downloading PDF: {document.pdf_url}")
            
#             if document.pdf_url.startswith(('http://', 'https://')):
#                 response = requests.get(document.pdf_url, timeout=30)
#                 response.raise_for_status()
#                 logger.debug(f"PDF downloaded successfully, size={len(response.content)} bytes")
#                 with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
#                     temp_file_path = temp_file.name
#                     temp_file.write(response.content)
#             else:
#                 temp_file_path = document.pdf_url
#                 logger.debug(f"Using local PDF path: {temp_file_path}")
                
#             excerpts = []
#             with pdfplumber.open(temp_file_path) as pdf:
#                 logger.debug(f"Processing PDF with {len(pdf.pages)} pages")
#                 for i, page in enumerate(pdf.pages[:20]):
#                     page_text = page.extract_text() or ''
#                     if not page_text:
#                         logger.debug(f"Page {i+1} has no text")
#                         continue
                        
#                     paragraphs = page_text.split('\n\n')
#                     logger.debug(f"Page {i+1} has {len(paragraphs)} paragraphs")
                    
#                     for paragraph in paragraphs:
#                         paragraph = paragraph.strip()
#                         if not paragraph or len(paragraph) < 20:
#                             logger.debug(f"Skipping short/empty paragraph: {paragraph[:50]}...")
#                             continue
                            
#                         if any(keyword.lower() in paragraph.lower() for keyword in sdg_keywords):
#                             cleaned = re.sub(r'\s+', ' ', paragraph).strip()
#                             excerpts.append(cleaned)
#                             logger.debug(f"Found SDG-relevant paragraph: {cleaned[:100]}...")
            
#             if document.pdf_url.startswith(('http://', 'https://')) and temp_file_path:
#                 import os
#                 try:
#                     os.unlink(temp_file_path)
#                     logger.debug(f"Deleted temp file: {temp_file_path}")
#                 except Exception as e:
#                     logger.warning(f"Failed to delete temp file {temp_file_path}: {str(e)}")
                    
#             if excerpts:
#                 result = '\n\n'.join(excerpts[:3])
#                 logger.info(f"Extracted {len(result)} characters of original text for summary {summary.id}")
                
#                 if hasattr(summary, 'original_text'):
#                     summary.original_text = result
#                     summary.save(update_fields=['original_text'])
#                     logger.debug(f"Saved original_text to summary {summary.id}")
                    
#                 logger.debug("Exiting _get_original_excerpt with result")
#                 return result
                
#             logger.warning(f"No SDG-relevant text found in document {document.id}")
#             logger.debug("Exiting _get_original_excerpt with fallback")
#             return "No specific text related to gender equality or inequality reduction found in the document."
            
#         except Exception as e:
#             logger.error(f"Error extracting original text for summary {summary.id}: {str(e)}")
#             logger.debug("Exiting _get_original_excerpt with error")
#             return f"Error extracting original text: {str(e)}"
    
#     def _get_real_explanation(self, summary, region_name=None):
#         logger.debug(f"Entering _get_real_explanation for summary {summary.id}")
#         try:
#             if hasattr(summary, 'explanation') and summary.explanation:
#                 logger.debug(f"Using stored explanation for summary {summary.id}: {summary.explanation[:100]}...")
#                 return summary.explanation
                
#             region_context = region_name or getattr(summary.document.region, 'name', '')
#             logger.debug(f"Generating explanation with region_context={region_context}")
#             explanation = self.explanation_generator.generate_explanation(summary.text, region_context)
            
#             if not explanation or len(explanation) < 50 or "Be specific about both positive and negative impacts" in explanation:
#                 logger.warning(f"Invalid explanation for summary {summary.id}: {explanation[:100]}...")
#                 explanation = self.explanation_generator._get_fallback_explanation(region_context)
#                 logger.debug(f"Using fallback explanation: {explanation[:100]}...")
            
#             if explanation and hasattr(summary, 'explanation'):
#                 summary.explanation = explanation
#                 summary.save(update_fields=['explanation'])
#                 logger.debug(f"Saved explanation to summary {summary.id}")
                
#             logger.info(f"Generated explanation for summary {summary.id}: {explanation[:100]}...")
#             logger.debug("Exiting _get_real_explanation")
#             return explanation
            
#         except Exception as e:
#             logger.error(f"Error generating explanation for summary {summary.id}: {str(e)}")
#             region_context = region_name or getattr(summary.document.region, 'name', '')
#             fallback = self.explanation_generator._get_fallback_explanation(region_context)
#             logger.debug(f"Using fallback explanation due to error: {fallback[:100]}...")
#             logger.debug("Exiting _get_real_explanation with fallback")
#             return fallback


# class RegionViewSet(viewsets.ReadOnlyModelViewSet):
#     logger.debug("Entering RegionViewSet")
#     queryset = Region.objects.all()
#     serializer_class = RegionSerializer
#     lookup_field = 'code'
#     logger.debug("Exiting RegionViewSet initialization")