from django.urls import path
from . import views as v

app_name='dashboard'
urlpatterns=[
    path('',v.home,name='home'),
    path('login/',v.login,name='login'),
    path('logout/',v.logout,name='logout'),
    path('language/',v.language,name='language'),
    path('section/<slug:slug>/',v.section,name='section'),
    path('form/<slug:operation>/<int:target>/',v.operation_form,name='form'),
    path('action/<slug:operation>/<int:target>/',v.action,name='action'),
    path('new/<slug:kind>/',v.item_form,name='item-create'),
    path('edit/<slug:kind>/<int:item_id>/',v.item_form,name='item-edit'),
    path('correct/<slug:kind>/<int:item_id>/',v.item_form,{'staff':True},name='staff-edit'),
    path('items/<slug:kind>/<int:item_id>/',v.detail,name='detail'),
    path('review/<int:item_id>/',v.review,name='review'),
    path('occurrences/<int:occurrence_id>/',v.occurrence,name='occurrence'),
    path('organizers/<int:organizer_id>/',v.organizer,name='organizer'),
    path('download/<slug:kind>/<int:target>/',v.download,name='download'),
    path('locations/',v.location_data,name='locations'),
    path('markers/',v.markers,name='markers'),
    path('upload/<slug:kind>/',v.upload,name='upload'),
]
