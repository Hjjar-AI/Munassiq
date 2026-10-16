from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import urlencode
from django import forms
from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from accounts.permissions import Administrator
from accounts.models import User
from accounts.services import audit
from catalog.models import Category, City, Country, Currency, Item
from catalog.presentation import item_data
from .bridge import call, values
from .forms import DashboardForm
from .labels import label, word
from .middleware import ACCESS, REFRESH, clear_tokens, put_tokens
from .operations import BUTTONS, OPERATIONS


def t(request, arabic, english):
    return word(request.dashboard_language, arabic, english)


def allowed(request, role):
    user=request.dashboard_user
    if role=='public': return True
    if not user: return False
    if role=='user': return True
    if role=='admin':
        return Administrator().has_permission(SimpleNamespace(user=user,META=request.META),None)
    if role=='reviewer':
        return user.has_role('moderator') or allowed(request,'admin')
    return user.has_role(role)


def guard(request, role):
    if allowed(request,role): return None
    if not request.dashboard_user and role in ('user','organizer'):
        return redirect('dashboard:login')
    raise Http404


def page(request, template='dashboard/page.html', status=200, **context):
    nav=[('events','الفعاليات','Events'),('services','نقاط الخدمة','Services'),('map','الخريطة','Map'),('categories','التخصصات','Categories')]
    if allowed(request,'user'):
        nav += [('mine','محتواي','My items'),('registrations','تسجيلاتي','My registrations'),('account','حسابي','My account')]
    if allowed(request,'reviewer'):
        nav += [('reviews','مراجعة المحتوى','Content review'),('manage','إدارة المحتوى','Manage content'),('applications','طلبات المنظّمين','Organizer requests'),('reports','البلاغات','Reports'),('feedback','الملاحظات','Feedback')]
    if allowed(request,'admin'):
        nav += [('users','الحسابات','Accounts'),('statistics','الإحصاءات','Statistics'),('audit','سجل التدقيق','Audit log'),('announcements','الإعلانات','Announcements'),('locations','الأماكن','Locations')]
    context.update(user=request.dashboard_user,lang=request.dashboard_language,
        rtl=request.dashboard_language=='ar',nav=[{'slug':s,'text':t(request,a,e)} for s,a,e in nav],
        tile_url=settings.MAP_TILE_URL)
    response=render(request,template,context,status=status)
    return response


def errors(response):
    data=values(response)
    if not isinstance(data,(dict,list)): return [str(data or response.status_code)]
    if isinstance(data,list): return [str(value) for value in data]
    return [f'{key}: {value}' for key,value in data.items()]


def content_fields(request,payload):
    result=[]
    for key,value in payload.items():
        if key in ('title','name','description','image_ids','pdf_id','online_url','registration_url','service_id'):continue
        if key in ('country_id','city_id','currency_id'):
            model={'country_id':Country,'city_id':City,'currency_id':Currency}[key]
            row=model.objects.filter(pk=value).first() if value else None
            value=(row.name_ar if request.dashboard_language=='ar' else row.name_en) if row else '—'
        elif key=='category_ids':
            value=' · '.join((row.name_ar if request.dashboard_language=='ar' else row.name_en) for row in Category.objects.filter(pk__in=value))
        elif key=='hours':
            names=['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد'] if request.dashboard_language=='ar' else ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
            value='\n'.join(f'{names[row["day"]]}: {row["start"]}–{row["end"]}' for row in value)
        elif key in ('type','mode','recurrence','contact_scope'):
            value=label(value,request.dashboard_language)
        result.append((t(request,'ساعات العمل','Working hours') if key=='hours' else label(key,request.dashboard_language),value))
    return result


def api_error(request,response):
    return page(request,title=t(request,'تعذر إتمام الطلب','Request could not be completed'),errors=errors(response),status=response.status_code)


def link(request,operation,target=0,button=False):
    spec=(BUTTONS if button else OPERATIONS)[operation]
    role=spec[4] if button else spec[5]
    if not allowed(request,role): return None
    return {'text':t(request,spec[0],spec[1]),'url':reverse('dashboard:action' if button else 'dashboard:form',args=[operation,target])}


