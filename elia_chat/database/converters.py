from typing import TYPE_CHECKING, Any


from elia_chat.database.models import ChatDao, MessageDao
from elia_chat.models import ChatData, ChatMessage, get_model

if TYPE_CHECKING:
    from litellm.types.completion import ChatCompletionUserMessageParam


def chat_message_to_message_dao(
    message: ChatMessage,
    chat_id: int,
) -> MessageDao:
    """Convert a ChatMessage to a SQLModel message."""
    meta: dict[str, Any] = message.message.get("meta", {})
    content = message.message.get("content", "")
    
    # Extract sidechain information from meta if present
    is_sidechain = meta.get("is_sidechain", False)
    sidechain_metadata = meta.get("sidechain_metadata", {})
    message_source = meta.get("message_source", "main")
    
    return MessageDao(
        chat_id=chat_id,
        role=message.message["role"],
        content=content if isinstance(content, str) else "",
        timestamp=message.timestamp,
        model=message.model.lookup_key,
        meta=meta,
        is_sidechain=is_sidechain,
        sidechain_metadata=sidechain_metadata,
        message_source=message_source,
    )


def chat_dao_to_chat_data(chat_dao: ChatDao) -> ChatData:
    """Convert the SQLModel chat to a ChatData."""
    model = chat_dao.model
    return ChatData(
        id=chat_dao.id,
        title=chat_dao.title,
        model=get_model(model),
        create_timestamp=chat_dao.started_at if chat_dao.started_at else None,
        messages=[
            message_dao_to_chat_message(message, model) for message in chat_dao.messages
        ],
        session_id=chat_dao.session_id,
    )


def message_dao_to_chat_message(message_dao: MessageDao, model: str) -> ChatMessage:
    """Convert the SQLModel message to a ChatMessage."""
    message: ChatCompletionUserMessageParam = {
        "content": message_dao.content,
        "role": message_dao.role,  # type: ignore
    }
    
    # Include sidechain metadata in the meta field for display widgets
    meta = dict(message_dao.meta) if message_dao.meta else {}
    if hasattr(message_dao, 'is_sidechain'):
        meta.update({
            "is_sidechain": message_dao.is_sidechain,
            "sidechain_metadata": message_dao.sidechain_metadata or {},
            "message_source": message_dao.message_source or "main"
        })
    
    # Add meta to message if we have sidechain data
    if meta:
        message["meta"] = meta  # type: ignore

    return ChatMessage(
        message=message,
        timestamp=message_dao.timestamp,
        model=get_model(model),
    )
