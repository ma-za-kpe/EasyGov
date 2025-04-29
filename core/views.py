# Views for the core app
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def health_check(request):
    # Simple health check endpoint to verify API is running
    return Response({'status': 'OK', 'message': 'EasyGov API is running'})