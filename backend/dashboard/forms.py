"""Human-readable HTML forms derived from the existing API's validation fields."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django import forms
from django.utils import timezone
from django.conf import settings
from rest_framework import serializers as api
from .labels import label, word


class MultipleInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFiles(forms.FileField):
    def clean(self, data, initial=None):
        return [super(MultipleFiles, self).clean(value, initial) for value in (data if isinstance(data, list) else [data]) if value]


class DashboardForm(forms.Form):
    def __init__(self, serializer, language, data=None, files=None, initial=None, references=None):
        self.api_serializer, self.language = serializer, language
        self.references = references or {}
        super().__init__(data=data, files=files, initial=initial)
        for name, field in serializer().fields.items():
            if field.read_only or name in ('id', 'created_at', 'policy_id', 'item_id', 'token'):
                continue
            options = {'label': label(name, language), 'required': field.required and not field.allow_null}
            default = field.default
            if default is not api.empty:
                options['initial'] = default() if callable(default) else default
            if name in ('image_ids','pdf_id','photo_id'):
                if name == 'image_ids':
                    self.fields[name] = forms.CharField(required=False,widget=forms.HiddenInput())
                else:
                    self.fields[name] = forms.IntegerField(required=False,widget=forms.HiddenInput())
                continue
            if name == 'hours':
                continue
            if name in self.references:
                choices = self.references[name]
                if name == 'category_ids':
                    html = forms.TypedMultipleChoiceField(choices=choices,coerce=int,**options)
                else:
                    html = forms.TypedChoiceField(choices=[('',word(language,'اختر','Choose'))]+choices,coerce=int,empty_value=None,**options)
            elif isinstance(field,api.ChoiceField):
                html = forms.ChoiceField(choices=[(value,label(value,language)) for value in field.choices],**options)
            elif isinstance(field,api.BooleanField):
                html = forms.BooleanField(**{**options,'required':False})
            elif isinstance(field,api.IntegerField):
                html = forms.IntegerField(min_value=field.min_value,max_value=field.max_value,**options)
            elif isinstance(field,(api.FloatField,api.DecimalField)):
                html = forms.DecimalField(**options)
            elif isinstance(field,api.DateTimeField):
                html = forms.CharField(widget=forms.DateTimeInput(attrs={'type':'datetime-local','step':'any'}),**options)
            elif isinstance(field,api.TimeField):
                html = forms.TimeField(widget=forms.TimeInput(attrs={'type':'time'}),**options)
            elif isinstance(field,api.FileField):
                html = forms.FileField(**options)
            elif isinstance(field,api.EmailField):
                html = forms.EmailField(**options)
            else:
                attrs = {}
                widget = forms.TextInput
                if 'password' in name:
                    widget=forms.PasswordInput
                    attrs['autocomplete']='current-password' if name=='current_password' else 'new-password'
                elif getattr(field,'max_length',0) and field.max_length > 500 or name in ('bio','description','text','reason'):
                    widget=forms.Textarea
                    attrs['rows']=5
                if 'password' in name:
                    attrs['autocomplete']='current-password' if name=='current_password' or serializer.__name__ in ('LoginSerializer','ChangeEmailSerializer','DeleteSerializer') else 'new-password'
                html = forms.CharField(max_length=getattr(field,'max_length',None),widget=widget(attrs=attrs),strip='password' not in name,**options)
            self.fields[name] = html
        if 'image_ids' in self.fields:
            self.fields['image_files'] = MultipleFiles(label=label('image_files',language),required=False,widget=MultipleInput(attrs={'accept':'image/jpeg,image/png,image/webp'}))
        if 'pdf_id' in self.fields:
            self.fields['pdf_file'] = forms.FileField(label=label('pdf_file',language),required=False,widget=forms.FileInput(attrs={'accept':'application/pdf'}))
        if 'photo_id' in self.fields:
            self.fields['photo_file'] = forms.FileField(label=label('photo_file',language),required=False)
        if 'password' in self.fields and serializer.__name__ not in ('LoginSerializer','ChangeEmailSerializer','DeleteSerializer'):
            self.fields['password'].help_text=word(language,f'على الأقل {settings.PASSWORD_MIN_LENGTH} أحرف',f'At least {settings.PASSWORD_MIN_LENGTH} characters')
        if initial:
            zone = ZoneInfo(initial.get('time_zone') or 'UTC')
            for name, field in serializer().fields.items():
                value = initial.get(name)
                if value and isinstance(field,api.DateTimeField):
                    parsed = datetime.fromisoformat(str(value).replace('Z','+00:00'))
                    self.initial[name] = parsed.astimezone(zone).replace(tzinfo=None).isoformat()
            self.initial['image_ids'] = ','.join(map(str,initial.get('image_ids',[])))

    def api_data(self):
        data = {key:value for key,value in self.cleaned_data.items() if key not in ('image_files','pdf_file','photo_file')}
        zone = data.get('time_zone') or 'UTC'
        try:
            local_zone=ZoneInfo(zone)
        except (ValueError,ZoneInfoNotFoundError):
            raise forms.ValidationError(word(self.language,'منطقة زمنية غير صالحة','Invalid time zone'))
        for key,field in self.api_serializer().fields.items():
            if key not in data:
                continue
            value=data[key]
            if isinstance(field,api.DateTimeField):
                if not value:
                    if field.allow_null: data[key]=None
                    else: data.pop(key)
                    continue
                try:
                    parsed=datetime.fromisoformat(value)
                    if parsed.tzinfo is None:
                        aware=parsed.replace(tzinfo=local_zone)
                        if aware.astimezone(ZoneInfo('UTC')).astimezone(local_zone).replace(tzinfo=None)!=parsed or aware.utcoffset()!=parsed.replace(tzinfo=local_zone,fold=1).utcoffset():
                            raise ValueError('Ambiguous clock time')
                        parsed=aware
                    data[key]=parsed.isoformat()
                except ValueError:
                    raise forms.ValidationError(word(self.language,'موعد غير صالح أو ملتبس بسبب التوقيت الصيفي','Invalid or ambiguous local date/time'))
            elif isinstance(field,api.TimeField):
                data[key]=value.isoformat() if value else None
            elif isinstance(field,api.ListField) and key=='image_ids':
                try: data[key]=[int(value) for value in value.split(',') if value]
                except ValueError: raise forms.ValidationError('Invalid photos')
            elif value is None and not field.allow_null:
                data.pop(key)
        return data
