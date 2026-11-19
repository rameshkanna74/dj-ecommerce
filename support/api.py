from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.api.permissions import IsPlatformAdmin, is_schema_generation
from orders.models import Order

from . import services
from .models import SupportTicket, TicketMessage


class TicketMessageSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    status_change_display = serializers.CharField(source="get_status_change_display", read_only=True)

    class Meta:
        model = TicketMessage
        fields = ["id", "author", "body", "is_staff_reply", "status_change", "status_change_display", "created_at"]

    def get_author(self, obj) -> str:
        if obj.is_staff_reply:
            return "CoreCart Support"
        return obj.author.display_name if obj.author else "Customer"


class TicketSerializer(serializers.ModelSerializer):
    order = serializers.SlugRelatedField(slug_field="order_number", queryset=Order.objects.none(), required=False,
                                         allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    reply_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = SupportTicket
        fields = ["id", "subject", "message", "order", "status", "status_display", "reply_count", "created_at",
                  "updated_at"]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            # Only the requesting user's own orders can be attached.
            self.fields["order"].queryset = Order.objects.filter(user=request.user)

    def validate_message(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Please describe the issue in at least 10 characters.")
        return value


class TicketDetailSerializer(TicketSerializer):
    messages = TicketMessageSerializer(many=True, read_only=True)

    class Meta(TicketSerializer.Meta):
        fields = TicketSerializer.Meta.fields + ["messages"]


class StaffTicketSerializer(TicketDetailSerializer):
    user = serializers.SerializerMethodField()

    class Meta(TicketDetailSerializer.Meta):
        fields = TicketDetailSerializer.Meta.fields + ["user"]

    def get_user(self, obj) -> dict:
        return {"id": obj.user_id, "username": obj.user.username, "email": obj.user.email, "role": obj.user.role}


class ReplySerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000)


class StaffRespondSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(choices=SupportTicket.Status.choices, required=False, allow_blank=True,
                                     default="")


class TicketViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                    viewsets.GenericViewSet):
    """The signed-in user's support tickets."""

    def get_serializer_class(self):
        return TicketDetailSerializer if self.action == "retrieve" else TicketSerializer

    def get_queryset(self):
        if is_schema_generation(self):
            return SupportTicket.objects.none()
        return (
            SupportTicket.objects.filter(user=self.request.user)
            .select_related("order")
            .prefetch_related("messages__author")
            .annotate(reply_count=Count("messages", filter=Q(messages__is_staff_reply=True)))
            .order_by("-updated_at")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ticket = services.open_ticket(request.user, data["subject"], data["message"], data.get("order"))
        return Response(TicketDetailSerializer(ticket, context=self.get_serializer_context()).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=ReplySerializer, responses={201: TicketMessageSerializer})
    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        ticket = self.get_object()
        serializer = ReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.add_customer_reply(ticket, request.user, serializer.validated_data["body"])
        return Response(TicketMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=TicketDetailSerializer)
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        ticket = services.customer_close(self.get_object(), request.user)
        return Response(TicketDetailSerializer(ticket, context=self.get_serializer_context()).data)


class StaffTicketViewSet(viewsets.ReadOnlyModelViewSet):
    """Support queue for administrators. Filter with ``status`` and ``q``."""

    serializer_class = StaffTicketSerializer
    permission_classes = [IsPlatformAdmin]

    @extend_schema(parameters=[OpenApiParameter("status", str, enum=SupportTicket.Status.values),
                               OpenApiParameter("q", str)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = SupportTicket.objects.select_related("user", "order").prefetch_related("messages__author")
        status_filter = self.request.query_params.get("status")
        if status_filter in SupportTicket.Status.values:
            queryset = queryset.filter(status=status_filter)
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(subject__icontains=query) | Q(user__username__icontains=query) | Q(user__email__icontains=query)
            )
        return queryset.order_by("-updated_at")

    @extend_schema(request=StaffRespondSerializer, responses=StaffTicketSerializer)
    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        ticket = self.get_object()
        serializer = StaffRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.staff_respond(ticket, request.user, serializer.validated_data["body"].strip(),
                               serializer.validated_data["status"])
        return Response(StaffTicketSerializer(self.get_queryset().get(pk=ticket.pk), context={"request": request}).data)
