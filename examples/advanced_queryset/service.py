"""Service avanzado con queryset personalizado."""

from sqlalchemy import Select, func, select
from sqlalchemy.orm import aliased
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService
from .models import User, Referral, Order


class UserService(BaseService):
    """Service con queryset personalizado para agregaciones."""

    search_fields = ["name", "email"]
    duplicate_check_fields = ["email"]

    def build_queryset(self) -> Select:
        """
        Construye un queryset personalizado que incluye:
        - COUNT de referidos por usuario
        - SUM y COUNT de órdenes por usuario
        """
        # Alias para las tablas relacionadas
        referral_alias = aliased(Referral)
        order_alias = aliased(Order)

        # Query base con agregaciones
        query = (
            select(
                User,
                func.count(func.distinct(referral_alias.id)).label(
                    "referidos_count"
                ),
                func.count(func.distinct(order_alias.id)).label("total_orders"),
                func.coalesce(func.sum(order_alias.total), 0).label(
                    "total_spent"
                ),
            )
            .outerjoin(referral_alias, User.id == referral_alias.user_id)
            .outerjoin(order_alias, User.id == order_alias.user_id)
            .group_by(User.id)
        )

        return query

