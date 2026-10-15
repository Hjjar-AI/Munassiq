"""Arabic/English dashboard vocabulary, independent of API field names."""
LABELS = {
    'email':('البريد الإلكتروني','Email'), 'password':('كلمة المرور','Password'),
    'current_password':('كلمة المرور الحالية','Current password'), 'name':('الاسم','Name'),
    'title':('العنوان','Title'), 'description':('الوصف','Description'), 'language':('اللغة','Language'),
    'country_id':('الدولة','Country'), 'city_id':('المدينة / البلدة','City / town'),
    'category_ids':('التخصصات والمواضيع','Specialties and topics'), 'time_zone':('المنطقة الزمنية','Time zone'),
    'latitude':('خط العرض','Latitude'), 'longitude':('خط الطول','Longitude'),
    'contact_person':('جهة الاتصال','Contact person'), 'contact_scope':('نوع جهة الاتصال','Contact scope'),
    'phone':('الهاتف مع رمز الدولة','Phone including country code'), 'type':('نوع نقطة الخدمة','Service type'),
    'address':('العنوان المكاني','Address'), 'price':('السعر التقريبي','Approximate price'),
    'currency_id':('العملة','Currency'), 'speaker_name':('اسم المحاضر','Speaker'), 'topic':('الموضوع','Topic'),
    'mode':('طريقة الحضور','Attendance'), 'online_url':('رابط الحضور عبر الإنترنت','Online meeting link'),
    'registration_contact':('جهة اتصال التسجيل','Registration contact'), 'registration_url':('رابط التسجيل الخارجي','External registration link'),
    'service_id':('نقطة الخدمة المستضيفة','Service venue'), 'starts_at':('موعد البداية بالتوقيت المحلي المختار','Start in selected local time'),
    'duration_minutes':('المدة بالدقائق','Duration in minutes'), 'seat_limit':('عدد المقاعد','Seat limit'),
    'registration_deadline':('آخر موعد للتسجيل بالتوقيت المختار','Registration deadline in selected zone'),
    'cancellation_cutoff_minutes':('إغلاق الإلغاء قبل البداية بالدقائق','Cancellation cutoff minutes before start'),
    'recurrence':('التكرار','Recurrence'), 'occurrence_count':('عدد المواعيد','Number of occurrences'),
    'reason':('السبب','Reason'), 'text':('الرسالة','Message'), 'workplace':('مكان العمل','Workplace'),
    'credential':('إثبات مهني خاص، حتى 5 ميغابايت','Private credential, up to 5 MB'),
    'approved':('الموافقة','Approve'), 'role':('الدور','Role'), 'enabled':('تفعيل','Enabled'),
    'banned':('حظر الحساب','Ban account'), 'consent':('أوافق على الشروط وسياسة الخصوصية','I accept Terms and Privacy'),
    'active':('متاح للاختيار','Available for selection'), 'name_ar':('الاسم بالعربية','Arabic name'),
    'name_en':('الاسم بالإنجليزية','English name'), 'code':('الرمز الدولي','International code'),
    'bio':('نبذة مهنية','Professional bio'), 'offset_minutes':('التذكير قبل البداية بالدقائق','Reminder minutes before start'),
    'reminders':('تذكيرات الفعاليات','Event reminders'), 'announcements':('الإعلانات','Announcements'),
    'followed_events':('فعاليات المتابعات','Followed events'), 'follow_delivery':('تواتر المتابعات','Follow delivery'),
    'quiet_start':('بداية ساعات الهدوء','Quiet hours start'), 'quiet_end':('نهاية ساعات الهدوء','Quiet hours end'),
    'audience':('الجمهور','Audience'), 'expires_at':('انتهاء الإعلان بالتوقيت العالمي UTC','Expiry in UTC'),
    'support_email':('بريد الدعم','Support email'), 'apk_download_url':('رابط تنزيل التطبيق','APK download URL'),
    'guide_ar':('دليل المنظّم بالعربية','Arabic organizer guide'), 'guide_en':('دليل المنظّم بالإنجليزية','English organizer guide'),
    'title_ar':('العنوان بالعربية','Arabic title'), 'title_en':('العنوان بالإنجليزية','English title'),
    'body_ar':('الرسالة بالعربية','Arabic message'), 'body_en':('الرسالة بالإنجليزية','English message'),
    'terms_ar':('الشروط بالعربية','Arabic terms'), 'terms_en':('الشروط بالإنجليزية','English terms'),
    'privacy_ar':('الخصوصية بالعربية','Arabic privacy'), 'privacy_en':('الخصوصية بالإنجليزية','English privacy'),
    'action':('الإجراء','Action'), 'image_files':('صور جديدة','New photos'), 'pdf_file':('ملف PDF اختياري','Optional PDF'),
    'photo_file':('الصورة الشخصية','Profile photo'),
}
CHOICES = {
    'ar':('العربية','Arabic'), 'en':('الإنجليزية','English'), 'personal':('شخصية','Personal'),
    'organization':('مؤسسية','Organizational'), 'clinic':('عيادة','Clinic'), 'center':('مركز','Center'),
    'contact_office':('جهة اتصال / مكتب','Contact / office'), 'service_at_place':('خدمة في مكان','Service at a place'),
    'online':('عبر الإنترنت','Online'), 'in_person':('حضوري','In person'), 'both':('حضوري وعبر الإنترنت','Both'),
    'none':('دون تكرار','None'), 'weekly':('أسبوعي','Weekly'), 'monthly':('شهري','Monthly'),
    'instant':('فوري','Instant'), 'daily':('ملخص يومي','Daily digest'), 'everyone':('الجميع','Everyone'),
    'organizers':('المنظّمون','Organizers'), 'location':('حسب المكان','By location'),
    'organizer':('منظّم','Organizer'), 'moderator':('مشرف','Moderator'), 'admin':('مدير','Admin'),
    'dismiss':('تجاهل البلاغ','Dismiss report'), 'hide':('إخفاء المحتوى','Hide item'), 'warn':('تنبيه المنظّم','Warn organizer'),
    'spam':('محتوى مزعج','Spam'), 'wrong_info':('معلومات خاطئة أو مزيفة','Wrong/fake information'), 'other':('غير ذلك','Other'),
    'pending':('بانتظار المراجعة','Pending review'), 'approved':('منشور','Published'), 'rejected':('مرفوض','Rejected'),
    'pending_changes':('تعديلات بانتظار المراجعة','Changes pending'), 'hidden':('مخفي','Hidden'),
    'soft_deleted':('محذوف مؤقتاً','Temporarily deleted'), 'registered':('مسجّل','Registered'),
    'waitlisted':('قائمة الانتظار','Waitlisted'), 'pending_reconfirm':('بانتظار إعادة التأكيد','Reconfirmation needed'),
    'cancelled':('ملغى','Cancelled'),
}


def word(language, arabic, english):
    return arabic if language == 'ar' else english


def label(name, language):
    return word(language, *LABELS.get(name, CHOICES.get(name, (name, name))))
