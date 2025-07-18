#!/usr/bin/env python3
"""
Example script demonstrating the navigation functionality of the Turo Crawler.
"""

import asyncio
import json
from crawler import TuroCrawler


async def example_navigate_all_links():
    """Example: Navigate through all links on a page."""
    print("=== Navigate All Links Example ===")
    
    crawler = TuroCrawler(debug_port=9222)
    
    try:
        if not await crawler.connect_to_browser():
            print("Failed to connect to browser.")
            return
        
        # Get all hrefs from the current page
        hrefs = await crawler.get_all_hrefs()
        print(f"Found {len(hrefs)} links on the page")
        
        # Navigate through first 3 links (for demo purposes)
        if hrefs:
            demo_links = hrefs[:3]
            results = await crawler.navigate_and_return(
                hrefs=demo_links,
                take_screenshot=True,
                extract_data=True,
                delay_between_navigation=1.0
            )
            
            print(f"\nNavigation Results:")
            for result in results:
                if "error" in result:
                    print(f"❌ {result['original_link']['text']}: {result['error']}")
                else:
                    print(f"✅ {result['original_link']['text']} -> {result['page_title']}")
                    print(f"   Screenshot: {result.get('screenshot_path', 'N/A')}")
                    print(f"   Data: {result.get('data_path', 'N/A')}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await crawler.close()


async def example_navigate_product_links():
    """Example: Navigate through product links specifically."""
    print("\n=== Navigate Product Links Example ===")
    
    crawler = TuroCrawler(debug_port=9222)
    
    try:
        if not await crawler.connect_to_browser():
            print("Failed to connect to browser.")
            return
        
        # Navigate through links that contain 'product' in the href
        results = await crawler.navigate_and_return_with_selector(
            selector="a[href*='product']",
            take_screenshot=True,
            extract_data=True,
            delay_between_navigation=1.5,
            max_links=5
        )
        
        print(f"Found and navigated through {len(results)} product links")
        for result in results:
            if "error" not in result:
                print(f"✅ Product: {result['original_link']['text']}")
                print(f"   URL: {result['current_url']}")
                print(f"   Title: {result['page_title']}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await crawler.close()


async def example_navigate_data_testid_links():
    """Example: Navigate through links with specific data-testid attributes."""
    print("\n=== Navigate Data-TestID Links Example ===")
    
    crawler = TuroCrawler(debug_port=9222)
    
    try:
        if not await crawler.connect_to_browser():
            print("Failed to connect to browser.")
            return
        
        # Common data-testid selectors for different types of links
        # 
        data_testid_selectors = [
            # Specific data-testid values
            "a[data-testid=baseTripCard][class=css-14aw0o6-BaseTripCard]",
            #"a[data-testid='item-link']",
            #"a[data-testid='detail-link']",
            #"a[data-testid='view-link']",
            #"a[data-testid='show-link']",
            
            # Partial matches (contains)
            #"a[data-testid*='product']",
            #"a[data-testid*='item']",
            #"a[data-testid*='link']",
            #"a[data-testid*='detail']",
            
            # Starts with
            #"a[data-testid^='product']",
            #"a[data-testid^='item']",
            
            # Ends with
            #"a[data-testid$='-link']",
            #"a[data-testid$='-button']",
            
            # Multiple data attributes
            #"a[data-testid='product-link'][href*='product']",
            #"a[data-testid*='link'][href]",
        ]
        
        for selector in data_testid_selectors:
            print(f"\nTrying selector: {selector}")
            try:
                results = await crawler.navigate_and_return_with_selector(
                    selector=selector,
                    take_screenshot=True,
                    extract_data=False,
                    delay_between_navigation=1.5,
                    customUrlAppend="/receipt",
                    max_links=200  # Limit to 3 links per selector
                )
                
                if results:
                    print(f"  Found {len(results)} links with selector '{selector}'")
                    for result in results:
                        if "error" not in result:
                            print(f"    ✅ {result['original_link']['text']} -> {result['page_title']}")
                            print(f"       URL: {result['current_url']}")
                            print(f"       Data-testid: {result['original_link'].get('dataTestid', 'N/A')}")
                else:
                    print(f"  No links found with selector '{selector}'")
                    
            except Exception as e:
                print(f"  Error with selector '{selector}': {e}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await crawler.close()


async def example_navigate_filtered_links():
    """Example: Navigate through filtered links."""
    print("\n=== Navigate Filtered Links Example ===")
    
    crawler = TuroCrawler(debug_port=9222)
    
    try:
        if not await crawler.connect_to_browser():
            print("Failed to connect to browser.")
            return
        
        # Get links that match a specific pattern (e.g., external links)
        filtered_hrefs = await crawler.get_all_hrefs(filter_pattern=r"https?://[^/]+\.com")
        print(f"Found {len(filtered_hrefs)} external .com links")
        
        if filtered_hrefs:
            # Navigate through first 2 external links
            demo_links = filtered_hrefs[:2]
            results = await crawler.navigate_and_return(
                hrefs=demo_links,
                take_screenshot=True,
                extract_data=True,
                delay_between_navigation=2.0
            )
            
            print(f"\nExternal Link Results:")
            for result in results:
                if "error" in result:
                    print(f"❌ {result['original_link']['text']}: {result['error']}")
                else:
                    print(f"✅ {result['original_link']['text']} -> {result['current_url']}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await crawler.close()


async def example_custom_navigation():
    """Example: Custom navigation with specific requirements."""
    print("\n=== Custom Navigation Example ===")
    
    crawler = TuroCrawler(debug_port=9222)
    
    try:
        if not await crawler.connect_to_browser():
            print("Failed to connect to browser.")
            return
        
        # Get all hrefs
        hrefs = await crawler.get_all_hrefs()
        
        # Filter for specific types of links (custom logic)
        interesting_links = []
        for link in hrefs:
            href = link['href'].lower()
            text = link['text'].lower()
            
            # Look for links that might be interesting
            if any(keyword in href or keyword in text for keyword in [
                'product', 'item', 'detail', 'view', 'show', 'info'
            ]):
                interesting_links.append(link)
        
        print(f"Found {len(interesting_links)} interesting links")
        
        if interesting_links:
            # Navigate through interesting links
            results = await crawler.navigate_and_return(
                hrefs=interesting_links[:3],  # Limit to 3 for demo
                take_screenshot=True,
                extract_data=True,
                delay_between_navigation=1.0
            )
            
            print(f"\nInteresting Links Results:")
            for result in results:
                if "error" not in result:
                    print(f"✅ {result['original_link']['text']}")
                    print(f"   URL: {result['current_url']}")
                    print(f"   Title: {result['page_title']}")
                    
                    # Show some extracted data
                    if 'page_data' in result:
                        data = result['page_data']
                        print(f"   Links on page: {len(data.get('links', []))}")
                        print(f"   Images on page: {len(data.get('images', []))}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await crawler.close()


async def example_specific_data_testid():
    """Example: Navigate through links with a specific data-testid value."""
    print("\n=== Specific Data-TestID Example ===")
    
    crawler = TuroCrawler(debug_port=9222)
    
    try:
        if not await crawler.connect_to_browser():
            print("Failed to connect to browser.")
            return
        
        # Example: Navigate through links with data-testid="product-card-link"
        specific_selector = "a[data-testid='product-card-link']"
        print(f"Looking for links with selector: {specific_selector}")
        
        results = await crawler.navigate_and_return_with_selector(
            selector=specific_selector,
            take_screenshot=True,
            extract_data=True,
            delay_between_navigation=1.0,
            max_links=5
        )
        
        print(f"Found {len(results)} links with data-testid='product-card-link'")
        for result in results:
            if "error" not in result:
                print(f"✅ {result['original_link']['text']}")
                print(f"   URL: {result['current_url']}")
                print(f"   Title: {result['page_title']}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await crawler.close()


async def main():
    """Run all navigation examples."""
    print("Turo Crawler - Navigation Examples")
    print("=" * 40)
    
    # Run different navigation examples
    # await example_navigate_all_links()
    #await example_navigate_product_links()
    await example_navigate_data_testid_links()
    #await example_navigate_filtered_links()
    #await example_custom_navigation()
    #await example_specific_data_testid()
    
    print("\nAll navigation examples completed!")


if __name__ == "__main__":
    asyncio.run(main()) 