@require_http_methods(['GET','POST'])
def login(request):
    from accounts.serializers import LoginSerializer
    form=DashboardForm(LoginSerializer,request.dashboard_language,request.POST if request.method=='POST' else None)
    issues=[]
    if request.method=='POST' and form.is_valid():
        response=call(request,'/api/v1/auth/login/','POST',form.cleaned_data)
        if response.status_code==200:
            result=redirect('dashboard:home')
            put_tokens(result,values(response))
            result.dashboard_tokens_handled=True
            return result
        issues=errors(response)
    return page(request,'dashboard/form.html',title=t(request,'تسجيل الدخول','Sign in'),form=form,errors=issues,
        links=[link(request,'signup'),link(request,'forgot')],submit_label=t(request,'تسجيل الدخول','Sign in'))


@require_http_methods(['POST'])
def logout(request):
    if request.dashboard_user:
        call(request,'/api/v1/auth/logout/','POST')
    response=redirect('dashboard:login')
    clear_tokens(response)
    response.dashboard_tokens_handled=True
    return response


@require_http_methods(['POST'])
def language(request):
    response=redirect('dashboard:home')
    selected=request.POST.get('language','ar')
    response.set_cookie('munassiq_language',selected if selected in ('ar','en') else 'ar',max_age=31536000,
        secure=not settings.DEBUG,httponly=True,samesite='Lax')
    return response


def references(request,initial=None):
    initial=initial or {}
    result={}
    for key,path in [('country_id','countries/'),('category_ids','categories/'),('currency_id','currencies/')]:
        rows=values(call(request,'/api/v1/'+path)) or []
        result[key]=[(row['id'],row['name_ar'] if request.dashboard_language=='ar' else row['name_en']) for row in rows]
    country=request.POST.get('country_id') or initial.get('country_id') or request.GET.get('country')
    query=urlencode({'country':country}) if country else ''
    cities=values(call(request,'/api/v1/cities/?'+query)) or []
    selected=request.POST.get('city_id') or initial.get('city_id') or request.GET.get('city')
    if str(selected or '').isdigit() and not any(str(row['id'])==str(selected) for row in cities):
        city=City.objects.filter(pk=selected,active=True).first()
        if city: cities.append({'id':city.pk,'name_ar':city.name_ar,'name_en':city.name_en})
    result['city_id']=[(row['id'],row['name_ar'] if request.dashboard_language=='ar' else row['name_en']) for row in cities]
    # Public venue picker loads all pages; the expected first-year list is small.
    venues=[]
    number=1
    while number:
        response=call(request,f'/api/v1/services/?page={number}')
        data=values(response) or {}
        venues += [(row['id'],row['payload'].get('name','')) for row in data.get('results',[])]
        number=data.get('next_page')
    result['service_id']=venues
    result['country']=result['country_id']
    return result


def upload_fields(request,form,data):
    for field,path,destination in [('image_files','images','image_ids'),('pdf_file','event-pdfs','pdf_id'),('photo_file','images','photo_id')]:
        uploads=form.cleaned_data.get(field)
        if not uploads: continue
        for upload in uploads if isinstance(uploads,list) else [uploads]:
            response=call(request,f'/api/v1/uploads/{path}/','POST',files={'file':upload})
            if response.status_code!=201:
                raise forms.ValidationError('; '.join(errors(response)))
            asset=values(response)['id']
            if destination=='image_ids': data.setdefault(destination,[]).append(asset)
            else: data[destination]=asset


