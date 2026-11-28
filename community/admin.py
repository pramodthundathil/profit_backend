from django.contrib import admin

from .models import Post, PostComment, PostMedia, PostReport, SocialProfile, UserBlock


class MediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'gym', 'author', 'visibility', 'status', 'like_count', 'comment_count', 'report_count', 'created_at')
    list_filter = ('visibility', 'status', 'kind')
    search_fields = ('text', 'author__email')
    raw_id_fields = ('gym', 'author')
    inlines = [MediaInline]


@admin.register(SocialProfile)
class SocialProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'member')
    search_fields = ('display_name', 'member__member_id')
    raw_id_fields = ('member',)


admin.site.register(PostComment)
admin.site.register(PostReport)
admin.site.register(UserBlock)
