from fastapi import HTTPException


class BaseAPIError(HTTPException):
    """Base class for API exceptions."""

    status_code = 500
    detail = "Internal server error"

    def __init__(
        self, detail: str | None = None, status_code: int | None = None
    ) -> None:
        super().__init__(
            status_code=status_code or self.__class__.status_code,
            detail=detail or self.__class__.detail,
        )


class UserNotFoundError(BaseAPIError):
    status_code = 404
    detail = "User not found"


class UsernameAlreadyExistsError(BaseAPIError):
    status_code = 400
    detail = "Username already in use"


class EmailAlreadyInUseError(BaseAPIError):
    status_code = 400
    detail = "Email already in use"


class InvalidCredentialsError(BaseAPIError):
    status_code = 401
    detail = "Invalid username or password"


class InactiveUserError(BaseAPIError):
    status_code = 403
    detail = "User account is disabled"


class PermissionDeniedError(BaseAPIError):
    status_code = 403
    detail = "Permission denied"


class PasswordValidationError(BaseAPIError):
    status_code = 400
    detail = "Password does not meet strength requirements"


class InvalidTokenError(BaseAPIError):
    status_code = 401
    detail = "Invalid or expired token"


class FaceVectorNotFoundError(BaseAPIError):
    status_code = 404
    detail = "Face vector not found"


class FaceVectorLimitExceededError(BaseAPIError):
    status_code = 422
    detail = "Face vector limit reached (max 100 per user)"


class NoFaceDetectedError(BaseAPIError):
    status_code = 400
    detail = "No face detected in the provided image"


class InvalidImageError(BaseAPIError):
    status_code = 400
    detail = "Could not decode the provided image"


class DoorNotFoundError(BaseAPIError):
    status_code = 404
    detail = "Door not found"


class DoorNameAlreadyExistsError(BaseAPIError):
    status_code = 400
    detail = "Door name already in use"


class DoorMqttIdAlreadyExistsError(BaseAPIError):
    status_code = 400
    detail = "Door MQTT ID already in use"


class DoorInactiveError(BaseAPIError):
    status_code = 409
    detail = "Door is inactive"


class DoorMqttNotConfiguredError(BaseAPIError):
    status_code = 409
    detail = "Door MQTT ID is not configured"
