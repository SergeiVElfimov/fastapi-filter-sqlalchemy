import typing
from collections import defaultdict
from enum import Enum
from warnings import warn

from pydantic import ValidationInfo, field_validator
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Query
from sqlalchemy.sql.selectable import Select

from .base import BaseFilterModel


def _backward_compatible_value_for_like_and_ilike(value: str):
    """Add % if not in value to be backward compatible.

    Args:
        value (str): The value to filter.

    Returns:
        Either the unmodified value if a percent sign is present, the value wrapped in % otherwise to preserve
        current behavior.
    """
    if "%" not in value:
        warn(
            "You must pass the % character explicitly to use the contains and icontains operators.",
            DeprecationWarning,
            stacklevel=2,
        )
        value = f"%{value}%"
    return value


_orm_operator_transformer = {
    "neq": lambda value: ("__ne__", value),
    "gt": lambda value: ("__gt__", value),
    "gte": lambda value: ("__ge__", value),
    "in": lambda value: ("in_", value),
    "isnull": lambda value: ("is_", None) if value is True else ("is_not", None),
    "lt": lambda value: ("__lt__", value),
    "lte": lambda value: ("__le__", value),
    "contains": lambda value: ("like", _backward_compatible_value_for_like_and_ilike(value)),
    "icontains": lambda value: ("ilike", _backward_compatible_value_for_like_and_ilike(value)),
    "range": lambda value: ("between", value),
    # XXX(arthurio): Mysql excludes None values when using `in` or `not in` filters.
    "not": lambda value: ("is_not", value),
    "not_in": lambda value: ("not_in", value),
}
"""Operators à la Django.

Examples:
    my_datetime__gte
    count__lt
    name__isnull
    user_id__in
"""


