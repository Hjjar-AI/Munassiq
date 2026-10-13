from getpass import getpass
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from accounts.models import Policy, RoleGrant, User
from accounts.services import audit, validate_password

TERMS_AR = 'مُنسِّق دليل مهني وخدمة تسجيل للفعاليات. لا تُدخل بيانات مرضى أو سجلات سريرية. قد يخضع المحتوى للمراجعة. التحقق من المنظّم ليس توصية مهنية.'
TERMS_EN = 'Munassiq is a professional directory and event-registration service. Do not submit patient information or clinical records. Content may be moderated. Organizer verification is not a professional endorsement.'
PRIVACY_AR = 'نخزن معلومات الحساب والدليل المهني والتسجيلات والتفضيلات. يطّلع المنظمون المخوّلون على أسماء المسجلين وبريدهم. وثائق الاعتماد خاصة وتُحذف بعد القرار ولا تدخل النسخ الاحتياطية. يمكن تصدير البيانات أو حذف الحساب. قد تبقى البيانات المحذوفة في النسخ الاحتياطية حتى انتهاء مدتها.'
PRIVACY_EN = 'We store account details, professional directory information, registrations and preferences. Authorized organizers can access registrant names and emails. Credential files are private, excluded from backups and deleted after review. Users can export data or delete their account. Deleted data may remain in retained backups until expiry.'


class Command(BaseCommand):
    help = 'Interactively create the first verified admin and placeholder policies; no default password.'

    def handle(self, *args, **options):
        if RoleGrant.objects.filter(role='admin').exists():
            raise CommandError('An administrator already exists. Bootstrap refused.')
        email = input('Admin email: ').strip().lower()
        name = input('Admin name: ').strip()
        password = getpass('Password (hidden): ')
        if password != getpass('Repeat password: '):
            raise CommandError('Passwords differ.')
        try:
            validate_email(email)
            validate_password(password)
            if not name:
                raise CommandError('Name is required.')
            with transaction.atomic():
                if RoleGrant.objects.filter(role='admin').exists():
                    raise CommandError('An administrator already exists.')
                user = User.objects.create_user(email, password, name=name, verified_at=timezone.now())
                RoleGrant.objects.create(user=user, role='admin')
                if not Policy.objects.exists():
                    Policy.objects.create(terms_ar=TERMS_AR, terms_en=TERMS_EN, privacy_ar=PRIVACY_AR, privacy_en=PRIVACY_EN)
                audit(user, 'admin.bootstrap', user)
        except (ValidationError, DjangoValidationError, IntegrityError) as exc:
            raise CommandError('Invalid account details or existing email.') from exc
        self.stdout.write(self.style.SUCCESS('First admin created. Organizer role is not granted.'))
