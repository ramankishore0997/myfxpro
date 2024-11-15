
from django.contrib import admin
from django.urls import path
from .views import *
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomePage.as_view(), name='landing_page'),
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('profile/', profile_view, name='profile'),
    path('trades/', UserTradesView.as_view(), name='user_trades'),

    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    path('deposit/', DepositView.as_view(), name='deposit'),
    path('withdraw/', WithdrawView.as_view(), name='withdraw'),
    path('deposit-request/', deposit_request_view, name='deposit-request'),

    path('kyc-submission/', KYCSubmissionView.as_view(), name='kyc_submission'),
    path('kyc-pending/', KYCPendingView.as_view(), name='kyc_pending'),
    path('verify-email/<uidb64>/<token>/', verify_email, name='email_verify'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)