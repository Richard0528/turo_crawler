#!/usr/bin/env python3
"""
Turo Crawler - A web crawler using Playwright and CDP to connect to Chrome browser instances.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import requests
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from dotenv import load_dotenv

from crawler import TuroCrawler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to demonstrate the crawler usage."""
    crawler = TuroCrawler(debug_port=9222)
    
    try:
        # Connect to the browser
        logger.info("Attempting to connect to Chrome browser...")
        if not await crawler.connect_to_browser():
            logger.error("Failed to connect to browser. Make sure Chrome is running with --remote-debugging-port=9222")
            return
        
        # Wait a moment for the page to load
        await asyncio.sleep(2)
        
        # Take a screenshot of the original page
        screenshot_path = await crawler.take_screenshot("original_page.png")
        logger.info(f"Original page screenshot taken: {screenshot_path}")
        
        # Get page data of the original page
        page_data = await crawler.get_page_data()
        data_path = await crawler.save_page_data(page_data, "original_page_data.json")
        logger.info(f"Original page data extracted: {data_path}")
        
        # Print some basic information about the original page
        print(f"\nOriginal Page:")
        print(f"Title: {page_data['title']}")
        print(f"URL: {page_data['url']}")
        print(f"Number of links found: {len(page_data['links'])}")
        print(f"Number of images found: {len(page_data['images'])}")
        
        # Example 1: Navigate through all hrefs on the page
        print(f"\n=== Example 1: Navigating through all hrefs ===")
        all_hrefs = await crawler.get_all_hrefs()
        print(f"Found {len(all_hrefs)} total hrefs on the page")
        
        # Navigate through first 5 hrefs (to avoid too many requests)
        if all_hrefs:
            limited_hrefs = all_hrefs[:5]  # Limit to first 5 for demo
            print(f"Navigating through first {len(limited_hrefs)} hrefs...")
            
            navigation_results = await crawler.navigate_and_return(
                hrefs=limited_hrefs,
                take_screenshot=True,
                extract_data=True,
                delay_between_navigation=1.5
            )
            
            print(f"\nNavigation Results:")
            for result in navigation_results:
                if "error" in result:
                    print(f"  ❌ {result['original_link']['text']}: {result['error']}")
                else:
                    print(f"  ✅ {result['original_link']['text']} -> {result['page_title']}")
        
        # Example 2: Navigate through specific links using CSS selector
        print(f"\n=== Example 2: Navigating through specific links ===")
        
        # Common selectors for different types of links
        selectors_to_try = [
            "a[href*='product']",      # Product links
            "a[href*='item']",         # Item links
            "a[href*='detail']",       # Detail links
            ".product-link",           # Product link class
            ".item-link",              # Item link class
            "a[href*='page']",         # Page links
            "a[href*='article']",      # Article links
        ]
        
        for selector in selectors_to_try:
            print(f"\nTrying selector: {selector}")
            try:
                selector_results = await crawler.navigate_and_return_with_selector(
                    selector=selector,
                    take_screenshot=True,
                    extract_data=True,
                    delay_between_navigation=1.0,
                    max_links=3  # Limit to 3 links per selector for demo
                )
                
                if selector_results:
                    print(f"  Found {len(selector_results)} links with selector '{selector}'")
                    for result in selector_results:
                        if "error" not in result:
                            print(f"    ✅ {result['original_link']['text']} -> {result['page_title']}")
                else:
                    print(f"  No links found with selector '{selector}'")
                    
            except Exception as e:
                print(f"  Error with selector '{selector}': {e}")
        
        # Example 3: Navigate through filtered hrefs
        print(f"\n=== Example 3: Navigating through filtered hrefs ===")
        
        # Get hrefs that contain specific patterns
        filtered_hrefs = await crawler.get_all_hrefs(filter_pattern=r"https?://")
        print(f"Found {len(filtered_hrefs)} external links")
        
        if filtered_hrefs:
            # Take first 3 external links for demo
            external_links = filtered_hrefs[:3]
            external_results = await crawler.navigate_and_return(
                hrefs=external_links,
                take_screenshot=True,
                extract_data=True,
                delay_between_navigation=2.0  # Longer delay for external sites
            )
            
            print(f"\nExternal Navigation Results:")
            for result in external_results:
                if "error" in result:
                    print(f"  ❌ {result['original_link']['text']}: {result['error']}")
                else:
                    print(f"  ✅ {result['original_link']['text']} -> {result['current_url']}")
        
        # Example: Wait for a specific element and click it
        await crawler.wait_for_element("button.submit", timeout=5000)
        await crawler.click_element("button.submit")
        
        # Example: Fill a form
        form_data = {"input[name='username']": "testuser", "input[name='password']": "testpass"}
        await crawler.fill_form(form_data)
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
