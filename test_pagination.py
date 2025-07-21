#!/usr/bin/env python3
"""
Test script to verify pagination performance improvements.
"""

import asyncio
import time
from elia_chat.chats_manager import ChatsManager
from elia_chat.database.models import ChatDao


async def test_pagination_performance():
    """Test pagination vs loading all chats."""
    
    print("Testing pagination performance...")
    
    # Test getting total count
    start_time = time.time()
    total_count = await ChatsManager.count_chats()
    count_time = time.time() - start_time
    print(f"Total chats: {total_count} (retrieved in {count_time:.3f}s)")
    
    if total_count == 0:
        print("No chats found in database - cannot test pagination")
        return
    
    # Test paginated loading (first 50)
    start_time = time.time()
    first_page = await ChatsManager.paginated_chats(limit=50, offset=0)
    page_time = time.time() - start_time
    print(f"First page: {len(first_page)} chats (retrieved in {page_time:.3f}s)")
    
    # Test loading all chats (for comparison)
    print("Loading all chats for comparison...")
    start_time = time.time()
    all_chats = await ChatsManager.all_chats()
    all_time = time.time() - start_time
    print(f"All chats: {len(all_chats)} chats (retrieved in {all_time:.3f}s)")
    
    # Calculate performance improvement
    if page_time > 0:
        improvement = (all_time / page_time)
        print(f"Pagination is {improvement:.1f}x faster for first page load")
    
    # Test multiple pages
    if total_count > 50:
        print(f"Testing multiple pages...")
        pages_to_test = min(5, (total_count + 49) // 50)  # Test up to 5 pages
        
        total_page_time = 0
        total_loaded = 0
        
        for page_num in range(pages_to_test):
            start_time = time.time()
            page_chats = await ChatsManager.paginated_chats(limit=50, offset=page_num * 50)
            page_load_time = time.time() - start_time
            total_page_time += page_load_time
            total_loaded += len(page_chats)
            print(f"  Page {page_num + 1}: {len(page_chats)} chats in {page_load_time:.3f}s")
        
        print(f"Total: {total_loaded} chats in {total_page_time:.3f}s across {pages_to_test} pages")
        avg_page_time = total_page_time / pages_to_test
        print(f"Average page load time: {avg_page_time:.3f}s")


if __name__ == "__main__":
    asyncio.run(test_pagination_performance())