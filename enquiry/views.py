from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required

from .models import EnquiryData, EnquiryStatus
from .forms import EnquiryDataForm, EnquiryStatusForm, EnquiryFilterForm
from members.models import Member
from home.models import GymOffice

def get_base_queryset(user):
    """Return enquiries scoped to the user's gym, unless they are super admin."""
    if user.role == 'admin':
        return EnquiryData.objects.all()
    if user.gym:
        return EnquiryData.objects.filter(gym=user.gym)
    return EnquiryData.objects.none()

@login_required
def enquiries_dashboard(request):
    """Dashboard view with comprehensive statistics"""
    base_qs = get_base_queryset(request.user)
    
    total_enquiries = base_qs.count()
    converted_enquiries = base_qs.filter(conversion=True).count()
    pending_enquiries = base_qs.filter(conversion=False).count()
    
    status_breakdown = base_qs.values('status').annotate(
        count=Count('status')
    ).order_by('-count')
    
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    recent_enquiries = base_qs.filter(date_created__gte=thirty_days_ago).count()
    
    current_month = timezone.now().replace(day=1).date()
    this_month_enquiries = base_qs.filter(date_created__gte=current_month).count()
    
    today = timezone.now().date()
    today_enquiries = base_qs.filter(date_created=today).count()
    
    conversion_rate = (converted_enquiries / total_enquiries * 100) if total_enquiries > 0 else 0
    
    total_followups = EnquiryStatus.objects.filter(enquiry__in=base_qs).count()
    avg_followups = (total_followups / total_enquiries) if total_enquiries > 0 else 0
    
    needs_followup = base_qs.filter(
        Q(next_follow_up_date__lte=today) & Q(conversion=False)
    ).exclude(status__in=['completed', 'rejected', 'not_required']).count()
    
    overdue_followups = base_qs.filter(
        Q(next_follow_up_date__lt=today) & Q(conversion=False)
    ).exclude(status__in=['completed', 'rejected', 'not_required']).count()
    
    today_followups = base_qs.filter(
        Q(next_follow_up_date=today) & Q(conversion=False)
    ).exclude(status__in=['completed', 'rejected', 'not_required']).count()
    
    recent_enquiries_list = base_qs.order_by('-date_created')[:5]
    recent_followups = EnquiryStatus.objects.filter(enquiry__in=base_qs).select_related('enquiry').order_by('-date_of_status')[:5]
    
    call_status_breakdown = EnquiryStatus.objects.filter(enquiry__in=base_qs).values('call_status').annotate(
        count=Count('call_status')
    ).order_by('-count')
    
    todays_pending_followups = base_qs.filter(
        Q(next_follow_up_date__lte=today) & Q(conversion=False)
    ).exclude(status__in=['completed', 'rejected', 'not_required']).order_by('next_follow_up_date')[:5]
    
    monthly_data = []
    for i in range(5, -1, -1):
        month_start = (timezone.now().replace(day=1) - timedelta(days=32*i)).replace(day=1).date()
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        
        month_enquiries = base_qs.filter(date_created__gte=month_start, date_created__lt=next_month).count()
        month_conversions = base_qs.filter(date_created__gte=month_start, date_created__lt=next_month, conversion=True).count()
        
        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'enquiries': month_enquiries,
            'conversions': month_conversions
        })
    
    context = {
        'total_enquiries': total_enquiries,
        'converted_enquiries': converted_enquiries,
        'pending_enquiries': pending_enquiries,
        'conversion_rate': round(conversion_rate, 1),
        'recent_enquiries_count': recent_enquiries,
        'this_month_enquiries': this_month_enquiries,
        'today_enquiries': today_enquiries,
        'total_followups': total_followups,
        'avg_followups': round(avg_followups, 1),
        'needs_followup': needs_followup,
        'overdue_followups': overdue_followups,
        'today_followups': today_followups,
        'status_breakdown': status_breakdown,
        'call_status_breakdown': call_status_breakdown,
        'recent_enquiries_list': recent_enquiries_list,
        'recent_followups': recent_followups,
        'monthly_data': monthly_data,
        'todays_pending_followups': todays_pending_followups,
        'today': today,
    }
    
    return render(request, "enquiries/index.html", context)


@login_required
@transaction.atomic
def todays_followups(request):
    """View for today's and pending follow-ups"""
    base_qs = get_base_queryset(request.user)
    today = timezone.now().date()
    
    followup_enquiries = base_qs.filter(
        Q(next_follow_up_date__lte=today) & Q(conversion=False)
    ).exclude(status__in=['completed', 'rejected', 'not_required']).order_by('next_follow_up_date', 'name')
    
    todays_followups = followup_enquiries.filter(next_follow_up_date=today)
    overdue_followups = followup_enquiries.filter(next_follow_up_date__lt=today)
    
    next_week = today + timedelta(days=7)
    upcoming_followups = base_qs.filter(
        Q(next_follow_up_date__gt=today) & 
        Q(next_follow_up_date__lte=next_week) & 
        Q(conversion=False)
    ).exclude(status__in=['completed', 'rejected', 'not_required']).order_by('next_follow_up_date', 'name')
    
    if request.method == 'POST' and 'enquiry_id' in request.POST:
        enquiry_id = request.POST.get('enquiry_id')
        quick_status = request.POST.get('quick_status')
        quick_notes = request.POST.get('quick_notes', '')
        
        enquiry = get_object_or_404(base_qs, id=enquiry_id)
        
        EnquiryStatus.objects.create(
            enquiry=enquiry,
            description=quick_notes or f"Quick update: {quick_status}",
            status=enquiry.status,
            call_status=quick_status
        )
        
        enquiry.number_of_followup += 1
        enquiry.last_follow_up_date = today
        
        if quick_status == 'callback':
            enquiry.next_follow_up_date = today + timedelta(days=1)
        elif quick_status == 'follow_up':
            enquiry.next_follow_up_date = today + timedelta(days=3)
        elif quick_status == 'converted':
            if not enquiry.conversion and not enquiry.converted_member:
                enquiry.conversion = True
                enquiry.next_follow_up_date = None
                enquiry.status = 'completed'
                member = _create_member_from_enquiry(enquiry.gym, enquiry)
                enquiry.converted_member = member
                messages.success(request, f"Member {member.member_id} created for {enquiry.name}")
        elif quick_status == 'not_interested':
            enquiry.status = 'rejected'
            enquiry.next_follow_up_date = None
        elif quick_status == 'closed':
            enquiry.status = 'not_required'
            enquiry.next_follow_up_date = None
        else:
            enquiry.next_follow_up_date = today + timedelta(days=2)
        
        enquiry.save()
        messages.success(request, f"Quick update added for {enquiry.name}")
        return redirect('enquiries:todays_followups')
    
    context = {
        'todays_followups': todays_followups,
        'overdue_followups': overdue_followups,
        'upcoming_followups': upcoming_followups,
        'total_due': followup_enquiries.count(),
        'today_count': todays_followups.count(),
        'overdue_count': overdue_followups.count(),
        'upcoming_count': upcoming_followups.count(),
        'today': today,
    }
    
    return render(request, 'enquiries/todays_followups.html', context)


@login_required
def enquiry_list(request):
    """View to list all enquiries with filtering options"""
    enquiries = get_base_queryset(request.user).order_by('-date_created')
    filter_form = EnquiryFilterForm(request.GET or None)
    
    if filter_form.is_valid():
        conversion = filter_form.cleaned_data.get('conversion')
        status = filter_form.cleaned_data.get('status')
        search = filter_form.cleaned_data.get('search')
        start_date = filter_form.cleaned_data.get('start_date')
        end_date = filter_form.cleaned_data.get('end_date')
        
        if conversion:
            enquiries = enquiries.filter(conversion=(conversion == 'True'))
        if status:
            enquiries = enquiries.filter(status=status)
        if start_date:
            enquiries = enquiries.filter(date_created__gte=start_date)
        if end_date:
            enquiries = enquiries.filter(date_created__lte=end_date)
        if search:
            enquiries = enquiries.filter(
                Q(name__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(email__icontains=search)
            )
    else:
        if not request.GET:
             enquiries = enquiries.filter(conversion=False)

    context = {
        'enquiries': enquiries,
        'filter_form': filter_form,
        'total_enquiries': enquiries.count()
    }
    
    return render(request, 'enquiries/enquiry_list.html', context)


@login_required
def enquiry_detail(request, pk):
    """View to display single enquiry details"""
    enquiry = get_object_or_404(get_base_queryset(request.user), pk=pk)
    statuses = enquiry.statuses.order_by('-date_of_status')
    
    context = {
        'enquiry': enquiry,
        'statuses': statuses,
    }
    return render(request, 'enquiries/enquiry_detail.html', context)


@login_required
def enquiry_create(request):
    """View to create new enquiry"""
    if request.user.role == 'admin':
        messages.error(request, 'Super admin cannot create enquiries without a specific gym context.')
        return redirect('enquiries:enquiry_list')

    if request.method == 'POST':
        form = EnquiryDataForm(request.POST)
        if form.is_valid():
            enquiry = form.save(commit=False)
            enquiry.gym = request.user.gym
            enquiry.save()
            messages.success(request, 'New enquiry created successfully!')
            return redirect('enquiries:enquiry_detail', pk=enquiry.pk)
    else:
        form = EnquiryDataForm()
    
    return render(request, 'enquiries/enquiry_form.html', {'form': form, 'title': 'Create Enquiry'})


@login_required
def enquiry_update(request, pk):
    """View to update enquiry details"""
    enquiry = get_object_or_404(get_base_queryset(request.user), pk=pk)
    
    if request.method == 'POST':
        form = EnquiryDataForm(request.POST, instance=enquiry)
        if form.is_valid():
            form.save()
            messages.success(request, 'Enquiry updated successfully!')
            return redirect('enquiries:enquiry_detail', pk=pk)
    else:
        form = EnquiryDataForm(instance=enquiry)
    
    return render(request, 'enquiries/enquiry_form.html', {'form': form, 'enquiry': enquiry, 'title': 'Update Enquiry'})


def _create_member_from_enquiry(gym, enquiry):
    """Helper method to create a member from a converted enquiry"""
    names = enquiry.name.split()
    first_name = names[0] if names else "Unknown"
    last_name = " ".join(names[1:]) if len(names) > 1 else ""
    
    # Generate unique mobile number if collision
    mobile = enquiry.phone_number
    if Member.all_objects.filter(gym=gym, mobile_number=mobile).exists():
        original_mobile = mobile
        counter = 1
        while Member.all_objects.filter(gym=gym, mobile_number=mobile).exists():
            suffix = f"-DUP{counter}" if counter > 1 else "-DUP"
            # Limit mobile number to 20 chars
            mobile = f"{original_mobile[:20-len(suffix)]}{suffix}"
            counter += 1
        
    member = Member.objects.create(
        gym=gym,
        first_name=first_name,
        last_name=last_name,
        mobile_number=mobile,
        email=enquiry.email,
        gender="Other",
        registration_date=timezone.now().date()
    )
    return member


@login_required
@transaction.atomic
def add_status_update(request, pk):
    """View to add new status update to an enquiry"""
    enquiry = get_object_or_404(get_base_queryset(request.user), pk=pk)
    
    if request.method == 'POST':
        form = EnquiryStatusForm(request.POST)
        next_followup = request.POST.get('next_followup')
        
        if form.is_valid():
            status = form.save(commit=False)
            status.enquiry = enquiry
            status.save()
            
            enquiry.status = status.status
            enquiry.number_of_followup += 1
            enquiry.last_follow_up_date = timezone.now().date()
            
            if status.call_status == 'converted':
                if not enquiry.conversion and not enquiry.converted_member:
                    enquiry.conversion = True
                    member = _create_member_from_enquiry(enquiry.gym, enquiry)
                    enquiry.converted_member = member
                    messages.success(request, f'Enquiry converted and member {member.member_id} created!')

            if next_followup:
                enquiry.next_follow_up_date = next_followup
            enquiry.save()
            
            messages.success(request, 'Status update added successfully!')
            return redirect('enquiries:enquiry_detail', pk=pk)
    else:
        form = EnquiryStatusForm()
    
    return render(request, 'enquiries/add_status_update.html', {'form': form, 'enquiry': enquiry})
