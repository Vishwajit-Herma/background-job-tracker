from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter


class CustomOrderingFilter(OrderingFilter):
    """
    Raise 400 Bad Request if invalid ordering fields are passed.
    """

    def remove_invalid_fields(self, queryset, fields, view, request):
        valid_fields = [item[0] for item in self.get_valid_fields(queryset, view, request)]
        invalid = [term.lstrip("-") for term in fields if term.lstrip("-") not in valid_fields]
        if invalid:
            raise ValidationError({"ordering": f"Invalid ordering field(s): {', '.join(invalid)}"})
        return super().remove_invalid_fields(queryset, fields, view, request)
