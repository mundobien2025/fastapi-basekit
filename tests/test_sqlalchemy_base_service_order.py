
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi_basekit.aio.sqlalchemy.service.base import BaseService

@pytest.mark.asyncio
async def test_base_service_order_by_default():
    # Mock Repository
    repo = MagicMock()
    repo.list_paginated = AsyncMock(return_value=([], 0))
    
    # Define a service with a default order_by
    class MyService(BaseService):
        order_by = "created_at"
        search_fields = ["name"]

    # Initialize service
    service = MyService(repository=repo)
    
    # 1. Test that it uses the default order_by when none is provided in list()
    await service.list()
    
    # Verify repo.list_paginated was called with the default order_by
    repo.list_paginated.assert_called_with(
        page=1,
        count=25,
        filters={},
        use_or=False,
        joins=None,
        order_by="created_at",
        search=None,
        search_fields=["name"]
    )
    
    # 2. Test that providing order_by in list() overrides the default
    await service.list(order_by="-updated_at")
    
    repo.list_paginated.assert_called_with(
        page=1,
        count=25,
        filters={},
        use_or=False,
        joins=None,
        order_by="-updated_at",
        search=None,
        search_fields=["name"]
    )

    # 3. Test that it also defaults search_fields correctly
    service_no_fields = BaseService(repository=repo)
    await service_no_fields.list()
    
    repo.list_paginated.assert_called_with(
        page=1,
        count=25,
        filters={},
        use_or=False,
        joins=None,
        order_by=None,
        search=None,
        search_fields=[]
    )
