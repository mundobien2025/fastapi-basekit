"""Los defaults mutables del BaseService (search_fields, kwargs_query,
duplicate_check_fields) deben ser por instancia — mutar uno no puede filtrarse
a otra instancia ni al atributo de clase (contaminación cross-request)."""

from example_crud_beanie.repository import UserBeanieRepository
from example_crud_beanie.service import UserBeanieService


class TestMutableDefaultsIsolation:
    def test_subclass_override_preserved(self):
        s = UserBeanieService(repository=UserBeanieRepository())
        # El override del subclass sigue vigente (copiado, no perdido).
        assert s.search_fields == ["name", "email"]
        assert s.duplicate_check_fields == ["email"]

    def test_mutation_does_not_leak_across_instances(self):
        s1 = UserBeanieService(repository=UserBeanieRepository())
        s2 = UserBeanieService(repository=UserBeanieRepository())
        s1.search_fields.append("phone")
        assert "phone" not in s2.search_fields
        # El atributo de CLASE queda intacto.
        assert "phone" not in UserBeanieService.search_fields

    def test_kwargs_query_dict_isolated(self):
        s1 = UserBeanieService(repository=UserBeanieRepository())
        s2 = UserBeanieService(repository=UserBeanieRepository())
        s1.kwargs_query["fetch_links"] = True
        assert s2.kwargs_query == {}
        assert UserBeanieService.kwargs_query == {}
