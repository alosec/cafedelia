"""
Core Watch-Transform-Execute interface

The fundamental pattern of cafedelia v2 sync pipeline.
Based on cafedelic's proven WTE architecture.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Callable, AsyncGenerator, Optional, Awaitable

T = TypeVar('T')  # Event type
A = TypeVar('A')  # Action type

# Type aliases for functional composition
WatcherFn = Callable[[], AsyncGenerator[T, None]]
TransformFn = Callable[[T], Optional[A]]
ExecutorFn = Callable[[A], Awaitable[None]]


class WTE(Generic[T, A]):
    """Watch-Transform-Execute pipeline interface"""
    
    def __init__(self, 
                 watch: WatcherFn[T], 
                 transform: TransformFn[T, A], 
                 execute: ExecutorFn[A]):
        self.watch = watch
        self.transform = transform  
        self.execute = execute
    
    async def run(self) -> None:
        """Execute the pipeline"""
        async for event in self.watch():
            action = self.transform(event)
            if action is not None:
                await self.execute(action)


class WTEBase(Generic[T, A], ABC):
    """Base class for object-oriented WTE implementations"""
    
    @abstractmethod
    async def watch(self) -> AsyncGenerator[T, None]:
        """Watch for events of type T"""
        pass
    
    @abstractmethod
    def transform(self, event: T) -> Optional[A]:
        """Transform event T into action A, or None to skip"""  
        pass
    
    @abstractmethod
    async def execute(self, action: A) -> None:
        """Execute action A"""
        pass
    
    async def run(self) -> None:
        """Execute the pipeline"""
        async for event in self.watch():
            action = self.transform(event)
            if action is not None:
                await self.execute(action)