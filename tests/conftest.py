from collections.abc import AsyncIterator
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, Query
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, declarative_base, relationship

from fastapi_filter_sqlalchemy import Filter as SQLAlchemyFilter
from fastapi_filter_sqlalchemy import FilterDepends, with_prefix


@pytest_asyncio.fixture(scope="function")
async def test_client(app):
    async with AsyncClient(base_url="http://test", transport=ASGITransport(app=app)) as async_test_client:
        yield async_test_client


@pytest.fixture(scope="package")
def UserFilterOrderByWithDefault(User, UserFilter):  # type: ignore[valid-type]
    class UserFilterOrderByWithDefault(UserFilter):  # type: ignore
        order_by: list[str] = ["age"]

    return UserFilterOrderByWithDefault


@pytest.fixture(scope="package")
def UserFilterOrderBy(User, UserFilter):  # type: ignore[valid-type]
    class UserFilterOrderBy(UserFilter):  # type: ignore
        order_by: list[str] | None = None

    return UserFilterOrderBy


@pytest.fixture(scope="package")
def UserFilterNoOrderBy(User, UserFilter):  # type: ignore[valid-type]
    return UserFilter


@pytest.fixture(scope="package")
def UserFilterCustomOrderBy(UserFilter):  # type: ignore[valid-type]
    class UserFilterCustomOrderBy(UserFilter):  # type: ignore
        class Constants(UserFilter.Constants):  # type: ignore[name-defined]
            ordering_field_name = "custom_order_by"

        custom_order_by: list[str] | None = None

    return UserFilterCustomOrderBy


@pytest.fixture(scope="package")
def UserFilterRestrictedOrderBy(UserFilter):  # type: ignore[valid-type]
    class UserFilterRestrictedOrderBy(UserFilter):  # type: ignore
        order_by: list[str] | None = None

        @field_validator("order_by")
        def restrict_sortable_fields(cls, value):
            if not value:
                return None

            allowed_field_names = ["age", "created_at"]
            for field_name in value:
                field_name = field_name.replace("-", "").replace("+", "")

                if field_name not in allowed_field_names:
                    raise ValueError(f"You may only sort by: {', '.join(allowed_field_names)}")

            return value

    return UserFilterRestrictedOrderBy


@pytest.fixture(scope="session")
def sqlite_file_path(tmp_path_factory):
    file_path = tmp_path_factory.mktemp("data") / "fastapi_filter_test.sqlite"
    yield file_path


@pytest.fixture(scope="session")
def database_url(sqlite_file_path) -> str:
    return f"sqlite+aiosqlite:///{sqlite_file_path}"


@pytest.fixture(scope="session")
def engine(database_url):
    return create_async_engine(database_url)


@pytest.fixture(scope="session")
def SessionLocal(engine):
    return async_sessionmaker(engine, autoflush=True, class_=AsyncSession)


@pytest_asyncio.fixture(scope="function")
async def session(engine, SessionLocal, Base):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session")
def Base():
    return declarative_base()


@pytest.fixture(scope="session")
def User(Base, Address, FavoriteSport, Sport):
    class User(Base):  # type: ignore[misc, valid-type]
        __tablename__ = "users"

        id = Column(Integer, primary_key=True, autoincrement=True)
        created_at = Column(DateTime, default=datetime.now, nullable=False)
        updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
        name = Column(String)
        age = Column(Integer, nullable=False)
        address_id = Column(Integer, ForeignKey("addresses.id"))
        address: Mapped[Address] = relationship(Address, backref="users", lazy="joined")  # type: ignore[valid-type]
        favorite_sports: Mapped[Sport] = relationship(  # type: ignore[valid-type]
            Sport,
            secondary="favorite_sports",
            backref="users",
            lazy="joined",
        )

    return User


@pytest.fixture(scope="session")
def Address(Base):
    class Address(Base):  # type: ignore[misc, valid-type]
        __tablename__ = "addresses"

        id = Column(Integer, primary_key=True, autoincrement=True)
        street = Column(String, nullable=True)
        city = Column(String, nullable=False)
        country = Column(String, nullable=False)

    return Address


@pytest.fixture(scope="session")
def Sport(Base):
    class Sport(Base):  # type: ignore[misc, valid-type]
        __tablename__ = "sports"

        id = Column(Integer, primary_key=True, autoincrement=True)
        name = Column(String, nullable=False)
        is_individual = Column(Boolean, nullable=False)

    return Sport


