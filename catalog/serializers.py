from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import Category, City, Country, Currency


class ZonedDateTimeField(serializers.DateTimeField):
    def to_internal_value(self, data):
        # Do not silently interpret an unspecified local clock as UTC.
        from django.utils.dateparse import parse_datetime
        try:
            parsed = parse_datetime(str(data))
        except (ValueError, TypeError):
            raise serializers.ValidationError('Use a valid date and time with a UTC offset.')
        if parsed is None or parsed.tzinfo is None:
            raise serializers.ValidationError('Include a UTC offset, e.g. +03:00 or Z.')
        return super().to_internal_value(data)


class CountrySerializer(serializers.ModelSerializer):
    code = serializers.RegexField(r'^[A-Z]{2}$', validators=[UniqueValidator(queryset=Country.objects.all())])
    class Meta:
        model = Country
        fields = ['id', 'code', 'name_ar', 'name_en', 'active']
        read_only_fields = ['id']


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'country', 'name_ar', 'name_en', 'active', 'geonames_id', 'region_ar', 'region_en',
            'district_ar', 'district_en', 'latitude', 'longitude', 'time_zone']
        read_only_fields = ['id', 'geonames_id']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name_ar', 'name_en', 'active']
        read_only_fields = ['id']


class CurrencySerializer(serializers.ModelSerializer):
    code = serializers.RegexField(r'^[A-Z]{3}$', validators=[UniqueValidator(queryset=Currency.objects.all())])
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name_ar', 'name_en', 'active']
        read_only_fields = ['id']


class ContentSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=10000)
    country_id = serializers.IntegerField(min_value=1)
    city_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)
    category_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=10)
    time_zone = serializers.CharField(max_length=80)
    latitude = serializers.FloatField(min_value=-90, max_value=90, allow_null=True, default=None)
    longitude = serializers.FloatField(min_value=-180, max_value=180, allow_null=True, default=None)
    contact_person = serializers.CharField(max_length=150, allow_blank=True, default='')
    contact_scope = serializers.ChoiceField(choices=['personal', 'organization'], default='personal')
    image_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=5, default=list)
    phone = serializers.CharField(max_length=50, allow_blank=True, default='')

    def validate(self, data):
        if data['phone']:
            import phonenumbers
            try:
                number = phonenumbers.parse(data['phone'], None)
                if not phonenumbers.is_valid_number(number):
                    raise ValueError('Invalid number')
                data['phone'] = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
            except (phonenumbers.NumberParseException, ValueError):
                raise serializers.ValidationError({'phone': 'Use a valid international phone number.'})
        if not Country.objects.filter(pk=data['country_id'], active=True).exists():
            raise serializers.ValidationError({'country_id': 'Choose an enabled country.'})
        if data['city_id'] and not City.objects.filter(pk=data['city_id'], country_id=data['country_id'], active=True).exists():
            raise serializers.ValidationError({'city_id': 'Choose a city in this country.'})
        ids = set(data['category_ids'])
        if len(ids) != len(data['category_ids']) or Category.objects.filter(pk__in=ids, active=True).count() != len(ids):
            raise serializers.ValidationError({'category_ids': 'Choose enabled categories without duplicates.'})
        try:
            ZoneInfo(data['time_zone'])
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError({'time_zone': 'Use an IANA time-zone name.'})
        import math
        if any(value is not None and not math.isfinite(value) for value in (data['latitude'], data['longitude'])):
            raise serializers.ValidationError('Map coordinates must be finite numbers.')
        if (data['latitude'] is None) != (data['longitude'] is None):
            raise serializers.ValidationError('Supply both map coordinates.')
        return data


class HoursSerializer(serializers.Serializer):
    day = serializers.IntegerField(min_value=0, max_value=6, help_text='Monday=0, Sunday=6')
    start = serializers.TimeField(format='%H:%M')
    end = serializers.TimeField(format='%H:%M')

    def validate(self, data):
        for value in (data['start'], data['end']):
            if value.second or value.microsecond or value.tzinfo:
                raise serializers.ValidationError('Use local HH:MM times.')
        if data['start'] == data['end']:
            raise serializers.ValidationError('A range must have a nonzero duration.')
        return data


