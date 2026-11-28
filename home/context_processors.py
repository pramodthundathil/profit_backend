def currency_context(request):
    """
    Context processor to add currency symbol and code to the template context.
    For logged-in users, it uses their gym's currency.
    """
    if request.user.is_authenticated and hasattr(request.user, 'gym') and request.user.gym:
        return {
            'currency_symbol': request.user.gym.currency_symbol or '₹',
            'currency_code': request.user.gym.currency_code or 'INR'
        }
    return {
        'currency_symbol': '₹',
        'currency_code': 'INR'
    }


def theme_assets(request):
    """Cache-busting version for the shared theme CSS/JS (file mtime)."""
    import os
    from django.contrib.staticfiles import finders

    version = 0
    for rel in ('css/profit-theme.css', 'js/profit-theme.js'):
        path = finders.find(rel)
        if path:
            version = max(version, int(os.path.getmtime(path)))
    return {'theme_version': version}
