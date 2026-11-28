"""Member app: the gym and ProFit community feeds."""
from django.db import IntegrityError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from member_api.coaching import FEATURE_DISABLED, compress_photo
from member_api.models import MemberAppSettings
from member_api.permissions import IsAppMember
from .feeds import blocked_user_ids, feed, page, visible_posts
from .models import Post, PostComment, PostLike, PostMedia, PostReport, SocialProfile, UserBlock
from .serializers import (
    CommentSerializer, PostSerializer, ReportSerializer, SocialProfileSerializer, SocialProfileUpdateSerializer,
)

TAG = 'Member App - Community'


class CommunityEnabled(BasePermission):
    def has_permission(self, request, view):
        app_settings = MemberAppSettings.for_gym(request.member.gym)
        if not (app_settings.community_feed_enabled or app_settings.public_feed_enabled):
            raise PermissionDenied({'code': FEATURE_DISABLED, 'detail': 'The community feed is turned off for this gym.'})
        request.app_settings = app_settings
        return True


class CommunityView(APIView):
    permission_classes = [IsAppMember, CommunityEnabled]

    def context(self):
        return {'request': self.request}

    def get_post(self, pk):
        return get_object_or_404(visible_posts(self.request.member, self.request.app_settings), pk=pk)


class FeedView(CommunityView):
    @swagger_auto_schema(tags=[TAG], operation_description="?scope=gym|public, ?before=<last post id> for the next page")
    def get(self, request):
        scope = request.query_params.get('scope', Post.GYM)
        if scope not in (Post.GYM, Post.PUBLIC):
            scope = Post.GYM
        posts, next_before = page(feed(request.member, scope, request.app_settings), request.query_params.get('before'))
        return Response({
            'scope': scope,
            'results': PostSerializer(posts, many=True, context=self.context()).data,
            'next_before': next_before,
        })