class ServiceSerializer(ContentSerializer):
    name = serializers.CharField(max_length=200)
    type = serializers.ChoiceField(choices=['clinic', 'center', 'contact_office', 'service_at_place'])
    address = serializers.CharField(max_length=500)
    hours = HoursSerializer(many=True, max_length=28, default=list)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, allow_null=True, default=None)
    currency_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)

    def validate(self, data):
        data = super().validate(data)
        if data['latitude'] is None or data['city_id'] is None:
            raise serializers.ValidationError('A service requires a city and map position.')
        if (data['price'] is None) != (data['currency_id'] is None):
            raise serializers.ValidationError('Supply both price and currency, or neither.')
        if data['currency_id'] and not Currency.objects.filter(pk=data['currency_id'], active=True).exists():
            raise serializers.ValidationError({'currency_id': 'Choose an enabled currency.'})
        ranges = []
        for row in data['hours']:
            start = row['day'] * 1440 + row['start'].hour * 60 + row['start'].minute
            end = row['day'] * 1440 + row['end'].hour * 60 + row['end'].minute
            if end <= start:
                end += 1440
            ranges.extend([(start, end), (start+10080, end+10080)])
        ranges.sort()
        if any(right[0] < left[1] for left, right in zip(ranges, ranges[1:])):
            raise serializers.ValidationError({'hours': 'Working-hour ranges overlap.'})
        return data


class EventSerializer(ContentSerializer):
    title = serializers.CharField(max_length=200)
    image_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=3, default=list)
    pdf_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)
    speaker_name = serializers.CharField(max_length=150)
    topic = serializers.CharField(max_length=200)
    mode = serializers.ChoiceField(choices=['in_person', 'online', 'both'])
    online_url = serializers.URLField(allow_blank=True, default='')
    registration_contact = serializers.CharField(max_length=200, allow_blank=True, default='')
    registration_url = serializers.URLField(allow_blank=True, default='')
    address = serializers.CharField(max_length=500, allow_blank=True, default='')
    service_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)
    starts_at = ZonedDateTimeField()
    duration_minutes = serializers.IntegerField(min_value=1, max_value=525600)
    seat_limit = serializers.IntegerField(min_value=1, max_value=100000)
    registration_deadline = ZonedDateTimeField(allow_null=True, default=None)
    cancellation_cutoff_minutes = serializers.IntegerField(min_value=0, max_value=525600, default=0)
    recurrence = serializers.ChoiceField(choices=['none', 'weekly', 'monthly'], default='none')
    occurrence_count = serializers.IntegerField(min_value=1, max_value=52, default=1)

    def validate(self, data):
        data = super().validate(data)
        if data['mode'] in {'online', 'both'} and not data['online_url']:
            raise serializers.ValidationError({'online_url': 'An online event needs a link.'})
        if data['mode'] in {'in_person', 'both'} and not data['service_id'] and (data['latitude'] is None or not data['address'] or data['city_id'] is None):
            raise serializers.ValidationError('Choose a service venue or supply city, address and map position.')
        if data['registration_deadline'] and data['registration_deadline'] > data['starts_at']:
            raise serializers.ValidationError({'registration_deadline': 'Deadline cannot follow event start.'})
        if data['recurrence'] == 'none' and data['occurrence_count'] != 1:
            raise serializers.ValidationError('A non-recurring event has one occurrence.')
        return data


class DecisionSerializer(serializers.Serializer):
    approved = serializers.BooleanField()
    reason = serializers.CharField(max_length=1000, allow_blank=True, default='')


class ReportSerializer(serializers.Serializer):
    item_id = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=['spam', 'wrong_info', 'other'])
    text = serializers.CharField(max_length=2000, allow_blank=True, default='')

    def validate(self, data):
        if data['reason'] == 'other' and not data['text']:
            raise serializers.ValidationError({'text': 'Describe the report.'})
        return data


class ReportResolutionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['dismiss', 'hide', 'warn'])
    reason = serializers.CharField(max_length=1000, allow_blank=True, default='')


class FeedbackSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=3000)


class RescheduleSerializer(serializers.Serializer):
    starts_at = ZonedDateTimeField()
    duration_minutes = serializers.IntegerField(min_value=1, max_value=525600)
    time_zone = serializers.CharField(max_length=80)


class RemoveRegistrationSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class DuplicateSerializer(serializers.Serializer):
    starts_at = ZonedDateTimeField()
    title = serializers.CharField(max_length=200, required=False)


class RegistrationResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    occurrence_id = serializers.IntegerField()
    state = serializers.CharField()
    reconfirm_deadline = serializers.DateTimeField(allow_null=True)
    overlap_warning = serializers.BooleanField(required=False)


class OccurrenceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    event_local_start = serializers.CharField()
    event_local_end = serializers.CharField()
    user_local_start = serializers.CharField()
    time_zone = serializers.CharField()
    cancelled = serializers.BooleanField()
    archived = serializers.BooleanField()
    seat_limit = serializers.IntegerField()
    registration_deadline = serializers.DateTimeField(allow_null=True)
    cancellation_cutoff_minutes = serializers.IntegerField()


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class AssetSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    size = serializers.IntegerField()


class StatsSerializer(serializers.Serializer):
    views = serializers.IntegerField()
    registered = serializers.IntegerField()
    pending_reconfirm = serializers.IntegerField()
    waitlisted = serializers.IntegerField()


class RegistrantSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    state = serializers.CharField()


class ReportResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    item_id = serializers.IntegerField(allow_null=True)
    reason = serializers.CharField()
    text = serializers.CharField()
    resolution = serializers.CharField()


class FeedbackResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    text = serializers.CharField()
    created_at = serializers.DateTimeField()


class ItemResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    status = serializers.CharField()
    owner_id = serializers.IntegerField(allow_null=True)
    payload = serializers.DictField()
    occurrences = OccurrenceSerializer(many=True, required=False)
    date_range = serializers.DictField(allow_null=True, required=False)
    open_now = serializers.BooleanField(required=False)
    locked = serializers.BooleanField(required=False)
    reviewer_name = serializers.CharField(allow_null=True, required=False)
    duplicate_flag = serializers.BooleanField(required=False)
    rejection_reason = serializers.CharField(required=False)
    proposed_revision_id = serializers.IntegerField(allow_null=True, required=False)


class QuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    country = serializers.IntegerField(min_value=1, required=False)
    city = serializers.IntegerField(min_value=1, required=False)
    category = serializers.IntegerField(min_value=1, required=False)
    currency = serializers.IntegerField(min_value=1, required=False)
    sort = serializers.ChoiceField(choices=['name', 'price', 'date'], default='name')
    open_now = serializers.BooleanField(default=False)
    archive = serializers.BooleanField(default=False)
    archived_only = serializers.BooleanField(default=False)
    time_zone = serializers.CharField(max_length=80, default='UTC')
    page = serializers.IntegerField(min_value=1, default=1)


class ItemPageSerializer(serializers.Serializer):
    results = ItemResultSerializer(many=True)
    next_page = serializers.IntegerField(allow_null=True)


class DuplicateCheckSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)


class DuplicateResultSerializer(serializers.Serializer):
    similar_name_exists = serializers.BooleanField()


class ViewResultSerializer(serializers.Serializer):
    counted = serializers.BooleanField()


class ReminderSerializer(serializers.Serializer):
    offset_minutes = serializers.IntegerField(min_value=0, max_value=525600)


class OrganizerProfileInputSerializer(serializers.Serializer):
    bio = serializers.CharField(max_length=2000, allow_blank=True, default='')
    photo_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)


class OrganizerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    bio = serializers.CharField()
    photo_id = serializers.IntegerField(allow_null=True)
    verified = serializers.BooleanField()


class OccurrenceDetailSerializer(OccurrenceSerializer):
    payload = serializers.DictField()