class Filter(BaseFilterModel):
    """Base filter for orm related filters.

    All children must set:
        ```python
        class Constants(Filter.Constants):
            model = MyModel
        ```

    It can handle regular field names and Django style operators.

    Example:
        ```python
        class MyModel:
            id: PrimaryKey()
            name: StringField(nullable=True)
            count: IntegerField()
            created_at: DatetimeField()

        class MyModelFilter(Filter):
            id: Optional[int]
            id__in: Optional[str]
            count: Optional[int]
            count__lte: Optional[int]
            created_at__gt: Optional[datetime]
            name__isnull: Optional[bool]
    """

    class Constants:
        model: type
        ordering_field_name: str = "order_by"
        search_model_fields: list[str]
        search_field_name: str = "search"
        prefix: str
        original_filter: type["Filter"]
        ordering_fk_fields_mapping: dict = {}

    class Direction(str, Enum):
        asc = "asc"
        desc = "desc"

    @field_validator("*", mode="before")
    def split_str(cls, value, field: ValidationInfo):
        if (
            field.field_name is not None
            and (
                field.field_name == cls.Constants.ordering_field_name
                or field.field_name.endswith("__in")
                or field.field_name.endswith("__not_in")
                or field.field_name.endswith("__likein")
                or field.field_name.endswith("__range")
            )
            and isinstance(value, str)
        ):
            if not value:
                # Empty string should return [] not ['']
                return []
            return list(value.split(","))
        return value

    def filter(self, query: Query | Select) -> Query | Select:
        """Filter method.

        :param query: Original query.
        :return: Query filtered by field.
        """
        for field_name, value in self.filtering_fields:
            query = self._filter_field(query, field_name, value)
        return query

    def _filter_field(self, query: Query | Select, field_name: str, value: typing.Any) -> Query | Select:
        field_value = getattr(self, field_name)

        to_date = False
        if isinstance(field_value, Filter):
            query = field_value.filter(query)
        else:
            if "__date" in field_name:
                field_name = field_name.replace("__date", "")
                to_date = True
            if "__" in field_name:
                field_name, operator = field_name.split("__")
                if operator != "likein":
                    operator, value = _orm_operator_transformer[operator](value)
            else:
                operator = "__eq__"

            if field_name == self.Constants.search_field_name and hasattr(self.Constants, "search_model_fields"):
                search_filters = [
                    getattr(self.Constants.model, field).ilike(f"%{value}%")
                    for field in self.Constants.search_model_fields
                ]
                query = query.filter(or_(*search_filters))
            else:
                query = self._custom_filter_field(
                    query=query, operator=operator, field_name=field_name, value=value, to_date=to_date
                )

        return query

    def _custom_filter_field(
        self, query: Query | Select, operator: str, field_name: str, value: typing.Any, to_date: bool = False
    ) -> Query | Select:
        """Create custom filters method.

        :param operator: Name of the filter operator.
        :param field_name: Name of the filter field.
        :return: Returns the query.
        """
        # Делаем провреку, что такого поля нету в модели
        # Если нету то вызываем метод get_field_name
        # Передаем в него запрос и значение.
        if hasattr(self.Constants.model, field_name):
            model_field = getattr(self.Constants.model, field_name)
            if to_date:
                model_field = func.date(model_field)
            if operator != "likein" and operator != "between":
                query = query.filter(getattr(model_field, operator)(value))
            elif operator == "between":
                query = query.filter(getattr(model_field, operator)(*value))
            else:
                value = [_backward_compatible_value_for_like_and_ilike(str(item)) for item in value]
                if isinstance(model_field.type, String):
                    query = query.filter(or_(*[model_field.ilike(item) for item in value]))
                else:
                    query = query.filter(or_(*[cast(model_field, String).ilike(item) for item in value]))
        else:
            query = getattr(self, f"get_{field_name}")(query, value)
        return query

    def sort(self, query: Query | Select):
        """Sorting method.

        :param query: The original query.
        :return: The query with sorting.
        """
        if not self.ordering_values:
            return query
        for field_name in self.ordering_values:
            if "__" in field_name:
                field_name, base_field_name = field_name.split("__")
            direction = Filter.Direction.asc
            if field_name.startswith("-"):
                direction = Filter.Direction.desc

            field_name = field_name.replace("-", "").replace("+", "")

            order_by_field = getattr(self.Constants.model, field_name)
            if field_name in self.Constants.ordering_fk_fields_mapping:
                model = self.Constants.ordering_fk_fields_mapping[field_name]

                order_by_field = getattr(model, base_field_name)
            query = query.order_by(getattr(order_by_field, direction)())

        return query

    @field_validator("*", mode="before", check_fields=False)
    def validate_order_by(cls, value, field: ValidationInfo):
        """Check fields for sorting method.

        :param value: Value.
        :param field: Field name.
        :return: Validation value.
        """
        if field.field_name != cls.Constants.ordering_field_name:
            return value

        if not value:
            return None

        field_name_usages = defaultdict(list)

        for field_name_with_direction in value:
            field_name = field_name_with_direction.replace("-", "").replace("+", "")
            if "__" in field_name:
                field_name, base_field_name = field_name.split("__")
                if (not base_field_name) or (
                    not (
                        field_name in cls.Constants.ordering_fk_fields_mapping
                        and hasattr(cls.Constants.ordering_fk_fields_mapping[field_name], base_field_name)
                    )
                ):
                    raise ValueError(f"{field_name}__{base_field_name} is not a valid ordering field.")

            if not (
                hasattr(cls.Constants.model, field_name) or (field_name in cls.Constants.ordering_fk_fields_mapping)
            ):
                raise ValueError(f"{field_name} is not a valid ordering field.")

            field_name_usages[field_name].append(field_name_with_direction)

        duplicated_field_names = [field_name for field_name, usages in field_name_usages.items() if len(usages) > 1]

        if duplicated_field_names:
            ambiguous_field_names = ", ".join(
                [
                    field_name_with_direction
                    for field_name in sorted(duplicated_field_names)
                    for field_name_with_direction in field_name_usages[field_name]
                ]
            )
            raise ValueError(
                f"Field names can appear at most once for {cls.Constants.ordering_field_name}. "
                f"The following was ambiguous: {ambiguous_field_names}."
            )

        return value
