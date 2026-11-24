"""One error type for handlers; the dispatcher turns it into the platform's {"detail": ...} shape."""


class ApiError(Exception):
    def __init__(self, status, detail, code=None):
        super().__init__(detail)
        self.status, self.detail, self.code = status, detail, code


NOT_FOUND = ("Not found", 404)


def not_found():
    return ApiError(404, "Not found")
