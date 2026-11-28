"""Staff-side member app APIs: gym feature switches and member logins (used by Profit_app)."""
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from members.models import Member
from .models import MemberAppSettings
from .permissions import IsGymAdmin, IsGymStaff, can_manage_member
from .serializers import BulkEnableSerializer, MemberAppSettingsSerializer
from . import services

TAG = 'Member App Admin API'


def _managed_members(user):
    members = Member.objects.filter(gym=user.gym)
    if user.role in ('branch_admin', 'staff') and user.branch_id:
        members = members.filter(branch_id=user.branch_id)
    return members


class MemberAppSettingsView(APIView):
    """Read (staff) or change (gym admin) the gym's member app switches."""

    def get_permissions(self):
        return [IsGymAdmin()] if self.request.method in ('PATCH', 'PUT') else [IsGymStaff()]

    @swagger_auto_schema(tags=[TAG], responses={200: MemberAppSettingsSerializer})
    def get(self, request):
        settings_obj = MemberAppSettings.for_gym(request.user.gym)
        data = MemberAppSettingsSerializer(settings_obj).data
        data['eligible_for_login'] = services.eligible_for_bulk_enable(_managed_members(request.user)).count()
        return Response(data)

    @swagger_auto_schema(tags=[TAG], request_body=MemberAppSettingsSerializer, responses={200: MemberAppSettingsSerializer})
    def patch(self, request):
        settings_obj = MemberAppSettings.for_gym(request.user.gym)
        serializer = MemberAppSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    put = patch


class _MemberLoginView(APIView):
    permission_classes = [IsGymStaff]

    def get_member(self, request, pk):
        member = get_object_or_404(Member.objects.select_related('gym', 'branch', 'user'), pk=pk, gym=request.user.gym)
        if not can_manage_member(request.user, member):
            return None
        return member

    def run(self, request, pk, action):
        member = self.get_member(request, pk)
        if member is None:
            return Response({'error': 'You can only manage members of your branch.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            message = action(member)
        except services.MemberLoginError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        member.refresh_from_db()
        return Response({'message': message, 'login': services.login_status(member)})


def _send_message(member, credentials):
    if services.send_credentials(credentials):
        return f"Login details sent to {member.email}."
    return (
        "Login is ready, but the email could not be sent. "
        "Check the email settings and use 'Resend credentials'."
    )


class MemberLoginStatusView(_MemberLoginView):
    @swagger_auto_schema(tags=[TAG], operation_description="App login state of a member")
    def get(self, request, pk):
        member = self.get_member(request, pk)
        if member is None:
            return Response({'error': 'You can only manage members of your branch.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(services.login_status(member))


class MemberEnableLoginView(_MemberLoginView):
    @swagger_auto_schema(tags=[TAG], operation_description="Enable app login and email the member their Member ID, username and a temporary password")
    def post(self, request, pk):
        return self.run(request, pk, lambda m: _send_message(m, services.enable_login(m, request.user)))


class MemberResendCredentialsView(_MemberLoginView):
    @swagger_auto_schema(tags=[TAG], operation_description="Email the member a new temporary password")
    def post(self, request, pk):
        return self.run(request, pk, lambda m: _send_message(m, services.reset_credentials(m, request.user)))


class MemberDisableLoginView(_MemberLoginView):
    @swagger_auto_schema(tags=[TAG], operation_description="Turn off app login and sign the member out everywhere")
    def post(self, request, pk):
        def disable(member):
            services.disable_login(member)
            return "App login turned off."
        return self.run(request, pk, disable)


class BulkEnableLoginView(APIView):
    permission_classes = [IsGymStaff]

    @swagger_auto_schema(
        tags=[TAG],
        operation_description="Enable login for chosen members, or all members with an email and no login. "
                              "Emails are sent in the background.",
        request_body=BulkEnableSerializer,
    )
    def post(self, request):
        if request.user.role == 'staff':
            return Response({'error': 'Only admins can enable logins in bulk.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = BulkEnableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not MemberAppSettings.for_gym(request.user.gym).member_login_enabled:
            return Response(
                {'error': 'Member app login is turned off for this gym. Turn it on first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        members = _managed_members(request.user)
        if not serializer.validated_data['all_eligible']:
            members = members.filter(pk__in=serializer.validated_data['member_ids'])
        result = services.bulk_enable(members, request.user)
        result['message'] = f"Login enabled for {result['enabled']} members. Their emails are being sent."
        return Response(result)
