# System
from typing import Optional, Union

# fastapi
from fastapi import status


class APIException(Exception):
    def __init__(
        self,
        message: str,
        status_code: str,
        status: int,
        data: Optional[Union[dict, str]] = None,
    ):
        """
        Excepción base para la API.

        :param message: Mensaje descriptivo del error.
        :param status_code: Código de error personalizado
        :param data: Información adicional opcional.
        """
        self.message = message
        self.status_code = status_code
        self.status = status
        if isinstance(data, dict):
            self.data = data.copy()
        else:
            self.data = data

    def __str__(self):
        return f"{self.status_code}: {self.message} | {self.data}"


# Excepción específica para errores de JWT
class JWTAuthenticationException(APIException):
    def __init__(
        self,
        data: Optional[Union[dict, str]] = None,
        message: str = "Error en la autenticación JWT",
    ):
        super().__init__(
            message=message,
            status_code="JWT_ERROR",
            data=data,
            status=status.HTTP_401_UNAUTHORIZED,
        )


# Excepción específica para errores de validación
class ValidationException(APIException):
    def __init__(
        self,
        data: Optional[Union[dict, str]] = None,
        message: str = "Error de validación",
    ):
        super().__init__(
            message=message,
            status_code="VALIDATION_ERROR",
            data=data,
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


# Excepción específica para errores de integridad en la base de datos
class DatabaseIntegrityException(APIException):
    def __init__(
        self,
        data: Optional[Union[dict, str]] = None,
        message: str = "Registro ya existe",
    ):
        super().__init__(
            message=message,
            status_code="DATABASE_INTEGRITY_ERROR",
            data=data,
            status=status.HTTP_400_BAD_REQUEST,
        )


class PermissionException(APIException):
    def __init__(
        self,
        data: Optional[Union[dict, str]] = None,
        message: str = "Usted no tiene permisos para ejecutar esta acción",
    ):
        super().__init__(
            message=message,
            status_code="PERMISSIONS",
            data=data,
            status=status.HTTP_403_FORBIDDEN,
        )


class GlobalException(APIException):
    def __init__(
        self,
        data: Optional[Union[dict, str]] = None,
        message: str = "Ocurrió un error desconocido",
    ):
        super().__init__(
            message=message,
            status_code="ERROR_GENERIC",
            data=data,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class NotFoundException(APIException):
    def __init__(
        self,
        data: Optional[Union[dict, str]] = None,
        message: str = "No se encontró",
    ):
        super().__init__(
            message=message,
            status_code="NOT_FOUND",
            data=data,
            status=status.HTTP_404_NOT_FOUND,
        )
