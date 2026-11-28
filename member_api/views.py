import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.core.mail import send_mail
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from members.models import Member
from .models import EmailOTP, MemberAppAccount, MemberAppSettings
from .permissions import IsAppMember, MEMBER_APP_DISABLED
from .serializers import (
    LogoutSerializer, MemberAppSettingsSerializer, MemberLoginSerializer, MemberProfileSerializer,
    MemberSummarySerializer, SendOTPSerializer, SetPasswordSerializer, VerifyOTPSerializer,
)
from .services import _revoke_sessions, get_account, validate_new_password

logger = logging.getLogger(__name__)

TAG = 'Member App API'
OTP_RESEND_INTERVAL = timedelta(seconds=60)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


def _login_member_by_email(email):
    """The member whose app login uses this email, if any."""
    return (
        Member.objects.select_related('user', 'gym', 'branch')
        .filter(user__isnull=False, user__role='member', user__email__iexact=email.strip())
        .first()
    )


def _login_member(identifier):
    if '@' in identifier:
        return _login_member_by_email(identifier)
    return (
        Member.objects.select_related('user', 'gym', 'branch')
        .filter(user__isnull=False, user__role='member', member_id__iexact=identifier)
        .first()
    )


def _session_response(request, member, message):
    account = get_account(member)
    update_last_login(None, member.user)
    return Response({
        'message': message,
        'tokens': get_tokens_for_user(member.user),
        'must_change_password': account.must_change_password,
        'member': MemberSummarySerializer(member, context={'request': request}).data,
    })


def _disabled_response():
    return Response(
        {'code': MEMBER_APP_DISABLED, 'error': 'Your gym has turned off the member app. Contact your gym for help.'},
        status=status.HTTP_403_FORBIDDEN,
    )