@pytest.fixture(scope="session")
def FavoriteSport(Base):
    class FavoriteSport(Base):  # type: ignore[misc, valid-type]
        __tablename__ = "favorite_sports"

        user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
        sport_id = Column(Integer, ForeignKey("sports.id"), primary_key=True)

    return FavoriteSport


@pytest_asyncio.fixture(scope="function")
async def users(session, User, Address):
    user_instances = [
        User(
            name=None,
            age=21,
            created_at=datetime(2021, 12, 1),
        ),
        User(
            name="Mr Praline",
            age=33,
            created_at=datetime(2021, 12, 1),
            address=Address(street="22 rue Bellier", city="Nantes", country="France"),
        ),
        User(
            name="The colonel",
            age=90,
            created_at=datetime(2021, 12, 2),
            address=Address(street="Wrench", city="Bathroom", country="Clue"),
        ),
        User(
            name="Mr Creosote",
            age=21,
            created_at=datetime(2021, 12, 3),
            address=Address(city="Nantes", country="France"),
        ),
        User(
            name="Rabbit of Caerbannog",
            age=1,
            created_at=datetime(2021, 12, 4),
            address=Address(street="1234 street", city="San Francisco", country="United States"),
        ),
        User(
            name="Gumbys",
            age=50,
            created_at=datetime(2021, 12, 4),
            address=Address(street="4567 avenue", city="Denver", country="United States"),
        ),
    ]
    session.add_all(user_instances)
    await session.commit()
    yield user_instances


@pytest_asyncio.fixture(scope="function")
async def sports(session, Sport):
    sport_instances = [
        Sport(
            name="Ice Hockey",
            is_individual=False,
        ),
        Sport(
            name="Tennis",
            is_individual=True,
        ),
    ]
    session.add_all(sport_instances)
    await session.commit()
    yield sports


@pytest_asyncio.fixture(scope="function")
async def favorite_sports(session, sports, users, FavoriteSport):
    favorite_sport_instances = [
        FavoriteSport(
            user_id=users[0].id,
            sport_id=sports[0].id,
        ),
        FavoriteSport(
            user_id=users[0].id,
            sport_id=sports[1].id,
        ),
        FavoriteSport(
            user_id=users[1].id,
            sport_id=sports[0].id,
        ),
        FavoriteSport(
            user_id=users[2].id,
            sport_id=sports[1].id,
        ),
    ]
    session.add_all(favorite_sport_instances)
    await session.commit()
    yield favorite_sport_instances


@pytest.fixture(scope="package")
def AddressOut():
    class AddressOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: int
        street: str | None
        city: str
        country: str

    return AddressOut


@pytest.fixture(scope="package")
def UserOut(AddressOut, SportOut):
    class UserOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: int
        created_at: datetime
        updated_at: datetime
        name: str | None
        age: int
        address: AddressOut | None  # type: ignore[valid-type]
        favorite_sports: list[SportOut] | None  # type: ignore[valid-type]

    return UserOut


@pytest.fixture(scope="package")
def SportOut():
    class SportOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: int
        name: str
        is_individual: bool

    return SportOut


@pytest.fixture(scope="package")
def Filter():
    yield SQLAlchemyFilter


@pytest.fixture(scope="package")
def AddressFilter(Address, Filter):
    class AddressFilter(Filter):  # type: ignore[misc, valid-type]
        street__isnull: bool | None = None
        city: str | None = None
        city__in: list[str] | None = None
        country__not_in: list[str] | None = None

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            model = Address

    yield AddressFilter


@pytest.fixture(scope="package")
def UserFilter(User, Filter, AddressFilter, Address):
    class UserFilter(Filter):  # type: ignore[misc, valid-type]
        name: str | None = None
        name__neq: str | None = None
        name__contains: str | None = None
        name__icontains: str | None = None
        name__in: list[str] | None = None
        name__not: str | None = None
        name__not_in: list[str] | None = None
        name__isnull: bool | None = None
        name__likein: list[str] | None = None
        age: int | None = None
        age__lt: int | None = None
        age__lte: int | None = None
        age__gt: int | None = None
        age__gte: int | None = None
        age__in: list[int] | None = None
        age__range: list[int] | None = None
        age__contains: str | None = None
        age__icontains: str | None = None
        address: AddressFilter | None = FilterDepends(  # type: ignore[valid-type]
            with_prefix("address", AddressFilter), by_alias=True
        )
        address_id__isnull: bool | None = None
        custom_filter: str | None = None
        search: str | None = None

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            model = User
            search_model_fields = ["name"]
            search_field_name = "search"

        def get_custom_filter(self, query, value):
            return query.filter(
                or_(
                    self.Constants.model.name == value,
                    Address.street == value,
                    Address.city == value,
                    Address.country == value,
                )
            )

    yield UserFilter


