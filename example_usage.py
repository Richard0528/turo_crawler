#!/usr/bin/env python3
"""
Example usage of the Turo Crawler with advanced features.
"""

import asyncio
import json
from crawler import TuroCrawler


async def example_basic_crawling():
    """Basic crawling example."""
    print("=== Basic Crawling Example ===")
    
    crawler = TuroCrawler(debug_port=9222)
    
    try:
        # Connect to browser
        if not await crawler.connect_to_browser():
            print("Failed to connect to browser. Make sure Chrome is running with --remote-debugging-port=9222")
            return
        
        # Take screenshot
        screenshot_path = await crawler.take_screenshot("example_screenshot.png")
        print(f"Screenshot saved: {screenshot_path}")
        
        # Get page data
        page_data = await crawler.get_page_data()
        data_path = await crawler.save_page_data(page_data, "example_data.json")
        print(f"Page data saved: {data_path}")
        
        # Print summary
        print(f"\nPage Title: {page_data['title']}")
        print(f"Page URL: {page_data['url']}")
        print(f"Links found: {len(page_data['links'])}")
        print(f"Images found: {len(page_data['images'])}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await crawler.close()


async def example_interactive_crawling():
    """Interactive crawling example with form filling and clicking."""
    print("\n=== Interactive Crawling Example ===")
    
    crawler = TuroCrawler(debug_port=9222)
    
    try:
        if not await crawler.connect_to_browser():
            print("Failed to connect to browser.")
            return
        
        # Wait for page to load
        await asyncio.sleep(2)
        
        # Example: Wait for a search box and fill it
        search_selector = "input[type='search'], input[name='q'], input[name='search'], .search-input"
        if await crawler.wait_for_element(search_selector, timeout=5000):
            print("Found search input, filling with 'example search'")
            await crawler.fill_form({search_selector: "example search"})
            
            # Look for a search button
            search_button_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                ".search-button",
                ".btn-search",
                "button:contains('Search')"
            ]
            
            for selector in search_button_selectors:
                if await crawler.wait_for_element(selector, timeout=2000):
                    print(f"Found search button with selector: {selector}")
                    await crawler.click_element(selector)
                    break
        
        # Execute custom JavaScript to get page metrics
        metrics = await crawler.execute_script("""
            return {
                url: window.location.href,
                title: document.title,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                document: {
                    width: document.documentElement.scrollWidth,
                    height: document.documentElement.scrollHeight
                },
                elements: {
                    links: document.querySelectorAll('a').length,
                    images: document.querySelectorAll('img').length,
                    forms: document.querySelectorAll('form').length,
                    inputs: document.querySelectorAll('input').length
                }
            }
        """)
        
        print(f"\nPage Metrics:")
        print(json.dumps(metrics, indent=2))
        
        # Take screenshot after interactions
        await crawler.take_screenshot("interactive_example.png")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await crawler.close()


async def example_data_extraction():
    """Example of extracting specific data from a page."""
    print("\n=== Data Extraction Example ===")
    
    crawler = TuroCrawler(debug_port=9222)
    
    try:
        if not await crawler.connect_to_browser():
            print("Failed to connect to browser.")
            return
        
        # Extract specific data using JavaScript
        extracted_data = await crawler.execute_script("""
            // Extract all text content from specific elements
            const data = {
                headings: [],
                paragraphs: [],
                lists: [],
                tables: []
            };
            
            // Get all headings
            document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(h => {
                data.headings.push({
                    level: h.tagName.toLowerCase(),
                    text: h.textContent.trim()
                });
            });
            
            // Get all paragraphs
            document.querySelectorAll('p').forEach(p => {
                data.paragraphs.push(p.textContent.trim());
            });
            
            // Get all lists
            document.querySelectorAll('ul, ol').forEach(list => {
                const items = [];
                list.querySelectorAll('li').forEach(li => {
                    items.push(li.textContent.trim());
                });
                data.lists.push({
                    type: list.tagName.toLowerCase(),
                    items: items
                });
            });
            
            // Get all tables
            document.querySelectorAll('table').forEach(table => {
                const rows = [];
                table.querySelectorAll('tr').forEach(tr => {
                    const cells = [];
                    tr.querySelectorAll('td, th').forEach(cell => {
                        cells.push(cell.textContent.trim());
                    });
                    rows.push(cells);
                });
                data.tables.push(rows);
            });
            
            return data;
        """)
        
        print("Extracted Data Summary:")
        print(f"- Headings: {len(extracted_data['headings'])}")
        print(f"- Paragraphs: {len(extracted_data['paragraphs'])}")
        print(f"- Lists: {len(extracted_data['lists'])}")
        print(f"- Tables: {len(extracted_data['tables'])}")
        
        # Save extracted data
        with open("output/data/extracted_content.json", "w") as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)
        print("Extracted data saved to output/data/extracted_content.json")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await crawler.close()


async def main():
    """Run all examples."""
    print("Turo Crawler - Example Usage")
    print("=" * 40)
    
    # Run basic example
    await example_basic_crawling()
    
    # Run interactive example
    await example_interactive_crawling()
    
    # Run data extraction example
    await example_data_extraction()
    
    print("\nAll examples completed!")


if __name__ == "__main__":
    asyncio.run(main()) 