# apps/accounts/utils/responses.py

from rest_framework.response import Response

def success_response(message, data=None, status_code=200):
    return Response(
        {
            "success": True,
            "status_code": status_code,
            "message": message,
            "data": data,
        },
        status=status_code,
    )


def error_response(message, errors=None, status_code=400):
    return Response(
        {
            "success": False,
            "status_code": status_code,
            "message": message,
            "errors": errors,
        },
        status=status_code,
    )