@require_http_methods(['GET','POST'])
def operation_form(request,operation,target):
    if operation not in OPERATIONS: raise Http404
    ar,en,serializer,path,method,role,read_path=OPERATIONS[operation]
    denied=guard(request,role)
    if denied:return denied
    initial={}
    if read_path:
        response=call(request,'/api/v1/'+read_path.format(id=target))
        if response.status_code!=200:return api_error(request,response)
        initial=values(response)
    if operation=='organizer-profile':
        response=call(request,f'/api/v1/organizers/{request.dashboard_user.pk}/')
        if response.status_code==200: initial=values(response)
    policy=None
    if operation=='signup':
        response=call(request,'/api/v1/policies/current/')
        if response.status_code!=200:return api_error(request,response)
        policy=values(response)
    ref=references(request,initial) if any(name in serializer().fields for name in ('country_id','country','category_ids','service_id')) else {}
    form=DashboardForm(serializer,request.dashboard_language,request.POST if request.method=='POST' else None,
        request.FILES if request.method=='POST' else None,initial,ref)
    issues=[]
    if request.method=='POST' and form.is_valid():
        try:
            data=form.api_data()
            if policy:
                if not data.get('consent'):raise forms.ValidationError(t(request,'الموافقة مطلوبة','Consent is required'))
                if request.POST.get('displayed_policy_id')!=str(policy['id']):
                    raise forms.ValidationError(t(request,'تغيرت الشروط. اقرأ النص الحالي ثم أعد الموافقة.','The policies changed. Read the current text and consent again.'))
                data['policy_id']=policy['id']
            if operation=='report': data['item_id']=target
            upload_fields(request,form,data)
            files={key:value for key,value in data.items() if hasattr(value,'read')}
            data={key:value for key,value in data.items() if key not in files}
            response=call(request,'/api/v1/'+path.format(id=target),method,data,files)
            if response.status_code<300:
                if operation=='signup':
                    result=redirect('dashboard:home')
                    put_tokens(result,values(response));result.dashboard_tokens_handled=True
                    return result
                if operation in ('delete-account','password'):
                    result=page(request,title=t(request,'تم. يرجى تسجيل الدخول مجدداً إذا كان الحساب باقياً','Done. Sign in again if the account remains.'))
                    clear_tokens(result);result.dashboard_tokens_handled=True
                    return result
                result=page(request,title=t(request,'تم الحفظ','Saved'),notice=t(request,'تم تنفيذ الطلب بنجاح.','Your request was completed.'))
                if operation in ('profile','preferences') and data.get('language'):
                    result.set_cookie('munassiq_language',data['language'],max_age=31536000,secure=not settings.DEBUG,httponly=True,samesite='Lax')
                return result
            issues=errors(response)
        except forms.ValidationError as exc: issues=exc.messages
    return page(request,'dashboard/form.html',title=t(request,ar,en),form=form,errors=issues,policy=policy)


@require_http_methods(['GET','POST'])
def action(request,operation,target):
    if operation not in BUTTONS:raise Http404
    ar,en,path,method,role=BUTTONS[operation]
    denied=guard(request,role)
    if denied:return denied
    form=forms.Form(request.POST if request.method=='POST' else None)
    form.fields['confirm']=forms.BooleanField(label=t(request,'أؤكد تنفيذ هذا الإجراء','I confirm this action'),required=True)
    if request.method=='POST' and form.is_valid():
        response=call(request,'/api/v1/'+path.format(id=target),method)
        if response.status_code>=300:return api_error(request,response)
        result=page(request,title=t(request,'تم تنفيذ الطلب','Action completed'),result=values(response))
        if operation=='logout-all':
            clear_tokens(result);result.dashboard_tokens_handled=True
        return result
    return page(request,'dashboard/form.html',title=t(request,ar,en),form=form,
        notice=t(request,'تحقق من الإجراء ورقم السجل قبل التأكيد: ','Check the action and record before confirming: ')+str(target))


