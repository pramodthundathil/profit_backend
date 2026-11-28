from django.contrib import admin

from .models import MemberAppAccount, MemberAppSettings


@admin.register(MemberAppSettings)
class MemberAppSettingsAdmin(admin.ModelAdmin):
    list_display = ('gym', 'member_login_enabled', 'community_feed_enabled', 'public_feed_enabled',
                    'food_log_enabled', 'trainer_instructions_enabled', 'updated_at')
    list_filter = ('member_login_enabled', 'public_feed_enabled')
    search_fields = ('gym__name',)


@admin.register(MemberAppAccount)
class MemberAppAccountAdmin(admin.ModelAdmin):
    list_display = ('member', 'must_change_password', 'credentials_sent_at', 'password_changed_at', 'enabled_at')
    search_fields = ('member__member_id', 'member__first_name', 'member__email')
    raw_id_fields = ('member', 'enabled_by')
