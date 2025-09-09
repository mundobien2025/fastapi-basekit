from typing import ClassVar, Type

from fastapi import Depends
from pydantic import BaseModel

from ...controller.base import BaseController
from ..service.base import BaseService


class BeanieBaseController(BaseController):
    """BaseController para Beanie ODM (async).

    Hereda el comportamiento del controlador base y conecta con
    `Beanie` a través de su `BaseService` sin requerir `db` explícito.
    """

    service: BaseService = Depends()
    schema_class: ClassVar[Type[BaseModel]]

    # No es necesario sobreescribir métodos CRUD; el base usa
    # `self.service` con la firma de Beanie (sin `db`).