@require_http_methods(['GET','POST'])
def item_form(request,kind,item_id=0,staff=False):
    from catalog.serializers import EventSerializer,ServiceSerializer
    if kind not in ('event','service'):raise Http404
    denied=guard(request,'reviewer' if staff else 'organizer')
    if denied:return denied
    initial={'time_zone':'Asia/Damascus'}
    if item_id:
        if staff:
            response=call(request,f'/api/v1/moderation/items/{item_id}/')
            if response.status_code!=200:return api_error(request,response)
            item=Item.objects.get(pk=item_id)
            if item.kind!=kind:raise Http404
            initial=(item.published_revision or item.proposed_revision).payload.copy()
        else:
            item=Item.objects.filter(pk=item_id,kind=kind,owner=request.dashboard_user).select_related('proposed_revision','published_revision').first()
            if not item:raise Http404
            initial=(item.proposed_revision or item.published_revision).payload.copy()
    serializer=EventSerializer if kind=='event' else ServiceSerializer
    form=DashboardForm(serializer,request.dashboard_language,request.POST if request.method=='POST' else None,
        request.FILES if request.method=='POST' else None,initial,references(request,initial))
    issues=[]
    duplicate_warning=False
    if request.method=='POST' and form.is_valid():
        try:
            data=form.api_data()
            if request.POST.get('attachments_present'):
                try:data['image_ids']=[int(value) for value in request.POST.getlist('keep_image_id')]
                except ValueError:raise forms.ValidationError('Invalid photos')
            if request.POST.getlist('new_image_id'):
                try:data.setdefault('image_ids',[]).extend(int(value) for value in request.POST.getlist('new_image_id'))
                except ValueError:raise forms.ValidationError('Invalid photos')
            if request.POST.get('remove_pdf'):data['pdf_id']=None
            if kind=='service':
                if not item_id:
                    duplicate=call(request,'/api/v1/services/duplicate-check/','POST',{'name':data['name']})
                    if duplicate.status_code!=200:return api_error(request,duplicate)
                    if values(duplicate)['similar_name_exists'] and not request.POST.get('confirm_duplicate'):
                        duplicate_warning=True
                        raise forms.ValidationError(t(request,'يوجد اسم مشابه. راجعه ثم أكد المتابعة إن كانت هذه نقطة مختلفة.','A similar name exists. Review it, then confirm if this is a different service.'))
                data['hours']=[]
                days=request.POST.getlist('hour_day');starts=request.POST.getlist('hour_start');ends=request.POST.getlist('hour_end')
                if not len(days)==len(starts)==len(ends):raise forms.ValidationError('Invalid hours')
                for day,start,end in zip(days,starts,ends):
                    if not start and not end:continue
                    data['hours'].append({'day':day,'start':start,'end':end})
            upload_fields(request,form,data)
            path=f'moderation/items/{item_id}/' if staff else f'{kind}s/'+(f'{item_id}/' if item_id else '')
            response=call(request,'/api/v1/'+path,'PATCH' if item_id else 'POST',data)
            if response.status_code<300:
                return page(request,title=t(request,'تم الحفظ','Saved'),notice=t(request,'يمكنك متابعة الحالة في محتواي.','Check the status under My items.'),result=values(response))
            issues=errors(response)
        except forms.ValidationError as exc:issues=exc.messages
    hours=initial.get('hours',[])
    if request.method=='POST':
        hours=[{'day':d,'start':s,'end':e} for d,s,e in zip(request.POST.getlist('hour_day'),request.POST.getlist('hour_start'),request.POST.getlist('hour_end'))]
        if request.POST.get('attachments_present'):
            kept=request.POST.getlist('keep_image_id')
            initial['image_ids']=[value for value in initial.get('image_ids',[]) if str(value) in kept]
            form.data=form.data.copy();form.data['image_ids']=','.join(kept)
    return page(request,'dashboard/form.html',title=t(request,'تحرير فعالية' if kind=='event' else 'تحرير نقطة خدمة','Edit event' if kind=='event' else 'Edit service'),
        form=form,errors=issues,service_hours=kind=='service',hours=hours,
        day_names=list(enumerate(['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد'] if request.dashboard_language=='ar' else ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])),
        map_picker=True,staff_edit=staff,existing_images=initial.get('image_ids',[]),existing_pdf=initial.get('pdf_id'),duplicate_warning=duplicate_warning,
        new_image_ids=request.POST.getlist('new_image_id'))


def home(request):
    return section(request,'events')


