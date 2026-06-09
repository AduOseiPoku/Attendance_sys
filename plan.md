This is the complete, comprehensive guide to building your QR Code Attendance and Onboarding System from scratch. By following this step-by-step breakdown, you will transition from an empty folder to a fully functioning application backed by Django and PostgreSQL.

---

## 🛠️ Prerequisites & Stack Architecture

* **Backend:** Django 5.x (Python 3.10+)
* **Database:** PostgreSQL
* **Frontend:** Mobile-responsive Tailwind CSS (via CDN for speed)
* **QR Generation:** Python `qrcode` library

---

# 🏃‍♂️ Sprint 1: Environment, PostgreSQL Setup & Database Models

**Goal:** Initialize your project repository, connect Django to a live PostgreSQL database, and define your data schemas.

### 1.1 Set Up PostgreSQL

Open your terminal or PostgreSQL CLI (`psql`) and run the following commands to create a fresh database and user:

```sql
CREATE DATABASE attendance_db;
CREATE USER attendance_admin WITH PASSWORD 'SecurePassword123';
ALTER ROLE attendance_admin SET client_encoding TO 'utf8';
ALTER ROLE attendance_admin SET default_transaction_isolation TO 'read committed';
ALTER ROLE attendance_admin SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE attendance_db TO attendance_admin;

```

### 1.2 Initialize the Django Project

In your terminal, navigate to your development directory and execute:

```bash
# Create directory and virtual environment
mkdir qr_attendance && cd qr_attendance
python -n venv venv
source .venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install core dependencies
pip install django psycopg2-binary qrcode[pil]

# Start Django project and application
django-admin startproject core .
python manage.py startapp attendance

```

### 1.3 Configure Database Connections

Open `core/settings.py`, add your app to `INSTALLED_APPS`, and swap out the default SQLite configuration for your PostgreSQL credentials:

```python
# core/settings.py

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'attendance', # Your new app
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'attendance_db',
        'USER': 'attendance_admin',
        'PASSWORD': 'SecurePassword123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

```

### 1.4 Define the Database Schemas

Open `attendance/models.py` and implement the relational mapping for your system:

```python
# attendance/models.py
from django.db import models

class Member(models.Model):
    student_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.student_id})"

class Event(models.Model):
    name = models.CharField(max_length=200)
    date = models.DateField()

    def __str__(self):
        return f"{self.name} ({self.date})"

class AttendanceLog(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('member', 'event') # Prevents double-scanning the same event

    def __str__(self):
        return f"{self.member.name} - {self.event.name}"

```

### 1.5 Execute Migrations & Create Admin Superuser

Run the following terminal commands to build your database tables and create your primary admin access credentials:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

```

---

# 🏃‍♂️ Sprint 2: Core Routing Views & Business Logic

**Goal:** Build the logical routing views that handle incoming user IDs, process check-ins, or route unregistered users into the onboarding flow.

### 2.1 Write Business Logic Views

Open `attendance/views.py` and write the operational routing methods:

```python
# attendance/views.py
from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Member, Event, AttendanceLog

def scan_landing(request, event_id):
    """Initial checkpoint when a member scans the QR code."""
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return HttpResponse("Event not found.", status=404)

    if request.method == "POST":
        entered_id = request.POST.get('student_id').strip()
        
        # Look up member in PostgreSQL
        member = Member.objects.filter(student_id=entered_id).first()
        
        if member:
            # Branch A: Member exists -> Log attendance and show success screen
            AttendanceLog.objects.get_or_create(member=member, event=event)
            return render(request, 'attendance/success.html', {
                'message': f"Welcome back, {member.name}! Your attendance for {event.name} has been logged."
            })
        else:
            # Branch B: Member missing -> Redirect to registration with ID preset
            return redirect(f"/onboard/{event_id}/?id={entered_id}")

    return render(request, 'attendance/scan_landing.html', {'event': event})


