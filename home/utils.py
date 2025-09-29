from rest_framework.views import exception_handler
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    # default DRF exception handler
    response = exception_handler(exc, context)

    if response is None:
        # log exception traceback
        logger.exception(f"Unhandled exception: {exc}")

    return response
