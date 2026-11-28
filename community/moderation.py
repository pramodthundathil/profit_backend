"""Trainers and admins moderate posts by their gym's members."""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from member_api.coaching import IsCoach
from .feeds import page
from .models import Post, PostComment, PostReport
from .serializers import CommentSerializer, PostSerializer

TAG = 'Coach API - Community'
FILTERS = ('pending', 'reported', 'hidden', 'all')


def gym_posts(user):
    return (
        Post.objects.filter(gym=user.gym)
        .select_related('author__member_profile__social_profile', 'author__member_profile')
        .prefetch_related('media')
        .annotate(open_reports=Count('reports', filter=Q(reports__resolved=False)))
    )


def filtered(user, name):
    posts = gym_posts(user)
    if name == 'pending':
        return posts.filter(status=Post.PENDING)
    if name == 'reported':
        return posts.filter(open_reports__gt=0)
    if name == 'hidden':
        return posts.filter(status=Post.HIDDEN)
    return posts


def moderation_card(post, request):
    """Staff see who really wrote a post, unlike other members."""
    data = PostSerializer(post, context={'request': request}).data
    member = getattr(post.author, 'member_profile', None)
    data['status'] = post.status
    data['hidden_reason'] = post.hidden_reason
    data['member'] = {'id': member.id, 'member_id': member.member_id, 'full_name': member.full_name} if member else None
    data['reports'] = [
        {'reason': r.get_reason_display(), 'details': r.details, 'created_at': r.created_at}
        for r in post.reports.filter(resolved=False)
    ]
    return data


class ModerationQueueView(APIView):
    permission_classes = [IsCoach]

    @swagger_auto_schema(tags=[TAG], operation_description="?filter=pending|reported|hidden|all, ?before=")
    def get(self, request):
        name = request.query_params.get('filter', 'pending')
        if name not in FILTERS:
            name = 'pending'
        posts, next_before = page(filtered(request.user, name), request.query_params.get('before'))
        counts = {key: filtered(request.user, key).count() for key in ('pending', 'reported', 'hidden')}
        return Response({
            'filter': name,
            'counts': counts,
            'results': [moderation_card(post, request) for post in posts],
            'next_before': next_before,
        })


class ModeratePostView(APIView):
    permission_classes = [IsCoach]

    @swagger_auto_schema(tags=[TAG], operation_description="Body: {action: approve|hide|restore|delete|dismiss_reports, reason}")
    def post(self, request, pk):
        post = get_object_or_404(gym_posts(request.user), pk=pk)
        action = request.data.get('action')
        reason = str(request.data.get('reason') or '')[:200]
        if action in ('approve', 'restore', 'dismiss_reports'):
            post.status = Post.PUBLISHED
            post.hidden_reason = ''
            post.save(update_fields=['status', 'hidden_reason', 'updated_at'])
            PostReport.objects.filter(post=post).update(resolved=True)
        elif action == 'hide':
            post.status = Post.HIDDEN
            post.hidden_reason = reason or 'Hidden by the gym team'
            post.save(update_fields=['status', 'hidden_reason', 'updated_at'])
            PostReport.objects.filter(post=post).update(resolved=True)
        elif action == 'delete':
            for media in post.media.all():
                media.delete()
            post.delete()
            return Response({'deleted': True})
        else:
            return Response({'action': ['Choose approve, hide, restore, delete or dismiss_reports.']}, status=status.HTTP_400_BAD_REQUEST)
        post = gym_posts(request.user).get(pk=post.pk)
        return Response(moderation_card(post, request))


class ModerateCommentView(APIView):
    permission_classes = [IsCoach]

    @swagger_auto_schema(tags=[TAG], operation_description="Hide a comment on one of your gym's posts")
    def post(self, request, pk):
        comment = get_object_or_404(PostComment, pk=pk, post__gym=request.user.gym)
        comment.is_hidden = True
        comment.save(update_fields=['is_hidden'])
        return Response({'hidden': True})
