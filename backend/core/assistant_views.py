import re
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, serializers as s, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .assistant_intents import (
    INJECTION, PERIOD_READ_ACTIONS, QUANTITY, ProviderUnavailable, active_provider, local_intent,
    period_followup, provider_intent, quantity_value,
)
from .assistant_proposals import PROPOSAL_LIFETIME, change_proposal, clarification_value, parse_proposal, prepare
from .assistant_tools import local_day, response, run_read_tool
from .finance_views import validated
from .models import AssistantConversation, AssistantExchange, AssistantProposal, Membership
from .reporting import as_json
from .views import TenantMixin

PROPOSAL_ACTIONS = {*AssistantProposal.Kind.values, "restock"}
CONTEXT_KEYS = ("followup", "report_intent", "conversation_intent")
QUANTITY_EDIT = re.compile(rf"(?:please\s+)?(?:make it|change (?:it|the quantity) to|set (?:it|the quantity) to)\s+({QUANTITY})(?:\s+instead)?", re.I)


class ConversationSerializer(s.ModelSerializer):
    class Meta:
        model = AssistantConversation
        fields = ["id", "title", "created_at", "updated_at"]
        read_only_fields = fields


class MessageInput(s.Serializer):
    request_id = s.UUIDField()
    text = s.CharField(max_length=2000)


class RevisionInput(s.Serializer):
    revision = s.IntegerField(min_value=1)


class EditInput(RevisionInput):
    payload = s.DictField()


def proposal_data(proposal):
    if not proposal:
        return None
    status = proposal.status
    if status == "pending" and proposal.expires_at <= timezone.now():
        status = "expired"
    return {"id": proposal.pk, "kind": proposal.kind, "status": status, "revision": proposal.revision,
            "expires_at": proposal.expires_at.isoformat(), "payload": proposal.payload, "preview": proposal.preview,
            "result": proposal.result}


class ExchangeSerializer(s.ModelSerializer):
    answer = s.SerializerMethodField()
    proposal = s.SerializerMethodField()

    class Meta:
        model = AssistantExchange
        fields = ["id", "request_id", "prompt", "answer", "proposal", "created_at"]

    @extend_schema(responses=dict)
    def get_answer(self, exchange) -> dict:
        return {key: value for key, value in exchange.answer.items() if key not in CONTEXT_KEYS}

    def get_proposal(self, exchange) -> dict | None:
        return proposal_data(getattr(exchange, "proposal", None))


def validation_text(detail):
    if isinstance(detail, dict):
        return " ".join(validation_text(value) for value in detail.values())
    if isinstance(detail, list):
        return " ".join(validation_text(value) for value in detail)
    return str(detail)


class AssistantStatus(TenantMixin, APIView):
    @extend_schema(responses={200: dict})
    def get(self, request, business_id):
        enabled = active_provider()
        return Response({"provider_enabled": enabled, "provider": settings.ASSISTANT_PROVIDER if enabled else None,
                         "voice_provider": settings.VOICE_PROVIDER})