@require_http_methods(['GET'])
def section(request,slug):
    spec={
        'events':('الفعاليات القادمة','Upcoming events','events/','public'),
        'services':('نقاط الخدمة','Service points','services/','public'),
        'categories':('التخصصات والمواضيع','Categories','categories/','public'),
        'mine':('محتواي','My items','me/items/','user'),
        'registrations':('تسجيلاتي','My registrations','me/registrations/','user'),
        'reviews':('قائمة المراجعة','Review queue','moderation/items/','reviewer'),
        'applications':('طلبات المنظّمين','Organizer applications','moderation/organizer-requests/','reviewer'),
        'reports':('البلاغات','Reports','moderation/reports/','reviewer'),
        'feedback':('الملاحظات','Feedback','moderation/feedback/','reviewer'),
        'users':('إدارة الحسابات','Manage accounts','admin/users/','admin'),
        'statistics':('الإحصاءات','Statistics','admin/statistics/','admin'),
        'audit':('سجل التدقيق','Audit log','admin/audit/','admin'),
        'announcements':('الإعلانات','Announcements','admin/announcements/','admin'),
        'locations':('المدن والبلدات','Cities and towns','cities/','admin'),
        'devices':('أجهزتي','My devices','me/devices/','user'),
        'requests':('طلباتي للمنظّم','My organizer requests','me/organizer-requests/','user'),
        'policies':('الشروط وسياسة الخصوصية','Terms and Privacy','policies/current/','public'),
    }
    if slug=='account':
        denied=guard(request,'user')
        if denied:return denied
        links=[link(request,name) for name in ['profile','preferences','verify','password','email','apply','organizer-profile','feedback','delete-account']]
        links += [{'text':t(request,'تنزيل بياناتي','Download my data'),'url':reverse('dashboard:download',args=['data',0])},link(request,'logout-all',button=True),
            {'text':t(request,'متابعاتي','My follows'),'url':reverse('dashboard:section',args=['follows'])},
            {'text':t(request,'أجهزتي','My devices'),'url':reverse('dashboard:section',args=['devices'])},
            {'text':t(request,'طلبات صفة المنظّم','Organizer applications'),'url':reverse('dashboard:section',args=['requests'])}]
        if allowed(request,'admin'):links += [link(request,'policies'),link(request,'app-settings')]
        return page(request,title=t(request,'حسابي','My account'),links=links)
    if slug=='follows':
        denied=guard(request,'user')
        if denied:return denied
        response=call(request,'/api/v1/me/follows/')
        if response.status_code!=200:return api_error(request,response)
        followed=values(response)
        cards=[]
        for organizer in User.objects.filter(pk__in=followed['organizer_ids']):
            cards.append({'title':organizer.name,'links':[link(request,'unfollow-organizer',organizer.pk,True)]})
        for category in Category.objects.filter(pk__in=followed['category_ids']):
            cards.append({'title':category.name_ar if request.dashboard_language=='ar' else category.name_en,'links':[link(request,'unfollow-category',category.pk,True)]})
        return page(request,title=t(request,'متابعاتي','My follows'),cards=cards)
    if slug=='map':
        return page(request,title=t(request,'خريطة نقاط الخدمة','Service map'),map_view=True)
    if slug=='manage':
        denied=guard(request,'reviewer')
        if denied:return denied
        audit(request.dashboard_user,'item.dashboard_manage_read')
        rows=Item.objects.select_related('proposed_revision','published_revision','reviewer').order_by('-pk')
        state=request.GET.get('status')
        if state in dict(Item.STATUSES):rows=rows.filter(status=state)
        try:number=max(1,int(request.GET.get('page',1)))
        except ValueError:number=1
        items=[item_data(row,request.dashboard_user,private=True,include_archive=True) for row in rows[(number-1)*30:number*30+1]]
        data={'results':items[:30],'next_page':number+1 if len(items)>30 else None}
        ar,en='إدارة جميع المحتويات','Manage all content'
    else:
        if slug not in spec:raise Http404
        ar,en,path,role=spec[slug]
        denied=guard(request,role)
        if denied:return denied
        query=request.GET.copy()
        for key in list(query):
            if not query[key]:del query[key]
        if slug=='events' and not query.get('sort'):query['sort']='date'
        response=call(request,'/api/v1/'+path+'?'+query.urlencode())
        if response.status_code!=200:return api_error(request,response)
        data=values(response)
    cards=[]
    rows=data.get('results',[]) if isinstance(data,dict) and 'results' in data else data
    if isinstance(rows,dict):rows=[rows]
    for row in rows or []:
        links=[]
        if 'kind' in row:
            name=row['payload'].get('title',row['payload'].get('name',''))
            links.append({'text':t(request,'فتح','Open'),'url':reverse('dashboard:detail',args=[row['kind'],row['id']])})
            if slug=='mine':links.append({'text':t(request,'تعديل','Edit'),'url':reverse('dashboard:item-edit',args=[row['kind'],row['id']])})
            if slug in ('reviews','manage'):links += moderation_links(request,row)
            fields=[(t(request,'الحالة','Status'),label(row['status'],request.dashboard_language))]
            if row.get('date_range'):
                fields.append((t(request,'نطاق المواعيد','Date range'),str(row['date_range']['start'])+' — '+str(row['date_range']['end'])))
            if row.get('occurrences'):
                fields.append((t(request,'الموعد المحلي للفعالية','Event local start'),row['occurrences'][0]['event_local_start']))
            if row['kind']=='service':
                fields.append((t(request,'مفتوح الآن','Open now'),t(request,'نعم','Yes') if row.get('open_now') else t(request,'لا','No')))
            if row.get('reviewer_name'):fields.append((t(request,'المراجع','Reviewer'),row['reviewer_name']))
            if row.get('duplicate_flag'):fields.append((t(request,'تنبيه','Warning'),t(request,'يوجد اسم مشابه','Similar name exists')))
            if row.get('rejection_reason'):fields.append((t(request,'سبب القرار','Decision reason'),row['rejection_reason']))
        else:
            name=(row.get('name') or row.get('name_ar' if request.dashboard_language=='ar' else 'name_en')
                or row.get('title_ar' if request.dashboard_language=='ar' else 'title_en') or str(row.get('id','')))
            fields=[(label(key,request.dashboard_language),label(value,request.dashboard_language) if key in ('state','status') else value)
                for key,value in row.items() if key not in ('id','name')]
            ident=row.get('id',0)
            if slug=='registrations':
                links=[link(request,key,ident,True) for key in ['cancel-registration','reconfirm']]
                links.append({'text':t(request,'الفعالية','Event'),'url':reverse('dashboard:occurrence',args=[row['occurrence_id']])})
            if slug in ('applications','requests'):
                fields=[(label(key,request.dashboard_language),value) for key,value in row.items() if key!='id']
                if slug=='applications':links=[link(request,'organizer-claim',ident,True),link(request,'organizer-decision',ident),link(request,'organizer-unlock',ident,True),{'text':t(request,'عرض الإثبات الخاص','View private credential'),'url':reverse('dashboard:download',args=['credential',ident])}]
            if slug=='reports':links=[link(request,'resolve',ident),{'text':t(request,'المحتوى','Item'),'url':reverse('dashboard:review',args=[row['item_id']])}] if row.get('item_id') else [link(request,'resolve',ident)]
            if slug=='users':links=[link(request,'roles',ident),link(request,'ban',ident),link(request,'delete-user',ident,True)]
            if slug=='categories':
                links=[link(request,'edit-category',ident),link(request,'follow-category',ident,True),link(request,'unfollow-category',ident,True),{'text':t(request,'فعاليات التخصص','Category events'),'url':reverse('dashboard:section',args=['events'])+'?category='+str(ident)}]
            if slug=='locations':links=[link(request,'edit-city',ident)]
            if slug=='devices':links=[link(request,'remove-device',ident,True)]
        cards.append({'title':name,'fields':fields,'links':links})
    top=[]
    if slug=='mine' and allowed(request,'organizer'):
        top=[{'text':t(request,'فعالية جديدة','New event'),'url':reverse('dashboard:item-create',args=['event'])},{'text':t(request,'نقطة خدمة جديدة','New service'),'url':reverse('dashboard:item-create',args=['service'])}]
    for section_name,ops in [('categories',['category']),('locations',['country','city','currency']),('announcements',['announcement'])]:
        if slug==section_name:top += [link(request,op) for op in ops]
    next_url=None
    parameter='page'
    next_value=data.get('next_page') if isinstance(data,dict) else None
    if slug=='locations' and response.get('X-Next-Page'):next_value=response['X-Next-Page']
    for key,param in [('next_after','after'),('next_before','before')]:
        if isinstance(data,dict) and data.get(key):next_value=data[key];parameter=param
    if next_value:
        query=request.GET.copy();query[parameter]=next_value;next_url='?'+query.urlencode()
    banners=values(call(request,'/api/v1/announcements/')) if slug=='events' else []
    return page(request,title=t(request,ar,en),cards=cards,links=top,next_url=next_url,banners=banners,
        organizer_guide=slug=='mine',
        filter_list=slug in ('events','services','locations','manage'),filters=references(request) if slug in ('events','services','locations') else {},section=slug)


