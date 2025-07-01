# FastAPI filter SQLAlchemy

[![build-status-image]][build-status]
[![pypi-version]][pypi]

This is a fork [fastapi-filter](https://github.com/arthurio/fastapi-filter)

- added functionality for creating custom filters (analog SerializerMethodField into [drf](https://github.com/encode/django-rest-framework)).
- possibility to sort by fields of related tables.
- new filter `range` implementing behavior `between`.
- new filter `likein` combines behavior `in` and `ilike`.

## Required
- python >=3.11, <4.0
- fastapi >=0.100.0, <1.0
- SQLAlchemy >=1.4.36, <2.1.0
- pydantic >=2.0.0, <3.0.0

## Installation
```pip install fastapi-filter-sqlalchemy```

## Contributing

Before contributing please read our [contributing guidelines](CONTRIBUTING.md).

[build-status-image]: https://github.com/SergeiVElfimov/fastapi-filter-sqlalchemy/actions/workflows/python-package.yml/badge.svg
[build-status]: https://github.com/SergeiVElfimov/fastapi-filter-sqlalchemy/actions/workflows/python-package.yml
[pypi-version]: https://img.shields.io/pypi/v/fastapi-filter-sqlalchemy.svg
[pypi]: https://pypi.org/project/fastapi-filter-sqlalchemy/