class Conversations(TenantMixin, mixins.ListModelMixin, mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AssistantConversation.objects.all()
    serializer_class = ConversationSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["title"]
    # Transaction tools check their own narrower roles.
    write_roles = Membership.Role.values

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    @extend_schema(request=None, responses={201: ConversationSerializer})
    def create(self, request, business_id):
        conversation = AssistantConversation.objects.create(business=self.business, user=request.user)
        return Response(self.get_serializer(conversation).data, status=201)

    @extend_schema(responses={200: ExchangeSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def messages(self, request, business_id, pk):
        exchanges = self.get_object().exchanges.filter(business=self.business).select_related("proposal")
        page = self.paginate_queryset(exchanges)
        return self.get_paginated_response(ExchangeSerializer(page, many=True).data)

    @extend_schema(request=MessageInput, responses={201: ExchangeSerializer, 200: ExchangeSerializer, 409: dict})
    @messages.mapping.post
    def send(self, request, business_id, pk):
        conversation = self.get_object()
        data = validated(MessageInput, request.data)
        prompt = data["text"]
        exchanges = conversation.exchanges.filter(business=self.business)
        prior = exchanges.filter(request_id=data["request_id"]).first()
        if prior:
            return self.replay(prior, prompt)
        recent = list(exchanges[:4])
        latest = recent[0] if recent else None
        command = prompt.strip().rstrip(".!?")
        control = self.control(command, latest)
        if not control:
            answer, proposal = self.interpret(prompt, recent)
        with transaction.atomic():
            conversation = self.get_queryset().select_for_update().get(pk=conversation.pk)
            prior = exchanges.filter(request_id=data["request_id"]).first()
            if prior:
                return self.replay(prior, prompt)
            if exchanges.values_list("pk", flat=True).first() != (latest.pk if latest else None):
                return Response({"detail": "A newer message arrived. Retry after reviewing the conversation."}, status=409)
            if control:
                answer = self.apply_control(conversation, command, latest, control)
                proposal = None
            exchange = AssistantExchange.objects.create(conversation=conversation, business=self.business,
                                                        request_id=data["request_id"], prompt=prompt, answer=answer)
            if proposal:
                AssistantProposal.objects.create(exchange=exchange, business=self.business, **proposal)
            if latest is None:
                conversation.title = " ".join(prompt.split())[:90]
            conversation.save(update_fields=["title", "updated_at"])
        return Response(ExchangeSerializer(exchange).data, status=201)

    def get_throttles(self):
        if self.action == "send":
            self.throttle_scope = "assistant_messages"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @staticmethod
    def replay(prior, prompt):
        if prior.prompt != prompt:
            return Response({"detail": "This message reference has already been used."}, status=409)
        return Response(ExchangeSerializer(prior).data)

    @staticmethod
    def control(command, latest):
        if latest is None:
            return None
        if re.fullmatch(r"(?:please )?cancel(?: it| the (?:sale|transaction|proposal))?", command, re.I):
            return "cancel"
        if command.casefold() in ("yes", "confirm", "yes please", "record it") and not latest.answer.get("followup"):
            return "confirmation"
        if QUANTITY_EDIT.fullmatch(command) and not latest.answer.get("followup"):
            return "quantity"
        return None

    def apply_control(self, conversation, command, latest, operation):
        mode = "workspace"
        if not Membership.objects.filter(business=self.business, user=self.request.user).exists():
            raise PermissionDenied("Your workspace access has changed.")
        if operation == "cancel" and latest.answer.get("followup"):
            return {**response("I cleared the current draft. No transaction was recorded."), "mode": mode}
        proposal = AssistantProposal.objects.filter(
            business=self.business, exchange__conversation=conversation
        ).order_by("-id").first()
        if not proposal or proposal.status != AssistantProposal.Status.PENDING:
            return {**response("There is no pending transaction in this conversation."), "mode": mode}
        if proposal.expires_at <= timezone.now():
            return {**response("That preview expired. Start a new transaction to continue."), "mode": mode}
        if operation == "confirmation":
            return {**response("Use Confirm on the transaction preview to record it."), "mode": mode}
        if operation == "cancel":
            _, error = change_proposal(proposal, self.request.user, proposal.revision, "cancel")
            text = error or "I cancelled the proposal. No transaction was recorded."
        else:
            if "quantity" not in proposal.payload:
                return {**response("This preview has no quantity to change. Use Edit preview to update it."), "mode": mode}
            quantity = quantity_value(QUANTITY_EDIT.fullmatch(command)[1])
            try:
                _, error = change_proposal(proposal, self.request.user, proposal.revision, "edit",
                                           {**proposal.payload, "quantity": quantity})
                text = error or f"I updated the preview to {quantity}. Review it before confirming."
            except ValidationError as problem:
                text = validation_text(problem.detail)
        return {**response(text), "mode": mode}

    def interpret(self, prompt, recent):
        if INJECTION.search(prompt):
            return {**response("I can help with supported workspace questions and transaction previews. Permissions and explicit confirmation still apply."),
                    "mode": "workspace"}, None
        latest = recent[0] if recent else None
        followup = latest.answer.get("followup") if latest else None
        report_context = latest.answer.get("report_intent") if latest else None
        prior_intent = next((item.answer["conversation_intent"] for item in recent
                             if item.answer.get("conversation_intent")), None)
        current_context = followup["intent"] if followup else report_context or prior_intent
        if active_provider():
            try:
                context = {"prior_messages": [item.prompt[:500] for item in reversed(recent)],
                           "current_draft_or_topic": followup["intent"] if followup else report_context,
                           "awaiting": followup["field"] if followup else None}
                if not followup and not report_context and prior_intent and prior_intent["action"] in PROPOSAL_ACTIONS - {"expense"} | {"stock"}:
                    context["recent_product"] = prior_intent.get("entity")
                intent = provider_intent(prompt, local_day(self.business), self.business.currency, context)
                mode = "provider"
            except ProviderUnavailable as failure:
                answer = response(str(failure) or "The configured model could not respond. Try sending your message again or check the server's provider configuration.")
                return {**answer, "mode": "provider_unavailable",
                        **({key: latest.answer[key] for key in CONTEXT_KEYS if key in latest.answer} if latest else {})}, None
            # A one-field reply can only fill that slot. Small models sometimes
            # emit unrelated defaults that would otherwise overwrite the draft.
            method_reply = (
                clarification_value("method", prompt, current_context)
                if followup and followup["field"] == "method"
                and intent["action"] in ("continue", current_context["action"])
                else None
            )
            report_reply = (
                period_followup(prompt, report_context)
                if report_context and not followup
                else None
            )
            if method_reply and intent.get("method", "").casefold().replace("bank ", "") == method_reply["method"]:
                intent = method_reply
            elif report_reply:
                intent = report_reply
            elif intent["action"] in PERIOD_READ_ACTIONS:
                # Keep an explicit analysis topic when the small model picks a broader financial report.
                specific = local_intent(prompt)
                if specific["action"] == "insights" and specific.get("entity"):
                    intent = {**intent, "action": "insights", "entity": specific["entity"],
                              "period": specific.get("period") or intent.get("period", ""),
                              "comparison": specific.get("comparison") or intent.get("comparison", "")}
            elif intent["action"] == "continue":
                changes = {key: value for key, value in intent.items() if key != "action"}
                if followup and followup["field"] == "source":
                    intent = clarification_value("source", prompt, current_context) or current_context
                elif followup and followup["field"] == "use_catalog":
                    intent = clarification_value("use_catalog", prompt, current_context) or current_context
                elif followup or report_context:
                    intent = {**current_context, **changes}
                    if report_context and not followup and changes.get("period") and "comparison" not in changes:
                        intent["comparison"] = ""
                else:
                    intent = {"action": "unsupported"}
            elif followup and intent["action"] in ("purchase", "opening", "adjustment") and followup["field"] == "source":
                intent = {**current_context, **intent}
            elif followup and intent["action"] == current_context["action"] and not intent.get("entity"):
                intent = {**current_context, **intent}
        else:
            mode = "demo"
            intent = local_intent(prompt)
            if followup and (intent["action"] == "unsupported" or prompt in latest.answer.get("choices", [])):
                quantity_edit = QUANTITY_EDIT.fullmatch(prompt.strip().rstrip(".!?"))
                if quantity_edit and current_context["action"] in PROPOSAL_ACTIONS - {"expense"}:
                    intent = {**current_context, "quantity": quantity_value(quantity_edit[1])}
                else:
                    intent = clarification_value(followup["field"], prompt, current_context) or intent
            elif intent["action"] == "unsupported":
                intent = period_followup(prompt, report_context) or intent
        if (report_context and intent["action"] == "insights" and not intent.get("period")
                and re.search(r"\b(?:that|those|same period|the change|what drove it)\b", prompt, re.I)):
            intent = {**intent, "period": report_context.get("period", ""),
                      "comparison": intent.get("comparison") or report_context.get("comparison", "")}
        if (prior_intent and prior_intent["action"] in PROPOSAL_ACTIONS | {"stock"}
                and intent["action"] in {"sale", "restock", "stock"}
                and re.match(r"^(?:of\s+)?(?:that|this|same)\b", intent.get("entity", ""), re.I)):
            if prior_intent.get("entity"):
                intent = {**intent, "entity": prior_intent["entity"]}
        if intent["action"] == "analysis" and settings.ASSISTANT_PROVIDER != "groq":
            intent = {**intent, "action": "insights"}
        proposal = None
        if not Membership.objects.filter(business=self.business, user=self.request.user).exists():
            raise PermissionDenied("Your workspace access has changed.")
        try:
            if intent["action"] in PROPOSAL_ACTIONS:
                answer, payload = parse_proposal(self.business, self.request.user, intent)
                if payload is not None:
                    key = uuid4()
                    payload, preview, _ = prepare(self.business, intent["action"], payload, key)
                    proposal = {"kind": intent["action"], "payload": payload, "preview": preview, "request_id": key,
                                "expires_at": timezone.now() + PROPOSAL_LIFETIME}
                    answer = response("Review this preview. Confirm when the details match the transaction you want to record.")
                    if preview.get("sku"):
                        intent = {**intent, "entity": preview["sku"]}
            elif intent["action"] in ("analysis", "insights", "unsupported") and settings.ASSISTANT_PROVIDER == "groq":
                from .business_conversation import answer_question
                intent = {**intent, "action": "analysis"}
                answer = answer_question(self.business, prompt, intent, recent)
                answer["report_intent"] = intent
            else:
                answer = run_read_tool(self.business, intent)
                if (answer.get("card") or intent["action"] == "insights") and intent["action"] in PERIOD_READ_ACTIONS:
                    answer["report_intent"] = intent
        except ProviderUnavailable as error:
            answer = {**response(str(error)), "mode": "provider_unavailable"}
            mode = "provider_unavailable"
        except ValidationError as error:
            answer = response(validation_text(error.detail))
        if answer.get("followup"):
            answer["conversation_intent"] = answer["followup"]["intent"]
        elif intent["action"] != "unsupported":
            answer["conversation_intent"] = intent
        elif followup:
            answer.update(followup=followup, choices=latest.answer.get("choices", []))
        return {**answer, "mode": mode}, proposal


class Proposals(TenantMixin, viewsets.GenericViewSet):
    queryset = AssistantProposal.objects.all()
    serializer_class = RevisionInput

    write_roles = Membership.Role.values

    def apply(self, request, pk, operation):
        proposal = get_object_or_404(self.get_queryset().filter(
            exchange__conversation__user=request.user, exchange__conversation__business=self.business,
        ), pk=pk)
        data = validated(EditInput if operation == "edit" else RevisionInput, request.data)
        proposal, error = change_proposal(proposal, request.user, data["revision"], operation, data.get("payload"))
        return Response({"proposal": proposal_data(proposal), "detail": error}, status=409 if error else 200)

    @extend_schema(request=EditInput, responses={200: dict, 409: dict})
    @action(detail=True, methods=["post"])
    def edit(self, request, business_id, pk):
        return self.apply(request, pk, "edit")

    @extend_schema(request=RevisionInput, responses={200: dict, 409: dict})
    @action(detail=True, methods=["post"])
    def confirm(self, request, business_id, pk):
        return self.apply(request, pk, "confirm")

    @extend_schema(request=RevisionInput, responses={200: dict, 409: dict})
    @action(detail=True, methods=["post"])
    def cancel(self, request, business_id, pk):
        return self.apply(request, pk, "cancel")