def moderation_links(request,row):
    target=row['id']
    result=[{'text':t(request,'تفاصيل المراجعة','Review details'),'url':reverse('dashboard:review',args=[target])}]
    return result


@require_http_methods(['GET'])
def detail(request,kind,item_id):
    if kind not in ('event','service'):raise Http404
    response=call(request,f'/api/v1/{kind}s/{item_id}/?'+request.GET.urlencode())
    if response.status_code!=200:return api_error(request,response)
    row=values(response)
    if kind=='event':call(request,f'/api/v1/events/{item_id}/views/','POST')
    links=[link(request,'report',item_id)]
    if allowed(request,'organizer') and row['owner_id']==request.dashboard_user.pk:
        links += [{'text':t(request,'تعديل','Edit'),'url':reverse('dashboard:item-edit',args=[kind,item_id])},link(request,'duplicate',item_id) if kind=='event' else None]
    if row.get('owner_id'):
        links.append({'text':t(request,'المنظّم','Organizer'),'url':reverse('dashboard:organizer',args=[row['owner_id']])})
    if kind=='event':links.append(link(request,'series-register',item_id,True))
    if allowed(request,'reviewer'):links+=moderation_links(request,row)
    p=row['payload']
    linked=[]
    if kind=='service':
        response=call(request,f'/api/v1/services/{item_id}/events/')
        linked=(values(response) or {}).get('results',[]) if response.status_code==200 else []
    return page(request,'dashboard/detail.html',title=p.get('title',p.get('name','')),item=row,links=links,
        fields=content_fields(request,p),
        linked=linked,apk_url=(values(call(request,'/api/v1/app-settings/')) or {}).get('apk_download_url',''))


