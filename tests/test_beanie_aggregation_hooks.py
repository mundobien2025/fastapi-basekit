"""Tests for the 0.3.2 Beanie aggregation hooks.

Covers:
- BaseRepository.build_list_queryset (default + override)
- BaseRepository.build_list_pipeline (default + override)
- BaseRepository.paginate_pipeline ($facet wrapper + validate flag)
- BaseService.use_aggregation flag routes list() to pipeline path
- BaseService.aggregation_validate flag passes through
- BaseService.build_list_queryset / build_list_pipeline service-level hooks
- list_with_aggregation backward-compat wrapper
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from beanie import Document
from pydantic import Field

from fastapi_basekit.aio.beanie.repository.base import BaseRepository
from fastapi_basekit.aio.beanie.service.base import BaseService


class FakeModel(Document):
    """Stand-in Beanie Document. Never inserted — only used for aggregate mocks."""

    name: str = Field(default="x")

    class Settings:
        name = "fake"


class FakeRepo(BaseRepository):
    model = FakeModel


# ---------- build_list_queryset ----------------------------------------------


class TestBuildListQueryset:
    def test_default_delegates_to_build_filter_query(self):
        repo = FakeRepo()
        with patch.object(repo, "build_filter_query") as mock_bfq:
            mock_bfq.return_value = "FAKE_FINDMANY"
            result = repo.build_list_queryset(
                search="foo",
                search_fields=["name"],
                filters={"is_active": True},
                order_by=[("created_at", -1)],
            )

        assert result == "FAKE_FINDMANY"
        mock_bfq.assert_called_once_with(
            search="foo",
            search_fields=["name"],
            filters={"is_active": True},
            order_by=[("created_at", -1)],
        )

    def test_default_passes_kwargs_through(self):
        repo = FakeRepo()
        with patch.object(repo, "build_filter_query") as mock_bfq:
            repo.build_list_queryset(fetch_links=True)
        assert mock_bfq.call_args.kwargs.get("fetch_links") is True

    def test_default_normalizes_none_search_fields_and_filters(self):
        repo = FakeRepo()
        with patch.object(repo, "build_filter_query") as mock_bfq:
            repo.build_list_queryset()
        kw = mock_bfq.call_args.kwargs
        assert kw["search_fields"] == []
        assert kw["filters"] == {}


# ---------- build_list_pipeline ----------------------------------------------


class TestBuildListPipeline:
    def test_no_filters_no_order_returns_empty_pipeline(self):
        repo = FakeRepo()
        pipeline = repo.build_list_pipeline()
        assert pipeline == []

    def test_filters_only_emits_match_stage(self):
        repo = FakeRepo()
        pipeline = repo.build_list_pipeline(
            filters={"is_active": True, "name": "Juan"}
        )
        assert len(pipeline) == 1
        assert "$match" in pipeline[0]
        assert pipeline[0]["$match"] == {"is_active": True, "name": "Juan"}

    def test_search_alone_emits_match_with_or(self):
        repo = FakeRepo()
        pipeline = repo.build_list_pipeline(
            search="ana", search_fields=["name", "email"]
        )
        assert len(pipeline) == 1
        match = pipeline[0]["$match"]
        assert "$or" in match
        assert {"name": {"$regex": ".*ana.*", "$options": "i"}} in match["$or"]
        assert {"email": {"$regex": ".*ana.*", "$options": "i"}} in match["$or"]

    def test_filters_plus_search_combined_with_and(self):
        repo = FakeRepo()
        pipeline = repo.build_list_pipeline(
            search="ana",
            search_fields=["name"],
            filters={"is_active": True},
        )
        match = pipeline[0]["$match"]
        assert "$and" in match
        assert {"is_active": True} in match["$and"]
        assert {"$or": [{"name": {"$regex": ".*ana.*", "$options": "i"}}]} in match["$and"]

    def test_simple_order_by_appends_sort_stage(self):
        repo = FakeRepo()
        pipeline = repo.build_list_pipeline(order_by="-created_at")
        assert pipeline[-1] == {"$sort": {"created_at": -1}}

    def test_ascending_order_by_no_dash(self):
        repo = FakeRepo()
        pipeline = repo.build_list_pipeline(order_by="name")
        assert pipeline[-1] == {"$sort": {"name": 1}}

    def test_match_plus_sort_in_correct_order(self):
        repo = FakeRepo()
        pipeline = repo.build_list_pipeline(
            filters={"is_active": True}, order_by="-created_at"
        )
        assert "$match" in pipeline[0]
        assert "$sort" in pipeline[1]

    def test_nested_order_without_link_falls_back_to_dot_path(self):
        repo = FakeRepo()
        # FakeModel has no Link fields → no $lookup, but field path normalized
        pipeline = repo.build_list_pipeline(order_by="profile__age")
        assert pipeline[-1] == {"$sort": {"profile.age": 1}}


# ---------- paginate_pipeline ------------------------------------------------


class TestPaginatePipeline:
    @pytest.mark.asyncio
    async def test_appends_facet_stage(self):
        repo = FakeRepo()
        # Mock model.aggregate
        agg_chain = MagicMock()
        agg_chain.to_list = AsyncMock(
            return_value=[{"metadata": [{"total": 5}], "data": []}]
        )
        with patch.object(FakeModel, "aggregate", return_value=agg_chain) as mock_agg:
            await repo.paginate_pipeline(
                [{"$match": {"x": 1}}], page=2, count=10
            )

        called_with = mock_agg.call_args[0][0]
        assert called_with[0] == {"$match": {"x": 1}}
        assert "$facet" in called_with[-1]
        facet = called_with[-1]["$facet"]
        assert facet["metadata"] == [{"$count": "total"}]
        assert facet["data"] == [{"$skip": 10}, {"$limit": 10}]

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list_zero_total(self):
        repo = FakeRepo()
        agg_chain = MagicMock()
        agg_chain.to_list = AsyncMock(return_value=[])
        with patch.object(FakeModel, "aggregate", return_value=agg_chain):
            items, total = await repo.paginate_pipeline([], page=1, count=10)
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_validate_true_calls_model_validate(self):
        repo = FakeRepo()
        raw_data = [{"name": "Juan"}, {"name": "Ana"}]
        agg_chain = MagicMock()
        agg_chain.to_list = AsyncMock(
            return_value=[{"metadata": [{"total": 2}], "data": raw_data}]
        )
        # Patch model_validate (Beanie Document.model_validate requires init_beanie;
        # bypass by stubbing it for this unit test)
        with patch.object(FakeModel, "aggregate", return_value=agg_chain), patch.object(
            FakeModel,
            "model_validate",
            side_effect=lambda d: type("Row", (), {"name": d["name"]})(),
        ) as mock_validate:
            items, total = await repo.paginate_pipeline(
                [], page=1, count=10, validate=True
            )

        assert total == 2
        assert mock_validate.call_count == 2
        assert [it.name for it in items] == ["Juan", "Ana"]

    @pytest.mark.asyncio
    async def test_validate_false_returns_raw_dicts(self):
        repo = FakeRepo()
        raw_data = [
            {"name": "Juan", "extra_joined_field": "X"},
            {"name": "Ana", "extra_joined_field": "Y"},
        ]
        agg_chain = MagicMock()
        agg_chain.to_list = AsyncMock(
            return_value=[{"metadata": [{"total": 2}], "data": raw_data}]
        )
        with patch.object(FakeModel, "aggregate", return_value=agg_chain):
            items, total = await repo.paginate_pipeline(
                [], page=1, count=10, validate=False
            )

        assert total == 2
        assert items == raw_data
        assert all(isinstance(item, dict) for item in items)

    @pytest.mark.asyncio
    async def test_validate_true_skips_unvalidatable_rows(self):
        """Rows that fail model_validate are silently dropped, not raised."""
        repo = FakeRepo()
        raw_data = [
            {"name": "Juan"},
            {"name": 123},  # invalid
            {"name": "Ana"},
        ]
        agg_chain = MagicMock()
        agg_chain.to_list = AsyncMock(
            return_value=[{"metadata": [{"total": 3}], "data": raw_data}]
        )

        def stub_validate(d):
            if not isinstance(d.get("name"), str):
                raise ValueError("not a string")
            return type("Row", (), {"name": d["name"]})()

        with patch.object(FakeModel, "aggregate", return_value=agg_chain), patch.object(
            FakeModel, "model_validate", side_effect=stub_validate
        ):
            items, total = await repo.paginate_pipeline(
                [], page=1, count=10, validate=True
            )

        # total reflects pipeline count; validation drops one row from items
        assert total == 3
        assert len(items) == 2
        assert [it.name for it in items] == ["Juan", "Ana"]

    @pytest.mark.asyncio
    async def test_pagination_skip_calculation_for_arbitrary_page(self):
        repo = FakeRepo()
        agg_chain = MagicMock()
        agg_chain.to_list = AsyncMock(
            return_value=[{"metadata": [{"total": 0}], "data": []}]
        )
        with patch.object(FakeModel, "aggregate", return_value=agg_chain) as mock_agg:
            await repo.paginate_pipeline([], page=5, count=20)

        facet = mock_agg.call_args[0][0][-1]["$facet"]
        # page 5, count 20 → skip 80
        assert facet["data"][0] == {"$skip": 80}
        assert facet["data"][1] == {"$limit": 20}


# ---------- list_with_aggregation backward-compat ----------------------------


class TestListWithAggregationBackwardCompat:
    @pytest.mark.asyncio
    async def test_delegates_to_build_list_pipeline_then_paginate(self):
        repo = FakeRepo()
        with patch.object(
            repo, "build_list_pipeline", return_value=[{"$match": {"x": 1}}]
        ) as mock_pipeline, patch.object(
            repo, "paginate_pipeline", new=AsyncMock(return_value=([], 0))
        ) as mock_pag:
            await repo.list_with_aggregation(
                search="foo",
                search_fields=["name"],
                filters={"x": 1},
                order_by="-created_at",
                page=1,
                count=10,
            )

        mock_pipeline.assert_called_once()
        mock_pag.assert_called_once()
        # validate=True is the back-compat default
        assert mock_pag.call_args.kwargs.get("validate") is True


# ---------- BaseService.use_aggregation routing ------------------------------


class _FakeRequest:
    """Minimal stand-in for fastapi.Request — only `.scope` is touched."""

    scope: dict = {}


class PipelineRoutedService(BaseService):
    use_aggregation = True


class FindManyRoutedService(BaseService):
    use_aggregation = False


class TestServiceListRouting:
    @pytest.mark.asyncio
    async def test_use_aggregation_true_routes_to_pipeline(self):
        repo = FakeRepo()
        svc = PipelineRoutedService(repo, request=None)

        with patch.object(
            svc, "build_list_pipeline", return_value=[{"$match": {}}]
        ) as mock_build, patch.object(
            repo, "paginate_pipeline", new=AsyncMock(return_value=([], 0))
        ) as mock_pag:
            await svc.list(page=1, count=10)

        mock_build.assert_called_once()
        mock_pag.assert_called_once()

    @pytest.mark.asyncio
    async def test_use_aggregation_false_routes_to_findmany(self):
        repo = FakeRepo()
        svc = FindManyRoutedService(repo, request=None)

        with patch.object(
            svc, "build_list_queryset", return_value="FAKE_QUERY"
        ) as mock_build, patch.object(
            repo, "paginate", new=AsyncMock(return_value=([], 0))
        ) as mock_pag:
            await svc.list(page=1, count=10)

        mock_build.assert_called_once()
        mock_pag.assert_called_once()

    @pytest.mark.asyncio
    async def test_nested_order_by_forces_pipeline_even_without_flag(self):
        repo = FakeRepo()
        svc = FindManyRoutedService(repo, request=None)

        with patch.object(
            svc, "build_list_pipeline", return_value=[]
        ) as mock_build, patch.object(
            repo, "paginate_pipeline", new=AsyncMock(return_value=([], 0))
        ):
            await svc.list(order_by="user__email", page=1, count=10)

        mock_build.assert_called_once()

    @pytest.mark.asyncio
    async def test_aggregation_validate_flag_propagates_to_repo(self):
        repo = FakeRepo()

        class FlatService(BaseService):
            use_aggregation = True
            aggregation_validate = False

        svc = FlatService(repo, request=None)

        with patch.object(svc, "build_list_pipeline", return_value=[]), patch.object(
            repo, "paginate_pipeline", new=AsyncMock(return_value=([], 0))
        ) as mock_pag:
            await svc.list(page=1, count=10)

        assert mock_pag.call_args.kwargs.get("validate") is False


# ---------- Service-level hooks default delegation --------------------------


class TestServiceHookDelegation:
    def test_build_list_queryset_delegates_to_repo(self):
        repo = FakeRepo()
        svc = BaseService(repo, request=None)
        with patch.object(repo, "build_list_queryset", return_value="X") as mock_repo:
            result = svc.build_list_queryset(
                search="foo", filters={"is_active": True}
            )
        assert result == "X"
        mock_repo.assert_called_once()

    def test_build_list_pipeline_delegates_to_repo(self):
        repo = FakeRepo()
        svc = BaseService(repo, request=None)
        with patch.object(repo, "build_list_pipeline", return_value=[]) as mock_repo:
            result = svc.build_list_pipeline(order_by="-created_at")
        assert result == []
        mock_repo.assert_called_once()

    def test_service_search_fields_used_when_caller_passes_none(self):
        repo = FakeRepo()

        class SearchSvc(BaseService):
            search_fields = ["name", "email"]

        svc = SearchSvc(repo, request=None)
        with patch.object(repo, "build_list_pipeline") as mock_repo:
            svc.build_list_pipeline(search="foo", search_fields=None)

        assert mock_repo.call_args.kwargs["search_fields"] == ["name", "email"]


# ---------- Override pattern (subquery cross-collection) --------------------


class TestOverridePattern:
    """Validates the documented override pattern: service composes $lookup
    on top of repo's default pipeline."""

    @pytest.mark.asyncio
    async def test_service_override_appends_lookup_stages(self):
        repo = FakeRepo()

        class JoinSvc(BaseService):
            use_aggregation = True
            aggregation_validate = False

            def build_list_pipeline(
                self,
                search=None,
                search_fields=None,
                filters=None,
                order_by=None,
                **kwargs,
            ):
                pipeline = self.repository.build_list_pipeline(
                    search=search,
                    search_fields=search_fields or self.search_fields,
                    filters=filters,
                    order_by=order_by or "-created_at",
                )
                pipeline.extend([
                    {
                        "$lookup": {
                            "from": "wallets",
                            "localField": "_id",
                            "foreignField": "user.$id",
                            "as": "wallet_data",
                        }
                    },
                    {
                        "$unwind": {
                            "path": "$wallet_data",
                            "preserveNullAndEmptyArrays": True,
                        }
                    },
                    {
                        "$project": {
                            "id": {"$toString": "$_id"},
                            "wallet_balance": {
                                "$convert": {
                                    "input": "$wallet_data.balance",
                                    "to": "string",
                                    "onNull": None,
                                }
                            },
                        }
                    },
                ])
                return pipeline

        svc = JoinSvc(repo, request=None)
        captured = {}

        async def capture_pipeline(pipeline, **kw):
            captured["pipeline"] = pipeline
            captured["validate"] = kw.get("validate")
            return [], 0

        with patch.object(repo, "paginate_pipeline", new=capture_pipeline):
            await svc.list(page=1, count=10)

        pipeline = captured["pipeline"]
        # $sort from default + $lookup + $unwind + $project added by override
        stage_keys = [list(s.keys())[0] for s in pipeline]
        assert "$sort" in stage_keys
        assert "$lookup" in stage_keys
        assert "$unwind" in stage_keys
        assert "$project" in stage_keys
        # validate=False because aggregation_validate=False
        assert captured["validate"] is False
