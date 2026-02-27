# apps/core/decorators.py

from functools import wraps
from django.http import JsonResponse

def role_required(allowed_roles):
    """
    Decorador para restringir acceso por roles.
    
    Uso:
    @role_required(['admin'])
    def my_view(request):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"error": "No autenticado"}, status=401)

            if request.user.role not in allowed_roles:
                return JsonResponse({"error": "Permisos insuficientes"}, status=403)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator