"""Member app: the member's own food log and the instructions their trainer sent."""
from datetime import timedelta

from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from foodlog.models import FoodLog, FoodLogFeedback
from training.models import TrainerInstruction, WorkoutLog
from .coaching import FoodLogEnabled, InstructionsEnabled, day_summary, exercise_ids, parse_date
from .coaching_serializers import (
    CommentSerializer, FoodLogSerializer, InstructionDetailSerializer, InstructionSerializer,
)
from .permissions import IsAppMember

TAG = 'Member App - Coaching'


def _logs(member):
    return FoodLog.objects.filter(member=member).prefetch_related('photos', 'feedback__author')


class MemberFoodLogListView(APIView):
    permission_classes = [IsAppMember, FoodLogEnabled]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @swagger_auto_schema(tags=[TAG], operation_description="Meals on ?date=YYYY-MM-DD (default today)")
    def get(self, request):
        day = parse_date(request.query_params.get('date'))
        logs = _logs(request.member).filter(log_date=day)
        # Opening the day counts as reading the trainer's feedback on it.
        FoodLogFeedback.objects.filter(food_log__in=logs, seen_by_member=False).update(seen_by_member=True)
        return Response({
            'summary': day_summary(request.member, day),
            'results': FoodLogSerializer(logs, many=True, context={'request': request}).data,
        })

    @swagger_auto_schema(tags=[TAG], operation_description="Log a meal. Multipart, with up to 4 `photos` files.")
    def post(self, request):
        serializer = FoodLogSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        log = serializer.save(member=request.member, gym=request.member.gym)
        return Response(FoodLogSerializer(log, context={'request': request}).data, status=status.HTTP_201_CREATED)


class MemberFoodLogDetailView(APIView):
    permission_classes = [IsAppMember, FoodLogEnabled]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_log(self, request, pk):
        return get_object_or_404(_logs(request.member), pk=pk)

    @swagger_auto_schema(tags=[TAG])
    def get(self, request, pk):
        return Response(FoodLogSerializer(self.get_log(request, pk), context={'request': request}).data)

    @swagger_auto_schema(tags=[TAG], operation_description="Edit a meal; add `photos` files or send remove_photo_ids")
    def patch(self, request, pk):
        serializer = FoodLogSerializer(self.get_log(request, pk), data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        log = serializer.save()
        return Response(FoodLogSerializer(_logs(request.member).get(pk=log.pk), context={'request': request}).data)

    @swagger_auto_schema(tags=[TAG])
    def delete(self, request, pk):
        log = self.get_log(request, pk)
        for photo in log.photos.all():
            photo.delete()
        log.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemberFoodHistoryView(APIView):
    """Daily totals for a range of days, for a week strip or chart."""
    permission_classes = [IsAppMember, FoodLogEnabled]

    @swagger_auto_schema(tags=[TAG], operation_description="Totals for the 7 days ending ?date= (default today)")
    def get(self, request):
        end = parse_date(request.query_params.get('date'))
        days = [end - timedelta(days=offset) for offset in range(6, -1, -1)]
        return Response({'days': [day_summary(request.member, day) for day in days]})


class MemberInstructionsView(APIView):
    permission_classes = [IsAppMember, InstructionsEnabled]

    @swagger_auto_schema(tags=[TAG], operation_description="Active workout plan, active diet plan and recent notes")
    def get(self, request):
        instructions = TrainerInstruction.objects.filter(member=request.member, is_active=True).select_related('author')
        context = {'request': request}
        workout = instructions.filter(kind=TrainerInstruction.WORKOUT).first()
        diet = instructions.filter(kind=TrainerInstruction.DIET).first()
        notes = instructions.filter(kind=TrainerInstruction.NOTE)[:20]
        return Response({
            'workout': InstructionSerializer(workout, context=context).data if workout else None,
            'diet': InstructionSerializer(diet, context=context).data if diet else None,
            'notes': InstructionSerializer(notes, many=True, context=context).data,
        })


def _member_instruction(request, pk):
    return get_object_or_404(TrainerInstruction.objects.select_related('author'), pk=pk, member=request.member)


class MemberInstructionDetailView(APIView):
    permission_classes = [IsAppMember, InstructionsEnabled]

    @swagger_auto_schema(tags=[TAG])
    def get(self, request, pk):
        return Response(InstructionDetailSerializer(_member_instruction(request, pk), context={'request': request}).data)


class MemberInstructionCommentView(APIView):
    permission_classes = [IsAppMember, InstructionsEnabled]

    @swagger_auto_schema(tags=[TAG], request_body=CommentSerializer, operation_description="Reply to the trainer")
    def post(self, request, pk):
        instruction = _member_instruction(request, pk)
        serializer = CommentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(instruction=instruction, author=request.user)
        return Response(CommentSerializer(comment, context={'request': request}).data, status=status.HTTP_201_CREATED)


class MemberWorkoutLogView(APIView):
    """Exercises the member ticked off on a day."""
    permission_classes = [IsAppMember, InstructionsEnabled]

    def get_workout(self, request, pk):
        return get_object_or_404(TrainerInstruction, pk=pk, member=request.member, kind=TrainerInstruction.WORKOUT)

    @swagger_auto_schema(tags=[TAG], operation_description="Ticked exercise ids on ?date=")
    def get(self, request, pk):
        workout = self.get_workout(request, pk)
        day = parse_date(request.query_params.get('date'))
        log = WorkoutLog.objects.filter(instruction=workout, log_date=day).first()
        return Response({'date': day.isoformat(), 'completed': log.completed if log else []})

    @swagger_auto_schema(tags=[TAG], operation_description="Body: {date, completed: [exercise ids]}")
    def put(self, request, pk):
        workout = self.get_workout(request, pk)
        day = parse_date(request.data.get('date'))
        completed = request.data.get('completed')
        if not isinstance(completed, list):
            return Response({'completed': ['Send a list of exercise ids.']}, status=status.HTTP_400_BAD_REQUEST)
        valid = exercise_ids(workout)
        completed = [str(item) for item in dict.fromkeys(completed) if str(item) in valid]
        log, _ = WorkoutLog.objects.update_or_create(
            instruction=workout, log_date=day, defaults={'completed': completed},
        )
        return Response({'date': day.isoformat(), 'completed': log.completed})
