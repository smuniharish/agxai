"""Offline stand-ins for chat models, built on LangChain's own fake chat model."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class ScriptedChatModel(GenericFakeChatModel):
    """Replays fixed replies and accepts tool binding like a real chat model.

    ``GenericFakeChatModel`` raises on ``bind_tools``, which ``create_agent`` and
    ``create_deep_agent`` call; the script already decides which tools are called.
    """

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedChatModel:
        return self


def scripted_model(*replies: AIMessage | str) -> ScriptedChatModel:
    """Return a model that answers each call with the next reply."""
    return ScriptedChatModel(messages=iter(replies))


def tool_call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    """Return a model turn that requests one tool call."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])
