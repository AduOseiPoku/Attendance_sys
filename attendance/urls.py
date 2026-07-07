# attendance/urls.py
from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.global_landing, name='global_landing'),
    path('api/church-events/<uuid:church_uuid>/', views.get_church_events, name='get_church_events'),
    # --- Member-facing check-in flows ---
    path('scan/<uuid:event_uuid>/', views.scan_landing, name='scan_landing'),
    path('onboard/<uuid:event_uuid>/', views.onboard_member, name='onboard_member'),

    # Unified resolution endpoint handling both name and phone suggestion forms securely
    path('confirm/<uuid:event_uuid>/<uuid:member_uuid>/', views.confirm_identity, name='confirm_identity'),
    path('quick-checkin/<uuid:event_uuid>/', views.quick_checkin, name='quick_checkin'),

    # --- Church Owner Dashboard ---
    path('owner/login/',              views.owner_login,         name='owner_login'),
    path('owner/logout/',             views.owner_logout,        name='owner_logout'),
    path('owner/',                    views.owner_dashboard,     name='owner_dashboard'),
    path('owner/members/',            views.owner_members,       name='owner_members'),
    path('owner/event/<int:pk>/',     views.owner_event_detail,  name='owner_event_detail'),
    path('owner/event/<int:pk>/toggle/', views.owner_toggle_event_status, name='owner_toggle_event_status'),
    path('owner/event/create/',        views.owner_create_event,  name='owner_create_event'),
]