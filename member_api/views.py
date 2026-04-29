from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate
import random
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import EmailOTP
from home.models import CustomUser
from members.models import Member
from .serializers import (
    SendOTPSerializer, VerifyOTPSerializer, 
    EmailPasswordLoginSerializer, SetPasswordSerializer,
    MemberProfileSerializer
)

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

class SendEmailOTPView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['Member App API'],
        operation_description="Send OTP to member's email",
        request_body=SendOTPSerializer,
        responses={200: "OTP sent successfully", 400: "Bad Request", 404: "Member not found"}
    )
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            # Check if member exists with this email
            if not Member.objects.filter(email=email).exists():
                return Response({"error": "No member found with this email."}, status=status.HTTP_404_NOT_FOUND)

            # Generate 6-digit OTP
            otp_code = str(random.randint(100000, 999999))
            
            # Save OTP
            EmailOTP.objects.create(email=email, otp=otp_code)
            
            # Send Email
            try:
                send_mail(
                    'Your Gym Login OTP',
                    f'Your OTP for login is {otp_code}. It is valid for 10 minutes.',
                    settings.EMAIL_HOST_USER,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Error sending email: {e}")
                # For development fallback if email fails
                print(f"OTP for {email} is {otp_code}")

            return Response({"message": "OTP sent successfully to your email."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailOTPView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['Member App API'],
        operation_description="Verify OTP and Login",
        request_body=VerifyOTPSerializer,
        responses={200: "Login successful", 400: "Invalid OTP", 404: "Member not found"}
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp = serializer.validated_data['otp']
            
            # Verify OTP
            otp_obj = EmailOTP.objects.filter(email=email, otp=otp).order_by('-created_at').first()
            if not otp_obj or not otp_obj.is_valid():
                return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)
            
            otp_obj.is_verified = True
            otp_obj.save()
            
            # Find Member
            member = Member.objects.filter(email=email).first()
            if not member:
                return Response({"error": "Member not found."}, status=status.HTTP_404_NOT_FOUND)
            
            # Find or Create CustomUser
            user = CustomUser.objects.filter(email=email).first()
            if not user:
                import secrets
                user = CustomUser.objects.create_user(
                    email=email,
                    password=secrets.token_urlsafe(12),
                    role='member',
                    gym=member.gym,
                    phone_number=member.mobile_number,
                    username=f"member_{member.member_id}"
                )
            
            # Link user to member if not already linked
            if not hasattr(member, 'user') or member.user != user:
                member.user = user
                member.save()

            tokens = get_tokens_for_user(user)
            return Response({
                "message": "Login successful.",
                "tokens": tokens,
                "is_password_set": user.has_usable_password() # If they want to prompt for setting password
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailPasswordLoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['Member App API'],
        operation_description="Login with Email and Password",
        request_body=EmailPasswordLoginSerializer,
        responses={200: "Login successful", 401: "Invalid credentials", 403: "Not a member account"}
    )
    def post(self, request):
        serializer = EmailPasswordLoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            user = authenticate(request, username=email, password=password)
            if user is not None:
                if user.role != 'member':
                    return Response({"error": "Not a member account."}, status=status.HTTP_403_FORBIDDEN)
                
                tokens = get_tokens_for_user(user)
                return Response({
                    "message": "Login successful.",
                    "tokens": tokens
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SetPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['Member App API'],
        operation_description="Set new password for authenticated member",
        request_body=SetPasswordSerializer,
        responses={200: "Password set successfully", 400: "Bad Request", 403: "Forbidden"}
    )
    def post(self, request):
        if request.user.role != 'member':
            return Response({"error": "Only members can use this API."}, status=status.HTTP_403_FORBIDDEN)

        serializer = SetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['password'])
            user.save()
            return Response({"message": "Password set successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MemberProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['Member App API'],
        operation_description="Get authenticated member profile",
        responses={200: MemberProfileSerializer, 403: "Forbidden", 404: "Profile not found"}
    )
    def get(self, request):
        user = request.user
        if user.role != 'member':
            return Response({"error": "Only members can access this profile."}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            member = user.member_profile
        except Member.DoesNotExist:
            return Response({"error": "Member profile not found for this user."}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = MemberProfileSerializer(member)
        return Response(serializer.data, status=status.HTTP_200_OK)
