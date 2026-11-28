from django.contrib import admin

from .models import InstructionComment, TrainerInstruction, WorkoutLog


class CommentInline(admin.TabularInline):
    model = InstructionComment
    extra = 0
    raw_id_fields = ('author',)


@admin.register(TrainerInstruction)
class TrainerInstructionAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'member', 'author', 'is_active', 'created_at')
    list_filter = ('kind', 'is_active')
    search_fields = ('title', 'member__member_id', 'member__first_name')
    raw_id_fields = ('member', 'author', 'gym')
    inlines = [CommentInline]


admin.site.register(WorkoutLog)