class PostCreateView(CommunityView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'community_post'

    @swagger_auto_schema(tags=[TAG], operation_description="Multipart: text, visibility (gym|public), kind, up to 4 `photos`")
    def post(self, request):
        serializer = PostSerializer(data=request.data, context=self.context())
        serializer.is_valid(raise_exception=True)
        app_settings = request.app_settings
        visibility = serializer.validated_data.get('visibility', Post.GYM)
        if visibility == Post.PUBLIC and not app_settings.public_feed_enabled:
            return Response({'visibility': ['Your gym has not turned on the ProFit community feed.']}, status=status.HTTP_400_BAD_REQUEST)
        if visibility == Post.GYM and not app_settings.community_feed_enabled:
            return Response({'visibility': ['Your gym has not turned on the gym feed.']}, status=status.HTTP_400_BAD_REQUEST)

        photos = serializer.validated_data.pop('_photos', [])
        with transaction.atomic():
            post = serializer.save(
                author=request.user,
                gym=request.member.gym,
                status=Post.PENDING if app_settings.require_post_approval else Post.PUBLISHED,
            )
            for order, content in enumerate(photos):
                media = PostMedia(post=post, order=order)
                media.image.save(content.name, content, save=True)
        SocialProfile.for_member(request.member)
        post = visible_posts(request.member, app_settings).get(pk=post.pk)
        return Response(PostSerializer(post, context=self.context()).data, status=status.HTTP_201_CREATED)


class PostDetailView(CommunityView):
    @swagger_auto_schema(tags=[TAG], operation_description="A post with its latest 100 comments")
    def get(self, request, pk):
        post = self.get_post(pk)
        comments = (
            post.comments.filter(is_hidden=False)
            .exclude(author_id__in=blocked_user_ids(request.user))
            .select_related('author__member_profile__social_profile', 'post')
            .order_by('-id')[:100]
        )
        data = PostSerializer(post, context=self.context()).data
        data['comments'] = CommentSerializer(reversed(list(comments)), many=True, context=self.context()).data
        return Response(data)

    @swagger_auto_schema(tags=[TAG], operation_description="Delete your own post")
    def delete(self, request, pk):
        post = get_object_or_404(Post, pk=pk, author=request.user)
        for media in post.media.all():
            media.delete()
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostLikeView(CommunityView):
    @swagger_auto_schema(tags=[TAG], operation_description="Like a post")
    def post(self, request, pk):
        post = self.get_post(pk)
        try:
            with transaction.atomic():
                PostLike.objects.create(post=post, user=request.user)
                Post.objects.filter(pk=post.pk).update(like_count=F('like_count') + 1)
        except IntegrityError:
            pass  # already liked
        post.refresh_from_db(fields=['like_count'])
        return Response({'liked': True, 'like_count': post.like_count})

    @swagger_auto_schema(tags=[TAG], operation_description="Remove your like")
    def delete(self, request, pk):
        post = self.get_post(pk)
        deleted, _ = PostLike.objects.filter(post=post, user=request.user).delete()
        if deleted:
            Post.objects.filter(pk=post.pk, like_count__gt=0).update(like_count=F('like_count') - 1)
        post.refresh_from_db(fields=['like_count'])
        return Response({'liked': False, 'like_count': post.like_count})


class PostCommentView(CommunityView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'community_comment'

    @swagger_auto_schema(tags=[TAG], request_body=CommentSerializer)
    def post(self, request, pk):
        post = self.get_post(pk)
        if post.status != Post.PUBLISHED:
            return Response({'error': 'This post is not published yet.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CommentSerializer(data=request.data, context=self.context())
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            comment = serializer.save(post=post, author=request.user)
            Post.objects.filter(pk=post.pk).update(comment_count=F('comment_count') + 1)
        return Response(CommentSerializer(comment, context=self.context()).data, status=status.HTTP_201_CREATED)


class CommentDeleteView(CommunityView):
    @swagger_auto_schema(tags=[TAG], operation_description="Delete your comment, or a comment on your post")
    def delete(self, request, pk):
        comment = get_object_or_404(PostComment.objects.select_related('post'), pk=pk)
        if request.user.id not in (comment.author_id, comment.post.author_id):
            return Response({'error': 'You can only delete your own comments.'}, status=status.HTTP_403_FORBIDDEN)
        with transaction.atomic():
            comment.delete()
            Post.objects.filter(pk=comment.post_id, comment_count__gt=0).update(comment_count=F('comment_count') - 1)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostReportView(CommunityView):
    @swagger_auto_schema(tags=[TAG], request_body=ReportSerializer,
                         operation_description="Report a post. After 3 reports it is hidden until a moderator reviews it.")
    def post(self, request, pk):
        post = self.get_post(pk)
        if post.author_id == request.user.id:
            return Response({'error': "You can't report your own post."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save(post=post, reporter=request.user)
                Post.objects.filter(pk=post.pk).update(report_count=F('report_count') + 1)
                Post.objects.filter(
                    pk=post.pk, status=Post.PUBLISHED, report_count__gte=Post.AUTO_HIDE_REPORTS,
                ).update(status=Post.HIDDEN, hidden_reason='Hidden after several reports')
        except IntegrityError:
            pass  # already reported
        return Response({'message': "Thanks. The gym's team will review this post."})


class MyProfileView(CommunityView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def payload(self, profile):
        count = Post.objects.filter(author=self.request.user).count()
        return SocialProfileSerializer(profile, context={**self.context(), 'post_count': count}).data

    @swagger_auto_schema(tags=[TAG], operation_description="Your display name, bio and avatar")
    def get(self, request):
        return Response(self.payload(SocialProfile.for_member(request.member)))

    @swagger_auto_schema(tags=[TAG], request_body=SocialProfileUpdateSerializer,
                         operation_description="Change display name or bio; multipart `avatar` file or remove_avatar=true")
    def patch(self, request):
        profile = SocialProfile.for_member(request.member)
        serializer = SocialProfileUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        remove = serializer.validated_data.pop('remove_avatar', False)
        upload = request.FILES.get('avatar')
        content = compress_photo(upload) if upload else None
        serializer.save()
        if (remove or content) and profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None
        if content:
            profile.avatar.save(content.name, content, save=False)
        profile.save()
        return Response(self.payload(profile))


def _profile_user(profile):
    member = profile.member
    return member.user if member.user_id else None


class ProfileView(CommunityView):
    @swagger_auto_schema(tags=[TAG], operation_description="Another member's profile and the posts you may see (?before= for more)")
    def get(self, request, pk):
        profile = get_object_or_404(SocialProfile.objects.select_related('member__user'), pk=pk)
        user = _profile_user(profile)
        if user is None or UserBlock.objects.filter(blocker=user, blocked=request.user).exists():
            return Response({'error': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        i_blocked = UserBlock.objects.filter(blocker=request.user, blocked=user).exists()
        posts_qs = visible_posts(request.member, request.app_settings).filter(author=user)
        # Members of other gyms are only visible through their public posts (or so you can unblock them).
        if profile.member.gym_id != request.member.gym_id and not i_blocked and not posts_qs.exists():
            return Response({'error': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        posts, next_before = page(posts_qs, request.query_params.get('before'))
        data = SocialProfileSerializer(profile, context={**self.context(), 'post_count': posts_qs.count()}).data
        data['is_me'] = user.id == request.user.id
        data['blocked'] = i_blocked
        data['posts'] = PostSerializer(posts, many=True, context=self.context()).data
        data['next_before'] = next_before
        return Response(data)


class BlockView(CommunityView):
    @swagger_auto_schema(tags=[TAG], operation_description="Block a member: you stop seeing each other's posts and comments")
    def post(self, request, pk):
        profile = get_object_or_404(SocialProfile.objects.select_related('member__user'), pk=pk)
        user = _profile_user(profile)
        if user is None or user.id == request.user.id:
            return Response({'error': "You can't block this member."}, status=status.HTTP_400_BAD_REQUEST)
        UserBlock.objects.get_or_create(blocker=request.user, blocked=user)
        return Response({'blocked': True})

    @swagger_auto_schema(tags=[TAG], operation_description="Unblock a member")
    def delete(self, request, pk):
        profile = get_object_or_404(SocialProfile.objects.select_related('member__user'), pk=pk)
        UserBlock.objects.filter(blocker=request.user, blocked=_profile_user(profile)).delete()
        return Response({'blocked': False})
