class ApiError(Exception):
    def __init__(self, detail: str, *, status_code: int = 500, code: str | None = None):
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(detail)


class ApiUnavailable(ApiError):
    def __init__(self, detail: str = "La API de Fulbacho no está disponible."):
        super().__init__(detail, status_code=503, code="api_unavailable")
