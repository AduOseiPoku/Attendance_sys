# attendance/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # --- Member-facing check-in flows ---
    path('scan/<int:event_id>/', views.scan_landing, name='scan_landing'),
    path('onboard/<int:event_id>/', views.onboard_member, name='onboard_member'),

    # Unified resolution endpoint handling both name and phone suggestion forms securely
    path('confirm/<int:event_id>/<int:member_id>/', views.confirm_identity, name='confirm_identity'),
    path('quick_checkin/<int:event_id>/', views.quick_checkin, name='quick_checkin'),

    # --- Church Owner Dashboard ---
    path('owner/login/',              views.owner_login,         name='owner_login'),
    path('owner/logout/',             views.owner_logout,        name='owner_logout'),
    path('owner/',                    views.owner_dashboard,     name='owner_dashboard'),
    path('owner/members/',            views.owner_members,       name='owner_members'),
    path('owner/event/<int:pk>/',     views.owner_event_detail,  name='owner_event_detail'),
]