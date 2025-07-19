# FastAPI Toolkit

This package provides reusable asynchronous utilities for building FastAPI applications with the Beanie ODM. It includes base classes for repositories, services and controllers as well as common exception handlers, response schemas and helper services such as JWT token management and file uploads to Supabase.

## Installation

```bash
pip install fastapi-toolkit
```

## Usage

Import the base classes and extend them in your project:

```python
from fastapi_toolkit.asynchronous.service import BaseService
from fastapi_toolkit.asynchronous.repository import BaseRepository
from fastapi_toolkit.asynchronous.controller import BaseController
```

These classes are designed to work asynchronously with Beanie models and FastAPI dependency injection.

## License

MIT
