from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from fastapi import HTTPException, status
from app.models.chat import ChatThread
from app.schemas.chat import ChatThreadCreate, ChatThreadUpdate


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_thread(
        self,
        request: ChatThreadCreate,
    ) -> ChatThread:
        thread = ChatThread(title=request.title)

        self.db.add(thread)
        await self.db.commit()
        await self.db.refresh(thread)

        return thread

    async def update_thread(
        self,
        thread_id: UUID,
        request: ChatThreadUpdate,
    ) -> ChatThread:
        thread = await self.db.get(ChatThread, thread_id)
        if thread is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat thread not found",
            )

        thread.title = request.title

        await self.db.commit()
        await self.db.refresh(thread)
        return thread

    async def delete_thread(self, thread_id: UUID) -> None:
        statement = (
            select(ChatThread).where(ChatThread.id == thread_id).with_for_update()
        )
        result = await self.db.execute(statement)
        thread = result.scalar_one_or_none()

        if thread is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat thread not found",
            )

        await self.db.delete(thread)
        await self.db.commit()

    async def list_threads(self) -> list[ChatThread]:
        statement = select(ChatThread).order_by(ChatThread.updated_at.desc())

        result = await self.db.execute(statement)

        return list(result.scalars().all())

    async def get_thread(
        self,
        thread_id: UUID,
    ) -> ChatThread:
        statement = (
            select(ChatThread)
            .options(selectinload(ChatThread.messages))
            .where(ChatThread.id == thread_id)
        )

        result = await self.db.execute(statement)
        thread = result.scalar_one_or_none()

        if thread is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat thread not found",
            )

        return thread
