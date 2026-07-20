# attendance/urls.py
from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.global_landing, name='global_landing'),
    path('church/<uuid:church_uuid>/', views.church_events, name='church_events'),
    path('api/church-events/<uuid:church_uuid>/', views.get_church_events, name='get_church_events'),

    # --- Member-facing check-in flows ---
    path('scan/<uuid:event_uuid>/', views.scan_landing, name='scan_landing'),
    path('onboard/<uuid:event_uuid>/', views.onboard_member, name='onboard_member'),
    path('church/<uuid:church_uuid>/onboard/', views.onboard_church_member, name='onboard_church_member'),

    # Unified resolution endpoint handling both name and phone suggestion forms securely
    path('confirm/<uuid:event_uuid>/<uuid:member_uuid>/', views.confirm_identity, name='confirm_identity'),
    path('quick-checkin/<uuid:event_uuid>/', views.quick_checkin, name='quick_checkin'),

    # --- Church Owner Dashboard ---
    path('owner/login/',                                    views.owner_login,               name='owner_login'),
    path('owner/logout/',                                   views.owner_logout,              name='owner_logout'),
    path('owner/',                                          views.owner_dashboard,           name='owner_dashboard'),
    path('owner/members/',                                  views.owner_members,             name='owner_members'),
    path('owner/member/<uuid:member_uuid>/edit/',           views.owner_edit_member,         name='owner_edit_member'),
    path('owner/member/<uuid:member_uuid>/deactivate/',     views.owner_deactivate_member,   name='owner_deactivate_member'),
    path('owner/graduation-years/',                         views.owner_graduation_years,     name='owner_graduation_years'),
    path('owner/graduation-years/edit/<int:year_id>/',      views.owner_edit_graduation_year, name='owner_edit_graduation_year'),
    path('owner/graduation-years/delete/<int:year_id>/',    views.owner_delete_graduation_year, name='owner_delete_graduation_year'),
    path('owner/departments/',                              views.owner_departments,          name='owner_departments'),
    path('owner/departments/edit/<int:dept_id>/',           views.owner_edit_department,      name='owner_edit_department'),
    path('owner/departments/delete/<int:dept_id>/',         views.owner_delete_department,    name='owner_delete_department'),
    path('owner/events/',                                   views.owner_events,              name='owner_events'),
    path('owner/event/<uuid:event_uuid>/',                  views.owner_event_detail,        name='owner_event_detail'),
    path('owner/event/<uuid:event_uuid>/toggle/',           views.owner_toggle_event_status, name='owner_toggle_event_status'),
    path('owner/event/<uuid:event_uuid>/edit/',             views.owner_edit_event,          name='owner_edit_event'),
    path('owner/event/<uuid:event_uuid>/export/',           views.owner_export_event_csv,    name='owner_export_event_csv'),
    path('owner/event/create/',                             views.owner_create_event,        name='owner_create_event'),
]