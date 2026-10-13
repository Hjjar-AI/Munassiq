from django.urls import path
from . import views as v

urlpatterns = [
    path('auth/signup/', v.SignupView.as_view()),
    path('auth/login/', v.LoginView.as_view()),
    path('auth/refresh/', v.RefreshView.as_view()),
    path('auth/logout/', v.LogoutView.as_view()),
    path('auth/logout-all/', v.LogoutAllView.as_view()),
    path('auth/verification/request/', v.VerificationRequestView.as_view()),
    path('auth/verification/confirm/', v.VerifyView.as_view()),
    path('auth/password/forgot/', v.ForgotPasswordView.as_view()),
    path('auth/password/reset/', v.ResetView.as_view()),
    path('me/', v.MeView.as_view()),
    path('me/password/change/', v.ChangePasswordView.as_view()),
    path('me/email/change/', v.ChangeEmailView.as_view()),
    path('me/email/confirm/', v.ConfirmEmailView.as_view()),
    path('me/data-export/', v.ExportView.as_view()),
    path('policies/current/', v.PolicyView.as_view()),
    path('admin/users/<int:user_id>/roles/', v.AdminRoleView.as_view()),
    path('admin/users/<int:user_id>/ban/', v.AdminBanView.as_view()),
    path('admin/users/', v.AdminUsersView.as_view()),
    path('admin/users/<int:user_id>/', v.AdminDeleteUserView.as_view()),
    path('admin/policies/', v.AdminPolicyView.as_view()),
    path('admin/audit/', v.AdminAuditView.as_view()),
]

from . import organizers as o
urlpatterns += [
    path('organizer-requests/', o.ApplyView.as_view()),
    path('me/organizer-requests/', o.MyRequestsView.as_view()),
    path('moderation/organizer-requests/', o.ReviewQueueView.as_view()),
    path('moderation/organizer-requests/<int:request_id>/claim/', o.ClaimView.as_view()),
    path('moderation/organizer-requests/<int:request_id>/credential/', o.CredentialView.as_view()),
    path('moderation/organizer-requests/<int:request_id>/decide/', o.DecideView.as_view()),
    path('admin/organizer-requests/<int:request_id>/unlock/', o.UnlockView.as_view()),
]
