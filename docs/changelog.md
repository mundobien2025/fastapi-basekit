# Changelog

Ver el archivo raw en el repo: [CHANGELOG.md](https://github.com/mundobien2025/fastapi-basekit/blob/main/CHANGELOG.md)

## 0.2.x — current

- ✨ `basekit init` CLI con cookiecutter (multi-ORM, multi-DB, redis, s3, license)
- 📚 Docs site MkDocs Material en GitHub Pages
- 🐛 `BasePaginationResponse[Schema]` (no `[List[Schema]]`) — fix double-nesting
- 📝 Skill `fastapi-basekit-crud` v2 (auto `self.action`, BaseService policy, alembic render_item)

## 0.2.1

- Plugin Claude Code estable
- Skill expanded — sections 22-28 (real-world fixes)

## 0.2.0

- Multi-ORM: SQLAlchemy + SQLModel + Beanie
- Async-only stack
- `BasePermission` async base class

## 0.1.x

- Initial release
- `BaseRepository`, `BaseService`, `BaseController` para SQLAlchemy
