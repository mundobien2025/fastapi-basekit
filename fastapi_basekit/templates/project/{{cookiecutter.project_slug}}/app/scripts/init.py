"""Master seed orchestrator."""

import asyncio

from app.scripts.init_admin import init_admin


async def run_all() -> None:
    await init_admin()


if __name__ == "__main__":
    asyncio.run(run_all())
