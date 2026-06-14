# attendance/decorators.py
"""
Custom authentication decorator for the Church Owner dashboard.
Only users who:
  1. Are authenticated (logged in), AND
  2. Have an associated ChurchOwner profile
are allowed through. Everyone else is redirected to the owner login page.
"""
from functools import wraps
from django.shortcuts import redirect


def owner_required(view_func):
    """
    Decorator that restricts a view to authenticated ChurchOwner accounts only.
    Usage:
        @owner_required
        def my_view(request):
            ...
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check 1: Must be logged in
        if not request.user.is_authenticated:
            return redirect("owner_login")

        # Check 2: Must have a linked ChurchOwner profile
        if not hasattr(request.user, "church_owner"):
            return redirect("owner_login")

        return view_func(request, *args, **kwargs)

    return _wrapped_view
