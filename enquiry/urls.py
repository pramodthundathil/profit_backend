from django.urls import path
from . import views

app_name = 'enquiries'

urlpatterns = [
    path('dashboard/', views.enquiries_dashboard, name='dashboard'),
    path('todays-followups/', views.todays_followups, name='todays_followups'),
    path('list/', views.enquiry_list, name='enquiry_list'),
    path('create/', views.enquiry_create, name='enquiry_create'),
    path('<int:pk>/', views.enquiry_detail, name='enquiry_detail'),
    path('<int:pk>/update/', views.enquiry_update, name='enquiry_update'),
    path('<int:pk>/add-status/', views.add_status_update, name='add_status_update'),
]
