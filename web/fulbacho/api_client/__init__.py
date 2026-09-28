from .endpoints import FulbachoAPI
from .exceptions import ApiError, ApiUnavailable


def api_for(django_request=None) -> FulbachoAPI:
    return FulbachoAPI(django_request)


__all__ = ["ApiError", "ApiUnavailable", "FulbachoAPI", "api_for"]
