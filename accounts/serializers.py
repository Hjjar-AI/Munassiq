from rest_framework import serializers
from .models import RoleGrant


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=1, max_length=256, write_only=True, trim_whitespace=False)
    name = serializers.CharField(max_length=150)
    language = serializers.ChoiceField(choices=['ar', 'en'], default='ar')
    policy_id = serializers.IntegerField(min_value=1)
    consent = serializers.BooleanField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=256, write_only=True, trim_whitespace=False)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200, write_only=True)


class ResetSerializer(TokenSerializer):
    password = serializers.CharField(max_length=256, write_only=True, trim_whitespace=False)


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(max_length=200, write_only=True)


class ProfileSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    language = serializers.ChoiceField(choices=['ar', 'en'], required=False)


class PasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=256, write_only=True, trim_whitespace=False)
    password = serializers.CharField(max_length=256, write_only=True, trim_whitespace=False)


class ChangeEmailSerializer(LoginSerializer):
    pass


class DeleteSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=256, write_only=True, trim_whitespace=False)


class RoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=RoleGrant.ROLES)
    enabled = serializers.BooleanField()


class BanSerializer(serializers.Serializer):
    banned = serializers.BooleanField()
    reason = serializers.CharField(max_length=500, required=False, default='')

    def validate(self, data):
        if data['banned'] and not data['reason']:
            raise serializers.ValidationError({'reason': 'A ban reason is required.'})
        return data


class PolicySerializer(serializers.Serializer):
    terms_ar = serializers.CharField(max_length=20000)
    terms_en = serializers.CharField(max_length=20000)
    privacy_ar = serializers.CharField(max_length=20000)
    privacy_en = serializers.CharField(max_length=20000)


class MessageSerializer(serializers.Serializer):
    detail = serializers.CharField()


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField()
    language = serializers.CharField()
    email_verified = serializers.BooleanField()
    roles = serializers.ListField(child=serializers.CharField())


class SessionSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    token_type = serializers.CharField()
    expires_in = serializers.IntegerField()
    user = UserSerializer()


class OrganizerApplySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    workplace = serializers.CharField(max_length=200)
    reason = serializers.CharField(max_length=1000)
    credential = serializers.FileField(write_only=True)


class OrganizerDecisionSerializer(serializers.Serializer):
    approved = serializers.BooleanField()
    reason = serializers.CharField(max_length=1000, required=False, default='')


class OrganizerResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    workplace = serializers.CharField()
    reason = serializers.CharField()
    status = serializers.CharField()
    locked = serializers.BooleanField()
    reviewer_name = serializers.CharField(allow_null=True)
    decision_reason = serializers.CharField()
    created_at = serializers.DateTimeField()
