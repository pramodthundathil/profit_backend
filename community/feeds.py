"""Who sees which posts.

- My gym feed: posts by members of the viewer's gym (gym-only and public ones), if the gym has the feed on.
- ProFit community feed: public posts from every gym that has the community feed on, if the viewer's gym has it on.
- Authors always see their own posts, including ones waiting for approval or hidden by moderators.
- Members who blocked each other never see each other's posts or comments.
"""
from django.db.models import Exists, OuterRef, Q

from member_api.models import MemberAppSettings
from .models import Post, PostLike, UserBlock


def blocked_user_ids(user):
    blocked = UserBlock.objects.filter(blocker=user).values_list('blocked_id', flat=True)
    blockers = UserBlock.objects.filter(blocked=user).values_list('blocker_id', flat=True)
    return set(blocked) | set(blockers)


def _with_details(posts, user):
    return (
        posts.select_related('author__member_profile__social_profile', 'gym')
        .prefetch_related('media')
        .annotate(liked_by_me=Exists(PostLike.objects.filter(post=OuterRef('pk'), user=user)))
    )


def public_scope():
    return Q(visibility=Post.PUBLIC, gym__member_app_settings__public_feed_enabled=True)


def visible_posts(member, app_settings=None):
    """Every post this member may open, in any feed."""
    app_settings = app_settings or MemberAppSettings.for_gym(member.gym)
    user = member.user
    reach = Q(pk__in=[])
    if app_settings.community_feed_enabled:
        reach |= Q(gym=member.gym)
    if app_settings.public_feed_enabled:
        reach |= public_scope()
    posts = (
        Post.objects.filter(reach)
        .filter(Q(status=Post.PUBLISHED, author__is_active=True) | Q(author=user))
        .exclude(author_id__in=blocked_user_ids(user))
    )
    return _with_details(posts, user)


def feed(member, scope, app_settings=None):
    app_settings = app_settings or MemberAppSettings.for_gym(member.gym)
    posts = visible_posts(member, app_settings)
    if scope == Post.PUBLIC:
        return posts.filter(public_scope()) if app_settings.public_feed_enabled else posts.none()
    return posts.filter(gym=member.gym) if app_settings.community_feed_enabled else posts.none()


def page(queryset, before, size=20):
    """Newest first, `size` at a time. Pass the last id you saw as `before` for the next page."""
    if before:
        try:
            queryset = queryset.filter(id__lt=int(before))
        except ValueError:
            pass
    items = list(queryset.order_by('-id')[:size + 1])
    has_more = len(items) > size
    items = items[:size]
    return items, (items[-1].id if has_more and items else None)
