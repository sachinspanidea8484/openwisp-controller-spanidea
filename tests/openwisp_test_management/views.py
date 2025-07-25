import json
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .swapper import load_model

TestCase = load_model("TestCase")
TestCategory = load_model("TestCategory")

# Simple test endpoint (no auth required for testing)
@csrf_exempt
def test_api(request):
    """Simple test endpoint to verify API is working"""
    return JsonResponse({
        'status': 'success',
        'message': 'Test Management API is working',
        'method': request.method,
        'path': request.path
    })

# List all categories
@staff_member_required
def list_categories(request):
    """List all categories for debugging"""
    categories = TestCategory.objects.all().values('id', 'name', 'code')
    return JsonResponse({
        'categories': list(categories),
        'count': TestCategory.objects.count()
    })

@staff_member_required
@require_http_methods(["GET"])
def get_category_test_cases(request, category_id):
    """API endpoint to get test cases for a category"""
    try:
        # Check if category exists
        if not TestCategory.objects.filter(id=category_id).exists():
            return JsonResponse({
                'error': 'Category not found',
                'category_id': str(category_id)
            }, status=404)
        
        test_cases = TestCase.objects.filter(
            category_id=category_id,
            is_active=True
        ).order_by('name')
        
        test_cases_data = []
        for tc in test_cases:
            test_cases_data.append({
                'id': str(tc.id),
                'name': tc.name,
                'test_case_id': tc.test_case_id,
                'test_type': tc.test_type,
                'test_type_display': tc.get_test_type_display()
            })
        
        return JsonResponse({
            'success': True,
            'category_id': str(category_id),
            'test_cases': test_cases_data,
            'count': len(test_cases_data)
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc(),
            'category_id': str(category_id)
        }, status=500)