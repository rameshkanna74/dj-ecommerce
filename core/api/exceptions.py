"""
Translate domain exceptions raised by the service layer into API responses.

Error body: ``{"detail": "<message>", "code": "<code>"}``. Validation errors keep
DRF's field-keyed format.
"""

from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _domain_errors():
    from cart.services import CartError
    from orders.models import CouponError
    from orders.payments import PaymentError
    from orders.services import CheckoutError, OrderWorkflowError
    from support.services import TicketError

    return {
        CartError: (status.HTTP_400_BAD_REQUEST, "cart_error"),
        CouponError: (status.HTTP_400_BAD_REQUEST, "coupon_error"),
        TicketError: (status.HTTP_400_BAD_REQUEST, "ticket_error"),
        PaymentError: (status.HTTP_409_CONFLICT, "payment_error"),
        CheckoutError: (status.HTTP_409_CONFLICT, "checkout_conflict"),
        OrderWorkflowError: (status.HTTP_409_CONFLICT, "invalid_transition"),
        ProtectedError: (status.HTTP_409_CONFLICT, "protected"),
    }


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        return response
    for exc_type, (status_code, code) in _domain_errors().items():
        if isinstance(exc, exc_type):
            message = str(exc)
            if isinstance(exc, ProtectedError):
                message = "This object is still referenced by other records and cannot be deleted."
            return Response({"detail": message, "code": code}, status=status_code)
    return None
