from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    """Custom exception handler for consistent error responses"""
    response = exception_handler(exc, context)
    
    if response is not None:
        response.data = {
            'error': {
                'code': exc.__class__.__name__,
                'message': str(exc),
                'details': response.data
            }
        }
    
    return response