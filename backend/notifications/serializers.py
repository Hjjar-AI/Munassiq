from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from rest_framework import serializers
from catalog.models import City, Country
from .models import Announcement, AppSettings, Device, Preferences


class PreferencesSerializer(serializers.ModelSerializer):
    country_id = serializers.PrimaryKeyRelatedField(source='country', queryset=Country.objects.filter(active=True), allow_null=True, required=False)
    city_id = serializers.PrimaryKeyRelatedField(source='city', queryset=City.objects.filter(active=True, country__active=True), allow_null=True, required=False)
    language = serializers.ChoiceField(choices=['ar', 'en'], required=False)

    class Meta:
        model = Preferences
        fields = ['language', 'time_zone', 'country_id', 'city_id', 'reminders',
            'announcements', 'followed_events', 'follow_delivery', 'quiet_start', 'quiet_end']

    def validate_time_zone(self, value):
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise serializers.ValidationError('Use a valid IANA time zone.')
        return value

    def validate(self, attrs):
        def current(name):
            return attrs.get(name, getattr(self.instance, name, None))
        start, end = current('quiet_start'), current('quiet_end')
        if (start is None) != (end is None) or (start is not None and start == end):
            raise serializers.ValidationError('Set both quiet-hour times to different values, or clear both.')
        if start is not None and (start.tzinfo is not None or end.tzinfo is not None):
            raise serializers.ValidationError('Quiet hours use local clock times without an offset.')
        country, city = current('country'), current('city')
        if city and (not country or city.country_id != country.pk):
            raise serializers.ValidationError('The city must belong to the selected country.')
        return attrs


class DeviceInputSerializer(serializers.Serializer):
    installation_id = serializers.UUIDField()
    token = serializers.CharField(max_length=4096, min_length=20, trim_whitespace=False, write_only=True)

    def validate_token(self, value):
        if any(character.isspace() or ord(character) < 32 for character in value):
            raise serializers.ValidationError('Invalid device token.')
        return value


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['id', 'installation_id', 'created_at', 'updated_at']


class FollowPageSerializer(serializers.Serializer):
    organizer_ids = serializers.ListField(child=serializers.IntegerField())
    category_ids = serializers.ListField(child=serializers.IntegerField())


class StatisticsSerializer(serializers.Serializer):
    users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    banned_users = serializers.IntegerField()
    events = serializers.IntegerField()
    services = serializers.IntegerField()
    unresolved_reports = serializers.IntegerField()


class EmptySerializer(serializers.Serializer):
    pass


class AnnouncementSerializer(serializers.ModelSerializer):
    country_id = serializers.PrimaryKeyRelatedField(source='country', queryset=Country.objects.filter(active=True), allow_null=True, required=False)
    city_id = serializers.PrimaryKeyRelatedField(source='city', queryset=City.objects.filter(active=True, country__active=True), allow_null=True, required=False)

    class Meta:
        model = Announcement
        fields = ['id', 'title_ar', 'title_en', 'body_ar', 'body_en', 'audience',
            'country_id', 'city_id', 'created_at', 'expires_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {'expires_at': {'required': False}}

    def validate(self, attrs):
        from datetime import timedelta
        from django.utils import timezone
        country, city = attrs.get('country'), attrs.get('city')
        if attrs.get('audience', 'everyone') == 'location':
            if not country or (city and city.country_id != country.pk):
                raise serializers.ValidationError('Select a country and a city belonging to it, if specified.')
        elif country or city:
            raise serializers.ValidationError('Location filters require the location audience.')
        expires = attrs.setdefault('expires_at', timezone.now()+timedelta(days=7))
        if expires <= timezone.now() or expires > timezone.now()+timedelta(days=30):
            raise serializers.ValidationError('Expiry must be in the next 30 days.')
        return attrs


class AppSettingsSerializer(serializers.ModelSerializer):
    guide_ar = serializers.CharField(max_length=10000, allow_blank=True, required=False)
    guide_en = serializers.CharField(max_length=10000, allow_blank=True, required=False)
    class Meta:
        model = AppSettings
        fields = ['support_email', 'apk_download_url', 'apk_version_code', 'guide_ar', 'guide_en']

    def validate_apk_download_url(self, value):
        if value and not value.startswith('https://'):
            raise serializers.ValidationError('Use an HTTPS download URL.')
        return value
