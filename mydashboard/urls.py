from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from myapp import views as myapp_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('home/', myapp_views.home, name='home'),
    path('', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('accounts/register/', myapp_views.register, name='register'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('api/sensor-data/', myapp_views.receive_sensor_data, name='receive_sensor_data'),
    path('fleet/', myapp_views.fleet_dashboard, name='fleet_dashboard'),
    path('api/sensor-data/', myapp_views.receive_sensor_data, name='api_sensor_data'),
]
