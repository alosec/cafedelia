"""
Pagination mixin for Textual widgets to handle large datasets efficiently.

Provides lazy loading and infinite scroll capabilities for OptionList-based widgets.
"""

import asyncio
from typing import Protocol, TypeVar, Generic, Callable, Awaitable, Any
from textual import log
from textual.message import Message
from textual.widgets.option_list import Option


T = TypeVar('T')


class PaginatedDataSource(Protocol[T]):
    """Protocol for data sources that support pagination."""
    
    async def get_page(self, limit: int, offset: int) -> list[T]:
        """Get a page of data with the given limit and offset."""
        ...
    
    async def get_total_count(self) -> int:
        """Get the total count of items for pagination calculations."""
        ...


class PaginationMixin(Generic[T]):
    """Mixin to add pagination capabilities to Textual widgets."""
    
    def __init__(self, page_size: int = 50, preload_pages: int = 2):
        self.page_size = page_size
        self.preload_pages = preload_pages
        self.current_page = 0
        self.total_items = 0
        self.loaded_pages: set[int] = set()
        self.loading_pages: set[int] = set()
        self.all_loaded = False
        self._data_source: PaginatedDataSource[T] | None = None
        self._item_factory: Callable[[T], Option] | None = None
    
    def set_data_source(
        self, 
        data_source: PaginatedDataSource[T], 
        item_factory: Callable[[T], Option]
    ) -> None:
        """Set the data source and item factory for pagination."""
        self._data_source = data_source
        self._item_factory = item_factory
    
    async def initialize_pagination(self) -> None:
        """Initialize pagination by loading the first page and getting total count."""
        if not self._data_source:
            raise ValueError("Data source must be set before initializing pagination")
        
        # Get total count for pagination calculations
        self.total_items = await self._data_source.get_total_count()
        log.debug(f"Pagination initialized with {self.total_items} total items")
        
        # Load first page
        await self.load_page(0)
    
    async def load_page(self, page_number: int) -> bool:
        """Load a specific page of data. Returns True if page was loaded."""
        if (page_number in self.loaded_pages or 
            page_number in self.loading_pages or
            not self._data_source or 
            not self._item_factory):
            return False
        
        # Check if we've already loaded all data
        max_page = (self.total_items - 1) // self.page_size
        if page_number > max_page:
            self.all_loaded = True
            return False
        
        self.loading_pages.add(page_number)
        
        try:
            offset = page_number * self.page_size
            items = await self._data_source.get_page(self.page_size, offset)
            
            # Convert items to options and add them
            options = [self._item_factory(item) for item in items]
            
            # Add options at the appropriate position
            if hasattr(self, 'add_options'):
                # For OptionList widgets - add at end for infinite scroll
                self.add_options(options)
            
            self.loaded_pages.add(page_number)
            
            # Check if this was the last page
            if len(items) < self.page_size:
                self.all_loaded = True
            
            log.debug(f"Loaded page {page_number} with {len(items)} items")
            return True
            
        except Exception as e:
            log.error(f"Error loading page {page_number}: {e}")
            return False
        finally:
            self.loading_pages.discard(page_number)
    
    async def load_next_page(self) -> bool:
        """Load the next page of data."""
        if self.all_loaded:
            return False
        
        next_page = max(self.loaded_pages) + 1 if self.loaded_pages else 0
        return await self.load_page(next_page)
    
    async def preload_pages_ahead(self, current_position: int | None = None) -> None:
        """Preload pages ahead of current position for smooth scrolling."""
        if self.all_loaded or not self.loaded_pages:
            return
        
        # Estimate current page based on position or use highest loaded page
        if current_position is not None:
            estimated_page = current_position // self.page_size
        else:
            estimated_page = max(self.loaded_pages)
        
        # Preload pages ahead
        for i in range(1, self.preload_pages + 1):
            target_page = estimated_page + i
            if target_page not in self.loaded_pages and target_page not in self.loading_pages:
                asyncio.create_task(self.load_page(target_page))
    
    def should_load_more(self, highlighted_index: int | None) -> bool:
        """Check if we should load more data based on current position."""
        if self.all_loaded or highlighted_index is None:
            return False
        
        # Calculate how many items we have loaded
        total_loaded = len(self.loaded_pages) * self.page_size
        
        # Load more if we're within one page of the end
        return highlighted_index >= total_loaded - self.page_size
    
    async def handle_scroll_near_end(self, highlighted_index: int | None) -> None:
        """Handle scrolling near the end of loaded data."""
        if self.should_load_more(highlighted_index):
            await self.load_next_page()
            await self.preload_pages_ahead(highlighted_index)
    
    def get_pagination_status(self) -> dict[str, Any]:
        """Get current pagination status for debugging/UI display."""
        return {
            "total_items": self.total_items,
            "loaded_pages": len(self.loaded_pages),
            "current_page": self.current_page,
            "all_loaded": self.all_loaded,
            "page_size": self.page_size,
            "estimated_loaded_items": len(self.loaded_pages) * self.page_size
        }