# core/api_views.py - Updated for language-agnostic explanations
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
        # Initialize the explanation generator
        self.explanation_generator = ExplanationGenerator()

    def list(self, request):
        region_code = request.query_params.get('region', 'UG')
        language = request.query_params.get('language', 'en')
        
        logger.info(f"Fetching summaries for region {region_code} in language {language}")

        try:
            region = Region.objects.get(code=region_code)
        except Region.DoesNotExist:
            logger.warning(f"Region not found: {region_code}")
            return Response({'error': 'Region not found'}, status=404)

        # Get summaries for this region and language
        summaries = Summary.objects.filter(
            document__region=region, 
            language=language
        ).select_related('document').order_by('document__id')

        # Handle distinct documents for cases with multiple summaries per document
        unique_documents = set()
        unique_summaries = []
        for summary in summaries:
            if summary.document.id not in unique_documents:
                unique_documents.add(summary.document.id)
                unique_summaries.append(summary)
        
        logger.info(f"Found {len(unique_summaries)} unique summaries for region {region_code} in {language}")
        
        # Build response with all necessary data
        response_data = []
        for summary in unique_summaries:
            fact_check_data = self._get_fact_check_data(summary)
            
            # Get original text from the document
            original_text = self._get_original_excerpt(summary)
            
            # Generate explanation in English (always generate in English for consistency)
            explanation = self._get_real_explanation(summary, region.name)
            
            response_data.append({
                'id': summary.id,
                'document_title': summary.document.title,
                'text': summary.text,
                'original_text': original_text,
                'explanation': explanation,  # Always in English
                'language': summary.language,
                'created_at': summary.created_at,
                'factCheck': fact_check_data,
                'region_name': region.name  # Include region name for context
            })
            
        return Response(response_data)
    
    def _get_fact_check_data(self, summary):
        """Get fact check data for a summary from FactCheck model or document"""
        try:
            fact_check = FactCheck.objects.filter(summary=summary).first()
            if fact_check:
                return {
                    'source_url': fact_check.source_url,
                    'is_verified': fact_check.is_verified
                }
        except Exception as e:
            logger.error(f"Error fetching fact check for summary {summary.id}: {str(e)}")
        
        # Use document verification info if available
        try:
            document = summary.document
            if hasattr(document, 'is_verified'):
                return {
                    'source_url': document.source_url or '',
                    'is_verified': document.is_verified
                }
        except Exception as e:
            logger.error(f"Error accessing document verification info for summary {summary.id}: {str(e)}")
        
        # Default values as last resort
        return {
            'source_url': '',
            'is_verified': False
        }
    
    def _get_original_excerpt(self, summary):
        """Get the original text excerpt from the document, focused on SDG 5 & SDG 10"""
        try:
            # Check if we have stored original text
            if hasattr(summary, 'original_text') and summary.original_text:
                return summary.original_text
                
            # Define keywords for SDG 5 & SDG 10
            sdg_keywords = [
                # SDG 5 - Gender Equality keywords
                'gender', 'women', 'girls', 'female', 'maternal', 
                'gender-based violence', 'gender equality', 'gender parity',
                
                # SDG 10 - Reduced Inequalities keywords
                'inequality', 'equity', 'disparity', 'marginalized', 'vulnerable',
                'inclusion', 'inclusive', 'discrimination', 'minority',
                'differently abled', 'disabilities', 'equal opportunity'
            ]
            
            # Your PDF extraction logic here
            # This is a simplified placeholder - replace with your actual extraction code
            document = summary.document
            if not document.pdf_url:
                return "PDF document not available."
                
            # Import PDF processing utilities
            import pdfplumber
            import tempfile
            import requests
            import re
            
            # Download or access the PDF
            if document.pdf_url.startswith(('http://', 'https://')):
                response = requests.get(document.pdf_url, timeout=30)
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                    temp_file_path = temp_file.name
                    temp_file.write(response.content)
            else:
                temp_file_path = document.pdf_url
                
            # Extract relevant sections
            excerpts = []
            with pdfplumber.open(temp_file_path) as pdf:
                for i, page in enumerate(pdf.pages[:20]):
                    page_text = page.extract_text() or ''
                    if not page_text:
                        continue
                        
                    paragraphs = page_text.split('\n\n')
                    
                    for paragraph in paragraphs:
                        paragraph = paragraph.strip()
                        if not paragraph or len(paragraph) < 20:
                            continue
                            
                        if any(keyword.lower() in paragraph.lower() for keyword in sdg_keywords):
                            cleaned = re.sub(r'\s+', ' ', paragraph).strip()
                            excerpts.append(cleaned)
            
            # Clean up temp file if needed
            if document.pdf_url.startswith(('http://', 'https://')) and temp_file_path:
                import os
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                    
            # Return the extracted text or a fallback message
            if excerpts:
                result = '\n\n'.join(excerpts[:3])
                
                # Store for future use if the model has the field
                if hasattr(summary, 'original_text'):
                    summary.original_text = result
                    summary.save(update_fields=['original_text'])
                    
                return result
                
            return "No specific text related to gender equality or inequality reduction found in the document."
            
        except Exception as e:
            logger.error(f"Error extracting original text for summary {summary.id}: {str(e)}")
            return f"Error extracting original text: {str(e)}"
    
    def _get_real_explanation(self, summary, region_name=None):
        """
        Generate a real explanation using LLM, always in English for consistency.
        The text-to-speech feature on the frontend will handle reading it in the user's preferred language.
        """
        try:
            # Check if we have a stored explanation
            if hasattr(summary, 'explanation') and summary.explanation:
                return summary.explanation
                
            # Generate explanation in English, with region context if available
            region_context = region_name or getattr(summary.document.region, 'name', '')
            explanation = self.explanation_generator.generate_explanation(summary.text, region_context)
            
            # Validate explanation to ensure it’s not the prompt or invalid
            if not explanation or len(explanation) < 50 or "Be specific about both positive and negative impacts" in explanation:
                logger.warning(f"Invalid explanation for summary {summary.id}: {explanation[:100]}...")
                explanation = self.explanation_generator._get_fallback_explanation(region_context)
            
            # Store for future use if the model has the field
            if explanation and hasattr(summary, 'explanation'):
                summary.explanation = explanation
                summary.save(update_fields=['explanation'])
                
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating explanation for summary {summary.id}: {str(e)}")
            return self.explanation_generator._get_fallback_explanation(region_context)


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    lookup_field = 'code'