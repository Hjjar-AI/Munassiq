from django.urls import path
from . import views as v

urlpatterns = [
    path('me/notification-preferences/', v.PreferenceView.as_view()),
    path('me/devices/', v.DeviceListView.as_view()),
    path('me/devices/<int:device_id>/', v.DeviceDetailView.as_view()),
    path('me/follows/', v.FollowListView.as_view()),
    path('me/follows/organizers/<int:organizer_id>/', v.OrganizerFollowView.as_view()),
    path('me/follows/categories/<int:category_id>/', v.CategoryFollowView.as_view()),
    path('admin/statistics/', v.AdminStatisticsView.as_view()),
    path('admin/announcements/', v.AdminAnnouncementView.as_view()),
    path('announcements/', v.BannerView.as_view()),
    path('app-settings/', v.PublicSettingsView.as_view()),
    path('admin/app-settings/', v.AdminSettingsView.as_view()),
]
