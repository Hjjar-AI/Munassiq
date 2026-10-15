"""Fixed form-to-API routes. Browser input can never choose an arbitrary API URL."""
from accounts import serializers as a
from catalog import serializers as c
from notifications import serializers as n

# Arabic title, English title, serializer, API path, HTTP method, allowed role,
# optional read endpoint for prefilled forms. A target of zero means no target.
OPERATIONS = {
 'signup':('إنشاء حساب','Create account',a.SignupSerializer,'auth/signup/','POST','public',None),
 'forgot':('نسيت كلمة المرور','Forgot password',a.EmailSerializer,'auth/password/forgot/','POST','public',None),
 'verify':('إرسال رابط التحقق','Send verification link',a.EmailSerializer,'auth/verification/request/','POST','user',None),
 'profile':('بيانات الحساب','Account details',a.ProfileSerializer,'me/','PATCH','user','me/'),
 'password':('تغيير كلمة المرور','Change password',a.PasswordSerializer,'me/password/change/','POST','user',None),
 'email':('تغيير البريد','Change email',a.ChangeEmailSerializer,'me/email/change/','POST','user',None),
 'delete-account':('حذف حسابي نهائياً','Permanently delete my account',a.DeleteSerializer,'me/','DELETE','user',None),
 'feedback':('إرسال ملاحظات','Send feedback',c.FeedbackSerializer,'feedback/','POST','user',None),
 'apply':('طلب صفة منظّم','Apply as organizer',a.OrganizerApplySerializer,'organizer-requests/','POST','user',None),
 'organizer-profile':('الملف المهني','Organizer profile',c.OrganizerProfileInputSerializer,'me/organizer-profile/','PATCH','organizer',None),
 'preferences':('الإشعارات والمتابعات','Notification preferences',n.PreferencesSerializer,'me/notification-preferences/','PATCH','user','me/notification-preferences/'),
 'report':('الإبلاغ عن المحتوى','Report item',c.ReportSerializer,'reports/','POST','user',None),
 'reminder':('ضبط التذكير','Set reminder',c.ReminderSerializer,'occurrences/{id}/reminder/','PUT','user',None),
 'reschedule':('تغيير موعد الفعالية','Reschedule event',c.RescheduleSerializer,'occurrences/{id}/reschedule/','POST','user','occurrences/{id}/'),
 'duplicate':('إنشاء فعالية من قالب','Duplicate as template',c.DuplicateSerializer,'events/{id}/duplicate/','POST','organizer',None),
 'remove-registration':('إزالة تسجيل مع السبب','Remove registration with reason',c.RemoveRegistrationSerializer,'organizer/registrations/{id}/remove/','POST','user',None),
 'decision':('قرار مراجعة المحتوى','Content review decision',c.DecisionSerializer,'moderation/items/{id}/decision/','POST','reviewer',None),
 'organizer-decision':('قرار طلب المنظّم','Organizer application decision',a.OrganizerDecisionSerializer,'moderation/organizer-requests/{id}/decide/','POST','reviewer',None),
 'resolve':('معالجة البلاغ','Resolve report',c.ReportResolutionSerializer,'moderation/reports/{id}/resolve/','POST','reviewer',None),
 'category':('إضافة تخصص أو موضوع','Add category',c.CategorySerializer,'categories/','POST','reviewer',None),
 'edit-category':('تعديل تخصص أو موضوع','Edit category',c.CategorySerializer,'categories/{id}/','PATCH','reviewer','categories/{id}/'),
 'country':('إضافة دولة','Add country',c.CountrySerializer,'countries/','POST','admin',None),
 'city':('إضافة مدينة أو بلدة','Add city or town',c.CitySerializer,'cities/','POST','admin',None),
 'edit-city':('تصحيح مدينة أو بلدة','Correct city or town',c.CitySerializer,'admin/cities/{id}/','PATCH','admin','admin/cities/{id}/'),
 'currency':('إضافة عملة','Add currency',c.CurrencySerializer,'currencies/','POST','admin',None),
 'roles':('تعديل أدوار الحساب','Change account roles',a.RoleSerializer,'admin/users/{id}/roles/','POST','admin',None),
 'ban':('حظر أو إلغاء حظر الحساب','Ban or unban account',a.BanSerializer,'admin/users/{id}/ban/','POST','admin',None),
 'policies':('تحرير الشروط والخصوصية','Edit Terms and Privacy',a.PolicySerializer,'admin/policies/','POST','admin','policies/current/'),
 'announcement':('إرسال إعلان','Send announcement',n.AnnouncementSerializer,'admin/announcements/','POST','admin',None),
 'app-settings':('إعدادات التطبيق العامة','Public app settings',n.AppSettingsSerializer,'admin/app-settings/','PATCH','admin','admin/app-settings/'),
}

# These are always POST HTML confirmation forms, even for DELETE/PUT API calls.
BUTTONS = {
 'claim':('بدء المراجعة','Claim review','moderation/items/{id}/claim/','POST','reviewer'),
 'hide':('إخفاء','Hide','moderation/items/{id}/hide/','POST','reviewer'),
 'unhide':('إظهار مجدداً','Unhide','moderation/items/{id}/unhide/','POST','reviewer'),
 'delete-item':('حذف مؤقت لثلاثة أيام','Delete with three-day restore window','moderation/items/{id}/','DELETE','reviewer'),
 'restore':('استعادة المحتوى دون التسجيلات','Restore item without registrations','moderation/items/{id}/restore/','POST','reviewer'),
 'unlock':('فك قفل المراجعة','Unlock review','admin/items/{id}/unlock/','POST','admin'),
 'organizer-claim':('بدء مراجعة الطلب','Claim application','moderation/organizer-requests/{id}/claim/','POST','reviewer'),
 'organizer-unlock':('فك قفل الطلب','Unlock application','admin/organizer-requests/{id}/unlock/','POST','admin'),
 'register':('التسجيل','Register','occurrences/{id}/registration/','POST','user'),
 'series-register':('التسجيل في مواعيد السلسلة المنشورة','Register for published series occurrences','series/{id}/registrations/','POST','user'),
 'cancel-registration':('إلغاء تسجيلي','Cancel my registration','registrations/{id}/cancel/','POST','user'),
 'reconfirm':('تأكيد الحضور','Reconfirm attendance','registrations/{id}/reconfirm/','POST','user'),
 'cancel-event':('إلغاء الفعالية وإبلاغ المسجلين','Cancel event and notify registrants','occurrences/{id}/cancel/','POST','user'),
 'remove-reminder':('إزالة التذكير','Remove reminder','occurrences/{id}/reminder/','DELETE','user'),
 'follow-organizer':('متابعة المنظّم','Follow organizer','me/follows/organizers/{id}/','PUT','user'),
 'unfollow-organizer':('إلغاء متابعة المنظّم','Unfollow organizer','me/follows/organizers/{id}/','DELETE','user'),
 'follow-category':('متابعة التخصص أو الموضوع','Follow category','me/follows/categories/{id}/','PUT','user'),
 'unfollow-category':('إلغاء المتابعة','Unfollow category','me/follows/categories/{id}/','DELETE','user'),
 'delete-user':('حذف الحساب نهائياً','Permanently delete account','admin/users/{id}/','DELETE','admin'),
 'remove-device':('إزالة الجهاز','Remove device','me/devices/{id}/','DELETE','user'),
 'logout-all':('تسجيل الخروج من جميع الأجهزة','Log out all devices','auth/logout-all/','POST','user'),
}
