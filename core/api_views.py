# core/api_views.py
from rest_framework import viewsets
from rest_framework.response import Response
from .models import Document, Summary
from .summarizer import Summarizer
from regions.models import Region

class SummaryViewSet(viewsets.ViewSet):
    def list(self, request):
        region_code = request.query_params.get('region', 'UG')
        language = request.query_params.get('language', 'en')

        try:
            region = Region.objects.get(code=region_code)
        except Region.DoesNotExist:
            return Response({'error': 'Region not found'}, status=404)

        # Get or create summaries
        documents = Document.objects.filter(region=region)
        summarizer = Summarizer()
        
        for doc in documents:
            # Check if summary exists
            summary_exists = Summary.objects.filter(document=doc, language=language).exists()
            if not summary_exists:
                summary_text = summarizer.summarize_document(doc.pdf_url, language=language)
                Summary.objects.create(
                    document=doc,
                    text=summary_text,
                    language=language
                )

        summaries = Summary.objects.filter(document__region=region, language=language)
        return Response([
            {
                'id': summary.id,
                'document_title': summary.document.title,
                'text': summary.text,
                'language': summary.language,
                'created_at': summary.created_at
            } for summary in summaries
        ])