class EmailPasswordLoginView(APIView):
    """Sign in with Member ID or email and password."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'member_auth'

    @swagger_auto_schema(
        tags=[TAG],
        operation_description="Sign in with Member ID or email and password. "
                              "If must_change_password is true, the app must call auth/change-password/ next.",
        request_body=MemberLoginSerializer,
        responses={200: "Signed in", 401: "Wrong credentials", 403: "Login turned off"},
    )
    def post(self, request):
        serializer = MemberLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = _login_member(serializer.validated_data['identifier'])

        if member is None or not member.user.check_password(serializer.validated_data['password']):
            return Response({'error': 'Wrong Member ID, email or password.'}, status=status.HTTP_401_UNAUTHORIZED)
        if not member.user.is_active:
            return Response(
                {'error': 'Your app login has been turned off. Contact your gym for help.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not MemberAppSettings.for_gym(member.gym).member_login_enabled:
            return _disabled_response()
        return _session_response(request, member, 'Signed in.')


class SendEmailOTPView(APIView):
    """Start a password reset by emailing a one-time code."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'member_otp'

    @swagger_auto_schema(
        tags=[TAG],
        operation_description="Email a 6-digit code for resetting the password. "
                              "The response is the same whether or not the email has an account.",
        request_body=SendOTPSerializer,
        responses={200: "Code sent if the account exists"},
    )
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].strip().lower()
        reply = Response({'message': 'If this email has a ProFit member login, a code has been sent to it.'})

        member = _login_member_by_email(email)
        if (
            member is None
            or not member.user.is_active
            or not MemberAppSettings.for_gym(member.gym).member_login_enabled
        ):
            return reply

        recent = EmailOTP.objects.filter(email=email, created_at__gte=timezone.now() - OTP_RESEND_INTERVAL)
        if recent.exists():
            return reply

        EmailOTP.objects.filter(email=email, is_verified=False).delete()
        code = f"{secrets.randbelow(1_000_000):06d}"
        EmailOTP.objects.create(email=email, otp=code)
        try:
            send_mail(
                f'{member.gym.name} app password reset code',
                f'Your code is {code}. It is valid for 10 minutes.\n\n'
                'If you did not ask to reset your password, you can ignore this email.',
                settings.DEFAULT_FROM_EMAIL,
                [member.user.email],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Could not send member OTP email for member %s", member.pk)
        return reply


class VerifyEmailOTPView(APIView):
    """Exchange the emailed code for a session that must set a new password."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'member_auth'

    @swagger_auto_schema(
        tags=[TAG],
        operation_description="Verify the emailed code. The member is signed in with must_change_password set.",
        request_body=VerifyOTPSerializer,
        responses={200: "Signed in", 400: "Wrong or expired code"},
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].strip().lower()
        code = serializer.validated_data['otp'].strip()

        otp = EmailOTP.objects.filter(email=email, is_verified=False).order_by('-created_at').first()
        if otp is None or not otp.is_valid():
            return Response({'error': 'This code has expired. Ask for a new one.'}, status=status.HTTP_400_BAD_REQUEST)
        if not secrets.compare_digest(otp.otp, code):
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            return Response({'error': 'Wrong code.'}, status=status.HTTP_400_BAD_REQUEST)

        otp.is_verified = True
        otp.save(update_fields=['is_verified'])

        member = _login_member_by_email(email)
        if member is None or not member.user.is_active:
            return Response({'error': 'This code has expired. Ask for a new one.'}, status=status.HTTP_400_BAD_REQUEST)
        if not MemberAppSettings.for_gym(member.gym).member_login_enabled:
            return _disabled_response()

        account = get_account(member)
        account.must_change_password = True
        account.save(update_fields=['must_change_password'])
        return _session_response(request, member, 'Code verified. Set a new password.')


class SetPasswordView(APIView):
    """Replace the password. The current one is not needed while a change is required."""
    permission_classes = [IsAppMember]
    allow_pending_password = True

    @swagger_auto_schema(
        tags=[TAG],
        operation_description="Set a new password. current_password is required unless must_change_password is true. "
                              "Other sessions are signed out and new tokens are returned.",
        request_body=SetPasswordSerializer,
        responses={200: "Password changed", 400: "Bad Request"},
    )
    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        account = get_account(request.member)

        if not account.must_change_password and not user.check_password(
            serializer.validated_data.get('current_password') or ''
        ):
            return Response({'current_password': ['Current password is wrong.']}, status=status.HTTP_400_BAD_REQUEST)

        password = serializer.validated_data['password']
        error = validate_new_password(user, password)
        if error:
            return Response({'password': [error]}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save()
        MemberAppAccount.objects.filter(pk=account.pk).update(
            must_change_password=False, password_changed_at=timezone.now()
        )
        _revoke_sessions(user)
        return Response({'message': 'Password changed.', 'tokens': get_tokens_for_user(user)})


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @swagger_auto_schema(tags=[TAG], request_body=LogoutSerializer, responses={205: "Signed out"})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data['refresh']).blacklist()
        except TokenError:
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MemberAppConfigView(APIView):
    """Everything the app needs at start-up: who is signed in and which features are on."""
    permission_classes = [IsAppMember]
    allow_pending_password = True

    @swagger_auto_schema(tags=[TAG], operation_description="Signed-in member, password state and gym feature switches.")
    def get(self, request):
        member = request.member
        return Response({
            'member': MemberSummarySerializer(member, context={'request': request}).data,
            'must_change_password': get_account(member).must_change_password,
            'features': MemberAppSettingsSerializer(MemberAppSettings.for_gym(member.gym)).data,
            'trainer': _trainer_card(member),
            'membership': _membership_card(member),
            'social_profile': _social_card(member, request),
        })


def _trainer_card(member):
    trainer = member.assigned_trainer
    if trainer is None or not trainer.is_active:
        return None
    return {
        'name': trainer.username or trainer.email.split('@')[0],
        'phone': trainer.phone_number or None,
        'email': trainer.email,
        'branch_name': trainer.branch.name if trainer.branch_id else None,
    }


def _membership_card(member):
    current = member.current_subscription
    end = current.end_date if current else member.access_expiry_date
    days_left = (end - timezone.localdate()).days if end else None
    return {
        'status': member.membership_status,
        'plan_name': (current.subscription_type.name if current and current.subscription_type_id else None) if current else None,
        'end_date': end.isoformat() if end else None,
        'days_left': max(days_left, 0) if days_left is not None else None,
        'access_enabled': member.access_enabled,
    }


def _social_card(member, request):
    from community.models import SocialProfile
    profile = SocialProfile.for_member(member)
    return {
        'id': profile.pk,
        'display_name': profile.display_name,
        'avatar': request.build_absolute_uri(profile.avatar.url) if profile.avatar else None,
    }


class MemberProfileView(APIView):
    permission_classes = [IsAppMember]

    @swagger_auto_schema(
        tags=[TAG],
        operation_description="Get authenticated member profile",
        responses={200: MemberProfileSerializer},
    )
    def get(self, request):
        return Response(MemberProfileSerializer(request.member, context={'request': request}).data)
