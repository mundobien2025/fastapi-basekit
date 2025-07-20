# FastAPI restfull

This package provides reusable asynchronous utilities for building FastAPI applications with the Beanie ODM. It includes base classes for repositories, services and controllers as well as common exception handlers, response schemas and helper services such as JWT token management and file uploads to Supabase.

## Installation

```bash
pip install fastapi-restfull
```

## Usage

Import the base classes and extend them in your project:

```python
from fastapi_restfull.aio.service import BaseService
from fastapi_restfull.aio.repository import BaseRepository
from fastapi_restfull.aio.controller import BaseController
```

These classes are designed to work asynchronously with Beanie models and FastAPI dependency injection.

## License

MIT
