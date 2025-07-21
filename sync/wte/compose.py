"""
Pipeline Composition Utilities

Helpers for building complex pipelines through functional composition.
"""

from typing import TypeVar, AsyncGenerator, Callable, Optional, Awaitable
from .core import WTE, WatcherFn, TransformFn, ExecutorFn

T = TypeVar('T')
M = TypeVar('M') 
A = TypeVar('A')


def compose(
    watch: WatcherFn[T],
    transform: TransformFn[T, A], 
    execute: ExecutorFn[A]
) -> WTE[T, A]:
    """Compose a WTE pipeline from functional components"""
    return WTE(watch, transform, execute)


def chain(
    transform1: TransformFn[T, M],
    transform2: TransformFn[M, A]
) -> TransformFn[T, A]:
    """Chain two transforms together"""
    def chained_transform(event: T) -> Optional[A]:
        middle = transform1(event)
        return transform2(middle) if middle is not None else None
    
    return chained_transform


async def pipe(
    source: AsyncGenerator[T, None],
    *transforms: Callable[[AsyncGenerator], AsyncGenerator]
) -> None:
    """Pipe an async generator through multiple transforms"""
    current = source
    
    for transform in transforms:
        current = transform(current)
    
    # Consume the final generator
    async for _ in current:
        pass  # Pipeline complete


def filter_transform(predicate: Callable[[T], bool]) -> Callable[[AsyncGenerator[T, None]], AsyncGenerator[T, None]]:
    """Create a filter transform for use in pipes"""
    async def filtered_generator(source: AsyncGenerator[T, None]) -> AsyncGenerator[T, None]:
        async for item in source:
            if predicate(item):
                yield item
    
    return filtered_generator


def map_transform(mapper: Callable[[T], M]) -> Callable[[AsyncGenerator[T, None]], AsyncGenerator[M, None]]:
    """Create a map transform for use in pipes"""
    async def mapped_generator(source: AsyncGenerator[T, None]) -> AsyncGenerator[M, None]:
        async for item in source:
            yield mapper(item)
    
    return mapped_generator


def batch_transform(batch_size: int) -> Callable[[AsyncGenerator[T, None]], AsyncGenerator[list[T], None]]:
    """Create a batching transform for use in pipes"""
    async def batched_generator(source: AsyncGenerator[T, None]) -> AsyncGenerator[list[T], None]:
        batch = []
        
        async for item in source:
            batch.append(item)
            
            if len(batch) >= batch_size:
                yield batch
                batch = []
        
        # Yield remaining items
        if batch:
            yield batch
    
    return batched_generator