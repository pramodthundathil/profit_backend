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
