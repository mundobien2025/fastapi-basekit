"""End-to-end integration test for Beanie aggregation hooks.

Uses mongomock-motor to run the pipelines our hooks generate against a
MongoDB-compatible engine. Goal: prove that the pipeline shapes emitted by
`build_list_pipeline` are valid Mongo pipelines that produce the expected
results — beyond the unit-level shape assertions in
`test_beanie_aggregation_hooks.py`.

Caveat: Beanie 2.x's `aggregate()` wrapper has a known compatibility issue
with mongomock-motor's cursor (`AsyncIOMotorLatentCommandCursor` is not
awaitable). We bypass that by executing pipelines through the raw pymongo
collection (`Doc.get_pymongo_collection().aggregate(...)`). This still
validates the *pipeline shape* end-to-end, which is what fastapi-basekit
is responsible for.
"""

from typing import Optional

import mongomock_motor
import pytest
from beanie import Document, init_beanie
from pydantic import Field

from fastapi_basekit.aio.beanie.repository.base import BaseRepository


class UserDoc(Document):
    name: str = Field(...)
    age: int = Field(...)
    is_active: bool = True

    class Settings:
        name = "users_pipeline_int"


class UserRepo(BaseRepository):
    model = UserDoc


@pytest.fixture
async def mongo_client():
    client = mongomock_motor.AsyncMongoMockClient()
    yield client
    client.close()


@pytest.fixture
async def db(mongo_client):
    await init_beanie(
        database=mongo_client.test_db, document_models=[UserDoc]
    )
    yield
    try:
        coll = UserDoc.get_pymongo_collection()
        await coll.drop()
    except Exception:
        pass


async def _seed():
    await UserDoc(name="Alice", age=30, is_active=True).insert()
    await UserDoc(name="Bob", age=25, is_active=True).insert()
    await UserDoc(name="Carol", age=40, is_active=False).insert()
    await UserDoc(name="Dave", age=35, is_active=True).insert()


async def _run_pipeline(pipeline):
    """Bypass Beanie's aggregate wrapper — execute via raw collection."""
    coll = UserDoc.get_pymongo_collection()
    return await coll.aggregate(pipeline).to_list(None)


class TestPipelineShapeIntegration:
    @pytest.mark.asyncio
    async def test_match_stage_filters_correctly(self, db):
        await _seed()
        repo = UserRepo()
        pipeline = repo.build_list_pipeline(filters={"is_active": True})
        rows = await _run_pipeline(pipeline)
        assert len(rows) == 3
        assert all(r["is_active"] for r in rows)

    @pytest.mark.asyncio
    async def test_search_regex_finds_substring(self, db):
        await _seed()
        repo = UserRepo()
        pipeline = repo.build_list_pipeline(
            search="li", search_fields=["name"]
        )
        rows = await _run_pipeline(pipeline)
        # "Alice" matches /.*li.*/i
        names = [r["name"] for r in rows]
        assert "Alice" in names

    @pytest.mark.asyncio
    async def test_search_plus_filter_combined_with_and(self, db):
        await _seed()
        repo = UserRepo()
        pipeline = repo.build_list_pipeline(
            search="a",
            search_fields=["name"],
            filters={"is_active": True},
        )
        rows = await _run_pipeline(pipeline)
        # active rows whose name contains "a" (case-insensitive): Alice, Dave
        names = sorted(r["name"] for r in rows)
        assert names == ["Alice", "Dave"]

    @pytest.mark.asyncio
    async def test_simple_sort_descending(self, db):
        await _seed()
        repo = UserRepo()
        pipeline = repo.build_list_pipeline(order_by="-age")
        rows = await _run_pipeline(pipeline)
        ages = [r["age"] for r in rows]
        assert ages == sorted(ages, reverse=True)

    @pytest.mark.asyncio
    async def test_simple_sort_ascending(self, db):
        await _seed()
        repo = UserRepo()
        pipeline = repo.build_list_pipeline(order_by="age")
        rows = await _run_pipeline(pipeline)
        ages = [r["age"] for r in rows]
        assert ages == sorted(ages)

    @pytest.mark.asyncio
    async def test_facet_pagination_via_raw_pipeline(self, db):
        """Reproduces what `paginate_pipeline` does: append a `$facet` and
        run the resulting pipeline. Validates the shape works end-to-end
        even though Beanie's aggregate wrapper is incompatible with
        mongomock-motor — the pipeline shape itself is correct.
        """
        await _seed()
        repo = UserRepo()
        pipeline = repo.build_list_pipeline(
            filters={"is_active": True}, order_by="-age"
        )
        pipeline.append(
            {
                "$facet": {
                    "metadata": [{"$count": "total"}],
                    "data": [{"$skip": 0}, {"$limit": 2}],
                }
            }
        )
        results = await _run_pipeline(pipeline)
        assert len(results) == 1
        bucket = results[0]
        assert bucket["metadata"][0]["total"] == 3
        assert len(bucket["data"]) == 2
        # First two rows by age desc among active: Dave(35), Alice(30)
        assert [r["name"] for r in bucket["data"]] == ["Dave", "Alice"]

    @pytest.mark.asyncio
    async def test_empty_pipeline_returns_all_rows(self, db):
        await _seed()
        repo = UserRepo()
        pipeline = repo.build_list_pipeline()  # empty
        rows = await _run_pipeline(pipeline)
        assert len(rows) == 4

    @pytest.mark.asyncio
    async def test_override_with_lookup_stage(self, db):
        """Service-level override stacking $lookup is the documented
        pattern. Validates the pipeline produced runs against Mongo.
        """
        await _seed()
        repo = UserRepo()

        # Build a base pipeline + a $lookup against an empty collection
        # (mongomock doesn't enforce schema — the $lookup will return [])
        pipeline = repo.build_list_pipeline(filters={"is_active": True})
        pipeline.extend(
            [
                {
                    "$lookup": {
                        "from": "wallets",
                        "localField": "_id",
                        "foreignField": "user.$id",
                        "as": "wallet_data",
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "id": {"$toString": "$_id"},
                        "name": 1,
                        "wallet_count": {"$size": "$wallet_data"},
                    }
                },
            ]
        )
        rows = await _run_pipeline(pipeline)
        assert len(rows) == 3
        for r in rows:
            assert "id" in r
            assert isinstance(r["id"], str)
            assert r["wallet_count"] == 0  # collection empty