def onboard_member(request, event_id):
    """Dynamic form to capture unregistered guests and sign them into the event."""
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return HttpResponse("Event not found.", status=404)

    suggested_id = request.GET.get('id', '')

    if request.method == "POST":
        student_id = request.POST.get('student_id').strip()
        name = request.POST.get('name').strip()
        phone = request.POST.get('phone').strip()
        address = request.POST.get('address').strip()

        # Write new profile record to database
        new_member = Member.objects.create(
            student_id=student_id,
            name=name,
            phone_number=phone,
            address=address
        )

        # Log check-in entry instantly
        AttendanceLog.objects.create(member=new_member, event=event)

        return render(request, 'attendance/success.html', {
            'message': f"Registration complete! You have been checked into {event.name}."
        })

    return render(request, 'attendance/onboard.html', {
        'suggested_id': suggested_id, 
        'event': event
    })

```

### 2.2 Configure Routing Profiles

Create the file `attendance/urls.py` to maps paths to your functions:

```python
# attendance/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('scan/<int:event_id>/', views.scan_landing, name='scan_landing'),
    path('onboard/<int:event_id>/', views.onboard_member, name='onboard_member'),
]

```

Now connect it to your root routing tree inside `core/urls.py`:

```python
# core/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.目で),
    path('', include('attendance.urls')),
]

```

---

# 🏃‍♂️ Sprint 3: UI Design & Admin Dashboard Analytics

**Goal:** Build clean frontend templates and supercharge your built-in Django dashboard to generate real-time metrics for who is missing.

### 3.1 Structure Your UI Templates

Create the necessary folder structures inside your directory app:

```bash
mkdir -p attendance/templates/attendance

```

#### File 1: `attendance/templates/attendance/scan_landing.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Event Check-In</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-slate-50 flex items-center justify-center min-h-screen p-4">
    <div class="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 max-w-md w-full text-center">
        <div class="w-16 h-16 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 font-bold text-xl">📲</div>
        <h2 class="text-2xl font-bold text-slate-800">Check-In</h2>
        <p class="text-slate-500 mt-1">Welcome to <span class="font-semibold text-slate-700">{{ event.name }}</span></p>
        
        <form method="POST" class="mt-6 text-left">
            {% csrf_token %}
            <label class="block text-sm font-medium text-slate-600">Member ID Number</label>
            <input type="text" name="student_id" placeholder="Enter ID to verify" class="w-full mt-2 p-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" required autofocus>
            <button type="submit" class="w-full mt-4 bg-blue-600 hover:bg-blue-700 text-white font-medium p-3 rounded-lg transition">Submit Attendance</button>
        </form>
    </div>
</body>
</html>

```

#### File 2: `attendance/templates/attendance/onboard.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Member Registration</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-slate-50 min-h-screen p-6 flex items-center justify-center">
    <div class="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 max-w-md w-full">
        <h3 class="text-xl font-bold text-slate-800">ID Not Found</h3>
        <p class="text-slate-500 text-sm mt-1">Please enter your profile details below to complete your event registration.</p>
        
        <form method="POST" class="mt-4 space-y-4">
            {% csrf_token %}
            <div>
                <label class="block text-sm font-medium text-slate-600">ID Number</label>
                <input type="text" name="student_id" value="{{ suggested_id }}" class="w-full mt-1 p-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-600">Full Name</label>
                <input type="text" name="name" placeholder="John Doe" class="w-full mt-1 p-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-600">Phone Number</label>
                <input type="tel" name="phone" placeholder="e.g., +233501234567" class="w-full mt-1 p-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required>
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-600">Residential Address</label>
                <textarea name="address" rows="3" placeholder="Enter physical or digital address" class="w-full mt-1 p-2.5 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" required></textarea>
            </div>
            <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium p-3 rounded-lg transition">Complete Registration</button>
        </form>
    </div>
</body>
</html>

```

#### File 3: `attendance/templates/attendance/success.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Success</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
</head>
<body class="bg-slate-50 flex items-center justify-center min-h-screen p-4">
    <div class="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 max-w-sm w-full text-center">
        <div class="w-16 h-16 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">✓</div>
        <h2 class="text-2xl font-bold text-slate-800">Success!</h2>
        <p class="text-slate-600 mt-2 text-sm">{{ message }}</p>
    </div>
</body>
</html>

