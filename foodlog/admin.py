from django.contrib import admin

from .models import FoodLog, FoodLogFeedback, FoodLogPhoto


class PhotoInline(admin.TabularInline):
    model = FoodLogPhoto
    extra = 0


class FeedbackInline(admin.TabularInline):
    model = FoodLogFeedback
    extra = 0
    raw_id_fields = ('author',)


@admin.register(FoodLog)
class FoodLogAdmin(admin.ModelAdmin):
    list_display = ('member', 'meal_type', 'log_date', 'calories', 'created_at')
    list_filter = ('meal_type', 'log_date')
    search_fields = ('member__member_id', 'member__first_name', 'description')
    raw_id_fields = ('member', 'gym')
    inlines = [PhotoInline, FeedbackInline]
