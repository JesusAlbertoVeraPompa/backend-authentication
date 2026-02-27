# config/exceptions.py

from rest_framework.views import exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        return Response(
            {
                "success": False,
                "status_code": response.status_code,
                "message": "Ocurrió un error en la solicitud",
                "errors": response.data,
            },
            status=response.status_code,
        )

    # Error 500 no controlado
    return Response(
        {
            "success": False,
            "status_code": 500,
            "message": "Error interno del servidor. Intenta nuevamente más tarde.",
            "errors": None,
        },
        status=500,
    )