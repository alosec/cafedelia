from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import desc
from sqlmodel import select

from elia_chat.database.database import get_session
from elia_chat.database.models import ActorDao, AgentRunDao, RoomDao, RoomMessageDao


DEFAULT_ACTORS = [
    {"key": "user", "name": "You", "kind": "human", "command": None},
    {"key": "claude", "name": "Claude Code", "kind": "agent", "command": "cnd"},
    {
        "key": "codex",
        "name": "Codex",
        "kind": "agent",
        "command": "codex exec --json --dangerously-bypass-approvals-and-sandbox",
    },
    {"key": "system", "name": "System", "kind": "system", "command": None},
]


@dataclass(frozen=True)
class RoomMessageData:
    id: int | None
    room_id: int
    actor_key: str
    actor_name: str
    actor_kind: str
    role: str
    event_type: str
    content: str
    timestamp: datetime.datetime | None
    raw_json: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRunData:
    id: int | None
    room_id: int
    actor_key: str
    status: str
    command: str


class RoomManager:
    @staticmethod
    async def ensure_default_actors() -> dict[str, ActorDao]:
        async with get_session() as session:
            actors: dict[str, ActorDao] = {}
            for actor_def in DEFAULT_ACTORS:
                statement = select(ActorDao).where(ActorDao.key == actor_def["key"])
                result = await session.exec(statement)
                actor = result.one_or_none()
                if actor is None:
                    actor = ActorDao(**actor_def)
                    session.add(actor)
                    await session.flush()
                else:
                    actor.name = actor_def["name"]
                    actor.kind = actor_def["kind"]
                    actor.command = actor_def["command"]
                    session.add(actor)
                actors[actor.key] = actor
            await session.commit()
            return actors

    @staticmethod
    async def get_or_create_room(title: str = "Claude Code × Codex") -> RoomDao:
        await RoomManager.ensure_default_actors()
        async with get_session() as session:
            statement = (
                select(RoomDao)
                .where(RoomDao.title == title)
                .where(RoomDao.archived == False)  # noqa: E712
                .order_by(desc(RoomDao.created_at))
            )
            result = await session.exec(statement)
            room = result.first()
            if room is None:
                room = RoomDao(title=title)
                session.add(room)
                await session.commit()
            return room

    @staticmethod
    async def list_rooms() -> list[RoomDao]:
        async with get_session() as session:
            statement = (
                select(RoomDao)
                .where(RoomDao.archived == False)  # noqa: E712
                .order_by(desc(RoomDao.updated_at))
            )
            result = await session.exec(statement)
            return list(result)

    @staticmethod
    async def archive_room(room_id: int) -> None:
        async with get_session() as session:
            room = await session.get(RoomDao, room_id)
            if room is None:
                return
            room.archived = True
            session.add(room)
            await session.commit()

    @staticmethod
    async def get_actor(actor_key: str) -> ActorDao:
        await RoomManager.ensure_default_actors()
        async with get_session() as session:
            statement = select(ActorDao).where(ActorDao.key == actor_key)
            result = await session.exec(statement)
            return result.one()

    @staticmethod
    async def add_message(
        room_id: int,
        actor_key: str,
        content: str,
        *,
        role: str = "assistant",
        event_type: str = "message",
        raw_json: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        parent_id: int | None = None,
    ) -> RoomMessageData:
        actor = await RoomManager.get_actor(actor_key)
        now = datetime.datetime.now(datetime.timezone.utc)
        async with get_session() as session:
            message = RoomMessageDao(
                room_id=room_id,
                actor_id=actor.id,
                role=role,
                event_type=event_type,
                content=content,
                timestamp=now,
                raw_json=raw_json or {},
                meta=meta or {},
                parent_id=parent_id,
            )
            session.add(message)
            room = await session.get(RoomDao, room_id)
            if room:
                room.updated_at = now
                session.add(room)
            await session.commit()
            return RoomMessageData(
                id=message.id,
                room_id=room_id,
                actor_key=actor.key,
                actor_name=actor.name,
                actor_kind=actor.kind,
                role=role,
                event_type=event_type,
                content=content,
                timestamp=message.timestamp,
                raw_json=raw_json or {},
                meta=meta or {},
            )

    @staticmethod
    async def get_messages(room_id: int, limit: int = 200) -> list[RoomMessageData]:
        async with get_session() as session:
            statement = (
                select(RoomMessageDao, ActorDao)
                .join(ActorDao, ActorDao.id == RoomMessageDao.actor_id)
                .where(RoomMessageDao.room_id == room_id)
                .order_by(RoomMessageDao.timestamp)
                .limit(limit)
            )
            result = await session.exec(statement)
            messages = []
            for message, actor in result:
                messages.append(
                    RoomMessageData(
                        id=message.id,
                        room_id=message.room_id,
                        actor_key=actor.key,
                        actor_name=actor.name,
                        actor_kind=actor.kind,
                        role=message.role,
                        event_type=message.event_type,
                        content=message.content,
                        timestamp=message.timestamp,
                        raw_json=dict(message.raw_json or {}),
                        meta=dict(message.meta or {}),
                    )
                )
            return messages

    @staticmethod
    async def format_transcript(room_id: int, limit: int = 40) -> str:
        messages = await RoomManager.get_messages(room_id, limit=limit)
        recent_messages = messages[-limit:]
        return "\n".join(
            f"{message.actor_name}: {message.content}" for message in recent_messages
        )

    @staticmethod
    async def latest_actor_meta_value(
        room_id: int,
        actor_key: str,
        meta_key: str,
    ) -> str | None:
        async with get_session() as session:
            statement = (
                select(RoomMessageDao, ActorDao)
                .join(ActorDao, ActorDao.id == RoomMessageDao.actor_id)
                .where(RoomMessageDao.room_id == room_id)
                .where(ActorDao.key == actor_key)
                .order_by(desc(RoomMessageDao.timestamp), desc(RoomMessageDao.id))
            )
            result = await session.exec(statement)
            for message, _actor in result:
                value = (message.meta or {}).get(meta_key)
                if isinstance(value, str) and value:
                    return value
            return None

    @staticmethod
    async def create_agent_run(
        room_id: int,
        actor_key: str,
        command: list[str],
    ) -> AgentRunData:
        actor = await RoomManager.get_actor(actor_key)
        async with get_session() as session:
            run = AgentRunDao(
                room_id=room_id,
                actor_id=actor.id,
                command=" ".join(command),
            )
            session.add(run)
            await session.commit()
            return AgentRunData(
                id=run.id,
                room_id=room_id,
                actor_key=actor.key,
                status=run.status,
                command=run.command,
            )

    @staticmethod
    async def finish_agent_run(
        run_id: int | None,
        *,
        status: str,
        exit_code: int | None = None,
        error: str | None = None,
    ) -> None:
        if run_id is None:
            return
        async with get_session() as session:
            run = await session.get(AgentRunDao, run_id)
            if run is None:
                return
            run.status = status
            run.exit_code = exit_code
            run.error = error
            run.ended_at = datetime.datetime.now(datetime.timezone.utc)
            session.add(run)
            await session.commit()
