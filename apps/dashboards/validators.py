"""Validation des paramètres de requête des dashboards."""

from datetime import timedelta

from rest_framework import serializers

from apps.events.constants import EventFormat, EventStatus
from apps.registrations.constants import RegistrationStatus


MAX_STATISTICS_RANGE_DAYS = 366


class DateRangeQuerySerializer(serializers.Serializer):
    """Valide une période personnalisée."""

    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if bool(start_date) != bool(end_date):
            raise serializers.ValidationError(
                "start_date et end_date doivent être fournis ensemble."
            )

        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError(
                    {"end_date": "end_date doit être postérieure ou égale à start_date."}
                )

            if end_date - start_date > timedelta(
                days=MAX_STATISTICS_RANGE_DAYS
            ):
                raise serializers.ValidationError(
                    "La période personnalisée ne peut pas dépasser 366 jours."
                )

        return attrs


class OrganizerStatisticsQuerySerializer(DateRangeQuerySerializer):
    """Paramètres autorisés pour les statistiques organisateur."""

    event_id = serializers.UUIDField(required=False)
    event_status = serializers.ChoiceField(
        choices=EventStatus.choices,
        required=False,
    )
    event_format = serializers.ChoiceField(
        choices=EventFormat.choices,
        required=False,
    )
    registration_status = serializers.ChoiceField(
        choices=RegistrationStatus.choices,
        required=False,
    )


class AdminStatisticsQuerySerializer(DateRangeQuerySerializer):
    """Périodes prédéfinies ou personnalisées pour les statistiques admin."""

    period = serializers.ChoiceField(
        choices=(
            "today",
            "last_7_days",
            "last_30_days",
            "last_12_months",
            "custom",
        ),
        required=False,
        default="last_30_days",
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        period = attrs.get("period", "last_30_days")
        has_custom_dates = bool(attrs.get("start_date") or attrs.get("end_date"))

        if period == "custom" and not (
            attrs.get("start_date") and attrs.get("end_date")
        ):
            raise serializers.ValidationError(
                "La période custom exige start_date et end_date."
            )

        if period != "custom" and has_custom_dates:
            raise serializers.ValidationError(
                "Pour des dates personnalisées, utilisez period=custom."
            )

        return attrs