@require_http_methods(['GET'])
def review(request,item_id):
    denied=guard(request,'reviewer')
    if denied:return denied
    response=call(request,f'/api/v1/moderation/items/{item_id}/')
    if response.status_code!=200:return api_error(request,response)
    row=values(response)
    links=[link(request,op,item_id,True) for op in ('claim','hide','unhide','delete-item','restore','unlock')]
    links += [link(request,'decision',item_id),{'text':t(request,'تصحيح فوري بواسطة المشرف','Immediate staff correction'),'url':reverse('dashboard:staff-edit',args=[row['kind'],item_id])}]
    return page(request,'dashboard/detail.html',title=t(request,'مراجعة المحتوى','Review content'),item=row,links=links,
        fields=content_fields(request,row['payload']),
        notice=t(request,'حالة المراجعة: ','Review state: ')+label(row['status'],request.dashboard_language)+' / '+str(row.get('reviewer_name') or '—'))


@require_http_methods(['GET'])
def occurrence(request,occurrence_id):
    response=call(request,f'/api/v1/occurrences/{occurrence_id}/?'+request.GET.urlencode())
    if response.status_code!=200:return api_error(request,response)
    row=values(response)
    from django.utils import timezone
    readonly=row['archived'] or row['cancelled'] or row['starts_at']<=timezone.now()
    links=[{'text':t(request,'إضافة إلى التقويم','Add to calendar'),'url':reverse('dashboard:download',args=['calendar',occurrence_id])}]
    if not readonly:links += [link(request,'register',occurrence_id,True),link(request,'reminder',occurrence_id),link(request,'remove-reminder',occurrence_id,True)]
    if request.dashboard_user:
        # Roster access is enforced by the existing export API, including staff
        # stewardship restrictions. Never infer permission from a hidden button.
        roster=call(request,f'/api/v1/organizer/occurrences/{occurrence_id}/registrants/')
        if roster.status_code==200:
            if not readonly:links += [link(request,'reschedule',occurrence_id),link(request,'cancel-event',occurrence_id,True)]
            for fmt in ('csv','pdf','waitlist-csv','waitlist-pdf'):
                links.append({'text':t(request,'تنزيل المسجلين ','Export registrants ')+fmt,'url':reverse('dashboard:download',args=[fmt,occurrence_id])})
            stats=call(request,f'/api/v1/organizer/occurrences/{occurrence_id}/stats/')
            cards=[{'title':entry['name'],'fields':[(label(k,request.dashboard_language),v) for k,v in entry.items() if k!='name'],'links':[link(request,'remove-registration',entry['id'])]} for entry in values(roster)]
            if stats.status_code==200:cards.insert(0,{'title':t(request,'الإحصاءات','Statistics'),'fields':list(values(stats).items())})
        else:
            cards=[]
            if allowed(request,'reviewer') and not readonly:links += [link(request,'reschedule',occurrence_id),link(request,'cancel-event',occurrence_id,True)]
    else:cards=[]
    return page(request,title=row['payload'].get('title',''),fields=[(label(k,request.dashboard_language),v) for k,v in row.items() if k!='payload'],links=links,cards=cards,
        notice=t(request,'الموعد للقراءة فقط: انتهى أو أُلغي أو أُرشف.','Read-only occurrence: started, cancelled or archived.') if readonly else None)


