"""Trainers and admins: review members' food logs and send them instructions (used by Profit_app)."""
from datetime import timedelta

from django.db.models import Count, Exists, Max, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from foodlog.models import FoodLog, FoodLogFeedback
from training.models import TrainerInstruction, WorkoutLog
from .coaching import (
    FoodLogEnabled, InstructionsEnabled, IsCoach, coached_members, day_summary, parse_date,
)
from .coaching_serializers import (
    CoachedMemberSerializer, CommentSerializer, FoodLogFeedbackSerializer, FoodLogSerializer,
    InstructionDetailSerializer, InstructionSerializer,
)
from .serializers import MemberAppSettingsSerializer
from .models import MemberAppSettings

TAG = 'Coach API'
PAGE_SIZE = 50
REVIEW_WINDOW_DAYS = 7


def annotate_coaching(members):
    since = timezone.localdate() - timedelta(days=REVIEW_WINDOW_DAYS)
    active = TrainerInstruction.objects.filter(member=OuterRef('pk'), is_active=True)
    return members.annotate(
        last_food_log_date=Max('food_logs__log_date'),
        unreviewed_meals=Count(
            'food_logs',
            filter=Q(food_logs__log_date__gte=since, food_logs__feedback__isnull=True),
            distinct=True,
        ),
        has_workout_plan=Exists(active.filter(kind=TrainerInstruction.WORKOUT)),
        has_diet_plan=Exists(active.filter(kind=TrainerInstruction.DIET)),
    ).select_related('user', 'branch')


def get_coached_member(request, pk):
    return get_object_or_404(coached_members(request.user), pk=pk)


