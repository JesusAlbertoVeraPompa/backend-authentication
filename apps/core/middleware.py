# apps/core/middleware.py

from django.http import JsonResponse

class RoleRequiredMiddleware:
    """
    Middleware que protege rutas sensibles basadas en el rol del usuario.

    - Si la ruta comienza con /api/admin/ solo permite usuarios con role='admin'
    - Evita errores cuando el usuario no está autenticado
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Verifica rutas protegidas de admin
        if request.path.startswith('/api/admin/'):
            # Si el usuario no está autenticado o no es admin → denegar acceso
            if not request.user.is_authenticated or request.user.role != 'admin':
                return JsonResponse({"error": "Acceso denegado"}, status=403)

        return self.get_response(request)