@require_http_methods(['GET'])
def organizer(request,organizer_id):
    response=call(request,f'/api/v1/organizers/{organizer_id}/')
    if response.status_code!=200:return api_error(request,response)
    profile=values(response)
    events=values(call(request,f'/api/v1/organizers/{organizer_id}/events/')) or {}
    return page(request,title=profile['name'],notice=profile['bio'],verified=profile['verified'],
        photo_id=profile['photo_id'],
        links=[link(request,'follow-organizer',organizer_id,True),link(request,'unfollow-organizer',organizer_id,True)],
        cards=[{'title':row['payload'].get('title',''),'links':[{'text':t(request,'فتح','Open'),'url':reverse('dashboard:detail',args=['event',row['id']])}]} for row in events.get('results',[])])


@require_http_methods(['GET'])
def download(request,kind,target):
    paths={'data':'me/data-export/','credential':f'moderation/organizer-requests/{target}/credential/',
        'file':f'files/{target}/','calendar':f'occurrences/{target}/calendar.ics'}
    if kind in ('csv','pdf','waitlist-csv','waitlist-pdf'):
        paths[kind]=f'organizer/occurrences/{target}/registrants/export/?format={kind.split("-")[-1]}'+('&state=waitlisted' if kind.startswith('waitlist') else '')
    if kind not in paths:raise Http404
    response=call(request,'/api/v1/'+paths[kind])
    if response.status_code>=300:return api_error(request,response)
    if hasattr(response,'accepted_renderer'):response.render()
    return response


@require_http_methods(['GET'])
def location_data(request):
    response=call(request,'/api/v1/cities/?'+request.GET.urlencode())
    result=JsonResponse(values(response),safe=False,status=response.status_code)
    for name in ('X-Next-Page','X-Location-Attribution'):
        if response.get(name):result[name]=response[name]
    return result


@require_http_methods(['GET'])
def markers(request):
    response=call(request,'/api/v1/map/services/?'+request.GET.urlencode())
    return JsonResponse(values(response),status=response.status_code)


@require_http_methods(['POST'])
def upload(request,kind):
    if kind not in ('images','event-pdfs'):raise Http404
    denied=guard(request,'user')
    if denied:return denied
    file=request.FILES.get('file')
    if not file:return JsonResponse({'detail':t(request,'اختر ملفاً','Choose a file')},status=400)
    response=call(request,f'/api/v1/uploads/{kind}/','POST',files={'file':file})
    return JsonResponse(values(response),status=response.status_code)