```

### 3.2 Inject Present vs. Absent Tables Into Django Admin

Open `attendance/admin.py` and implement our customized admin tracking script to view real-time calculations directly within the dashboard:

```python
# attendance/admin.py
from django.contrib import admin
from .models import Member, Event, AttendanceLog

admin.site.register(Member)
admin.site.register(AttendanceLog)

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        event = self.get_object(request, object_id)
        
        if event:
            # 1. Fetch IDs of users tracked as present inside PostgreSQL logs
            present_member_ids = AttendanceLog.objects.filter(event=event).values_list('member_id', flat=True)
            
            # 2. Separate into Present vs Absent rosters
            extra_context['present_members'] = Member.objects.filter(id__in=present_member_ids)
            extra_context['absent_members'] = Member.objects.exclude(id__in=present_member_ids)
            
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

```

Create a custom admin template file path to display these lists visually:
`templates/admin/attendance/event/change_form.html`

```html
{% extends "admin/change_form.html" %}
{% block after_field_sets %}
<hr style="margin: 30px 0; border-color: #ccc;">
<h2>Live Attendance Reports</h2>
<div style="display: flex; gap: 40px; margin-top: 20px;">
    
    <div style="flex: 1; background: #f6fff6; border: 1px solid #c2ecc2; padding: 15px; border-radius: 6px;">
        <h3 style="color: #28a745; margin-top:0;">✓ Present Members ({{ present_members|length }})</h3>
        <ul>
            {% for member in present_members %}
                <li><strong>{{ member.name }}</strong> ({{ member.student_id }})</li>
            {% empty %}
                <li style="color: #666;">No check-ins logged yet.</li>
            {% endfor %}
        </ul>
    </div>

    <div style="flex: 1; background: #fff5f5; border: 1px solid #fbcbcb; padding: 15px; border-radius: 6px;">
        <h3 style="color: #dc3545; margin-top:0;">𐄂 Absent Members ({{ absent_members|length }})</h3>
        <ul>
            {% for member in absent_members %}
                <li><strong>{{ member.name }}</strong> ({{ member.student_id }})</li>
            {% empty %}
                <li style="color: #666;">Everyone is accounted for!</li>
            {% endfor %}
        </ul>
    </div>
</div>
{% endblock %}

```

*(Make sure your main `settings.py` template block points to your base custom `templates` folder layout).*

---

# 🏃‍♂️ Sprint 4: QR Engine Utilities & Network Integration Testing

**Goal:** Generate physical vector assets, run structural checks over local device networks, and complete development validation profiles.

### 4.1 Write Your Standalone Asset Engine

Create a file named `generate_qr.py` in your root project folder to generate barcodes linked to specific events:

```python
# generate_qr.py
import qrcode

# Configure using your computer's local Wi-Fi IP address (e.g., 192.168.1.50) for cross-device testing
host_domain = "http://192.168.1.100:8000" 
event_id = 1 # Your target database Event primary key reference

target_route = f"{host_domain}/scan/{event_id}/"

qr = qrcode.QRCode(version=1, box_size=10, border=4)
qr.add_data(target_route)
qr.make(fit=True)

img = qr.make_image(fill_color="black", back_color="white")
img.save(f"live_event_{event_id}_barcode.png")

print(f"QR Vector successfully compiled matching view configuration route: {target_route}")

```

### 4.2 Cross-Device Verification

1. Connect both your running workstation laptop and your test mobile phone to the **same local Wi-Fi router network**.
2. Find your computer's local private network IP address (via terminal tool commands like `ifconfig` or `ipconfig`). Run the script above using that IP address.
3. Boot up the development instance bound directly to that network node layout:
```bash
python manage.py runserver 0.0.0.0:8000

```


4. Open the newly created `live_event_1_barcode.png` asset image file on your screen, point your mobile device camera at it, and click open the linked URL block.
5. Test both workflows: submit an ID that already exists in your system, and another that triggers the onboarding screen to verify everything saves instantly to your PostgreSQL database.



Example queries you'll be able to run later

Get all attendees for an event:

event.attendance_logs.select_related("member")

Get attendance history for a member:

member.attendance_logs.select_related("event")

Count attendance for an event:

AttendanceLog.objects.filter(event=event).count()