class CoachMembersView(APIView):
    """Members to coach: a trainer's assigned members, or all members an admin manages."""
    permission_classes = [IsCoach]

    @swagger_auto_schema(tags=[TAG], operation_description="?search=, ?needs_review=1, ?page=")
    def get(self, request):
        members = annotate_coaching(coached_members(request.user).filter(is_active=True))
        search = request.query_params.get('search', '').strip()
        if search:
            members = members.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
                | Q(member_id__icontains=search) | Q(mobile_number__icontains=search)
            )
        if request.query_params.get('needs_review') in ('1', 'true'):
            members = members.filter(unreviewed_meals__gt=0)
        members = members.order_by('-unreviewed_meals', '-last_food_log_date', 'first_name')

        try:
            page = max(int(request.query_params.get('page', 1)), 1)
        except ValueError:
            page = 1
        total = members.count()
        chunk = members[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
        features = MemberAppSettings.for_gym(request.user.gym)
        return Response({
            'count': total,
            'has_more': page * PAGE_SIZE < total,
            'features': MemberAppSettingsSerializer(features).data,
            'results': CoachedMemberSerializer(chunk, many=True, context={'request': request}).data,
        })


class CoachMemberOverviewView(APIView):
    permission_classes = [IsCoach]

    @swagger_auto_schema(tags=[TAG], operation_description="A member's coaching summary: today's food and active plans")
    def get(self, request, pk):
        member = get_object_or_404(annotate_coaching(coached_members(request.user)), pk=pk)
        active = TrainerInstruction.objects.filter(member=member, is_active=True)
        context = {'request': request}
        workout = active.filter(kind=TrainerInstruction.WORKOUT).first()
        diet = active.filter(kind=TrainerInstruction.DIET).first()
        return Response({
            'member': CoachedMemberSerializer(member, context=context).data,
            'features': MemberAppSettingsSerializer(MemberAppSettings.for_gym(request.user.gym)).data,
            'today': day_summary(member, parse_date(request.query_params.get('date'))),
            'workout': InstructionSerializer(workout, context=context).data if workout else None,
            'diet': InstructionSerializer(diet, context=context).data if diet else None,
        })


class CoachFoodLogsView(APIView):
    permission_classes = [IsCoach, FoodLogEnabled]

    @swagger_auto_schema(tags=[TAG], operation_description="Meals for the 7 days ending ?date= (default today), newest first")
    def get(self, request, pk):
        member = get_coached_member(request, pk)
        end = parse_date(request.query_params.get('date'))
        start = end - timedelta(days=6)
        logs = (
            FoodLog.objects.filter(member=member, log_date__range=(start, end))
            .prefetch_related('photos', 'feedback__author')
            .order_by('-log_date', 'meal_time', 'created_at')
        )
        context = {'request': request}
        days = []
        for offset in range(7):
            day = end - timedelta(days=offset)
            day_logs = [log for log in logs if log.log_date == day]
            days.append({
                'summary': day_summary(member, day),
                'meals': FoodLogSerializer(day_logs, many=True, context=context).data,
            })
        return Response({'start': start.isoformat(), 'end': end.isoformat(), 'days': days})


class CoachFoodLogFeedbackView(APIView):
    permission_classes = [IsCoach, FoodLogEnabled]

    @swagger_auto_schema(tags=[TAG], request_body=FoodLogFeedbackSerializer, operation_description="Review a meal")
    def post(self, request, log_id):
        log = get_object_or_404(FoodLog, pk=log_id, member__in=coached_members(request.user))
        serializer = FoodLogFeedbackSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        feedback = serializer.save(food_log=log, author=request.user)
        return Response(FoodLogFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)


class CoachFeedbackDetailView(APIView):
    permission_classes = [IsCoach, FoodLogEnabled]

    @swagger_auto_schema(tags=[TAG], operation_description="Delete your own feedback")
    def delete(self, request, feedback_id):
        feedback = get_object_or_404(
            FoodLogFeedback, pk=feedback_id, food_log__member__in=coached_members(request.user),
        )
        if feedback.author_id != request.user.id and request.user.role != 'gym_admin':
            return Response({'error': 'You can only delete your own feedback.'}, status=status.HTTP_403_FORBIDDEN)
        feedback.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CoachInstructionListView(APIView):
    permission_classes = [IsCoach, InstructionsEnabled]

    @swagger_auto_schema(tags=[TAG], operation_description="All of a member's instructions, newest first")
    def get(self, request, pk):
        member = get_coached_member(request, pk)
        instructions = TrainerInstruction.objects.filter(member=member).select_related('author').prefetch_related('comments')
        return Response(InstructionSerializer(instructions, many=True, context={'request': request}).data)

    @swagger_auto_schema(tags=[TAG], request_body=InstructionSerializer,
                         operation_description="Send an instruction. A new active workout or diet plan replaces the current one.")
    def post(self, request, pk):
        member = get_coached_member(request, pk)
        serializer = InstructionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instruction = serializer.save(member=member, gym=member.gym, author=request.user)
        return Response(InstructionSerializer(instruction, context={'request': request}).data, status=status.HTTP_201_CREATED)


def get_coached_instruction(request, pk):
    return get_object_or_404(
        TrainerInstruction.objects.select_related('author', 'member'),
        pk=pk, member__in=coached_members(request.user),
    )


class CoachInstructionDetailView(APIView):
    permission_classes = [IsCoach, InstructionsEnabled]

    @swagger_auto_schema(tags=[TAG])
    def get(self, request, pk):
        return Response(InstructionDetailSerializer(get_coached_instruction(request, pk), context={'request': request}).data)

    @swagger_auto_schema(tags=[TAG], request_body=InstructionSerializer)
    def patch(self, request, pk):
        instruction = get_coached_instruction(request, pk)
        serializer = InstructionSerializer(instruction, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(InstructionDetailSerializer(instruction, context={'request': request}).data)

    put = patch

    @swagger_auto_schema(tags=[TAG])
    def delete(self, request, pk):
        get_coached_instruction(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CoachInstructionCommentView(APIView):
    permission_classes = [IsCoach, InstructionsEnabled]

    @swagger_auto_schema(tags=[TAG], request_body=CommentSerializer)
    def post(self, request, pk):
        instruction = get_coached_instruction(request, pk)
        serializer = CommentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(instruction=instruction, author=request.user)
        return Response(CommentSerializer(comment, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CoachWorkoutProgressView(APIView):
    permission_classes = [IsCoach, InstructionsEnabled]

    @swagger_auto_schema(tags=[TAG], operation_description="Exercises ticked per day over the last 14 days")
    def get(self, request, pk):
        instruction = get_coached_instruction(request, pk)
        since = timezone.localdate() - timedelta(days=13)
        logs = WorkoutLog.objects.filter(instruction=instruction, log_date__gte=since).order_by('-log_date')
        return Response([{'date': log.log_date.isoformat(), 'completed': log.completed} for log in logs])