@pytest.fixture(scope="package")
def UserFilterByAlias(UserFilter, AddressFilter):
    class UserFilterByAlias(UserFilter):  # type: ignore[misc, valid-type]
        address: AddressFilter | None = FilterDepends(  # type: ignore[valid-type]
            with_prefix("address", AddressFilter), by_alias=True
        )

    yield UserFilterByAlias


@pytest.fixture(scope="package")
def SportFilter(Sport, Filter):
    class SportFilter(Filter):  # type: ignore[misc, valid-type]
        name: str | None = Field(Query(description="Name of the sport", default=None))
        is_individual: bool
        bogus_filter: str | None = None

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            model = Sport

        @field_validator("bogus_filter")
        def throw_exception(cls, value):
            if value:
                raise ValueError("You can't use this bogus filter")

    yield SportFilter


@pytest.fixture(scope="package")
def app(
    Address,
    FavoriteSport,
    SessionLocal,
    Sport,
    SportFilter,
    SportOut,
    User,
    UserFilter,
    UserFilterByAlias,
    UserFilterCustomOrderBy,
    UserFilterOrderBy,
    UserFilterOrderByWithDefault,
    UserFilterRestrictedOrderBy,
    UserOut,
):
    app = FastAPI()

    async def get_db() -> AsyncIterator[AsyncSession]:
        async with SessionLocal() as session:
            yield session

    @app.get("/users", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users(
        user_filter: UserFilter = FilterDepends(UserFilter),  # type: ignore[valid-type]
        db: AsyncSession = Depends(get_db),
    ):
        query = user_filter.filter(select(User).outerjoin(Address))  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().unique().all()

    @app.get("/users-by-alias", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_by_alias(
        user_filter: UserFilter = FilterDepends(UserFilterByAlias, by_alias=True),  # type: ignore[valid-type]
        db: AsyncSession = Depends(get_db),
    ):
        query = user_filter.filter(select(User).outerjoin(Address))  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().unique().all()

    @app.get("/users_with_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_order_by(
        user_filter: UserFilterOrderBy = FilterDepends(UserFilterOrderBy),  # type: ignore[valid-type]
        db: AsyncSession = Depends(get_db),
    ):
        query = user_filter.sort(select(User).outerjoin(Address))  # type: ignore[attr-defined]
        query = user_filter.filter(query)  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().unique().all()

    @app.get("/users_with_no_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_no_order_by(
        user_filter: UserFilter = FilterDepends(UserFilter),  # type: ignore[valid-type]
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_default_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_default_order_by(
        user_filter: UserFilterOrderByWithDefault = FilterDepends(  # type: ignore[valid-type]
            UserFilterOrderByWithDefault
        ),
        db: AsyncSession = Depends(get_db),
    ):
        return await get_users_with_order_by(user_filter, db)

    @app.get("/users_with_restricted_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_restricted_order_by(
        user_filter: UserFilterRestrictedOrderBy = FilterDepends(  # type: ignore[valid-type]
            UserFilterRestrictedOrderBy
        ),
        db: AsyncSession = Depends(get_db),
    ):
        return await get_users_with_order_by(user_filter, db)

    @app.get("/users_with_custom_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_custom_order_by(
        user_filter: UserFilterCustomOrderBy = FilterDepends(UserFilterCustomOrderBy),  # type: ignore[valid-type]
        db: AsyncSession = Depends(get_db),
    ):
        return await get_users_with_order_by(user_filter, db)

    @app.get("/sports", response_model=list[SportOut])  # type: ignore[valid-type]
    async def get_sports(
        sport_filter: SportFilter = FilterDepends(SportFilter),  # type: ignore[valid-type]
        db: AsyncSession = Depends(get_db),
    ):
        query = sport_filter.filter(select(Sport))  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().all()

    yield app
