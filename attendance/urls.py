# attendance/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('scan/<int:event_id>/', views.scan_landing, name='scan_landing'),
    path('onboard/<int:event_id>/', views.onboard_member, name='onboard_member'),
    
    # Unified resolution endpoint handling both name and phone suggestion forms securely
    path('confirm/<int:event_id>/<int:member_id>/', views.confirm_identity, name='confirm_identity'),
]