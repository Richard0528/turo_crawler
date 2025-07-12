import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import requests
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TuroCrawler:
    """
    A web crawler that connects to Chrome browser instances with remote debugging enabled.
    """
    
    def __init__(self, debug_port: int = 9222, output_dir: str = "output"):
        """
        Initialize the crawler.
        
        Args:
            debug_port: The port where Chrome is running with remote debugging
            output_dir: Directory to save screenshots and data
        """
        self.debug_port = debug_port
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.output_dir / "screenshots").mkdir(exist_ok=True)
        (self.output_dir / "data").mkdir(exist_ok=True)
        
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    async def connect_to_browser(self) -> bool:
        """
        Connect to the Chrome browser instance running with remote debugging.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Get the list of available targets from Chrome DevTools Protocol
            response = requests.get(f"http://localhost:{self.debug_port}/json")
            if response.status_code != 200:
                logger.error(f"Failed to connect to Chrome on port {self.debug_port}")
                return False
                
            targets = response.json()
            logger.info(f"Found {len(targets)} targets in Chrome")
            
            # Find the main page target
            main_target = None
            for target in targets:
                if target.get("type") == "page" and target.get("url") != "about:blank":
                    main_target = target
                    break
            
            if not main_target:
                logger.error("No main page target found")
                return False
                
            logger.info(f"Connecting to target: {main_target.get('title', 'Unknown')}")
            
            # Connect using Playwright with CDP
            playwright = await async_playwright().start()
            
            # Connect to the existing browser
            self.browser = await playwright.chromium.connect_over_cdp(
                f"http://localhost:{self.debug_port}"
            )
            
            # Get the context and page
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
                pages = self.context.pages
                if pages:
                    self.page = pages[0]
                    logger.info(f"Successfully connected to page: {self.page.url}")
                    return True
                else:
                    logger.error("No pages found in the browser context")
                    return False
            else:
                logger.error("No browser contexts found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to browser: {e}")
            return False
    
    async def get_all_hrefs(self, filter_pattern: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Get all href links from the current page.
        
        Args:
            filter_pattern: Optional regex pattern to filter hrefs
            
        Returns:
            List of dictionaries containing link information
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        # Get all hrefs using JavaScript
        hrefs = await self.page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.map(link => ({
                    text: link.textContent.trim(),
                    href: link.href,
                    title: link.title || '',
                    className: link.className || '',
                    id: link.id || '',
                    dataTestid: link.getAttribute('data-testid') || '',
                    dataTestId: link.getAttribute('data-testId') || '',
                    dataTestID: link.getAttribute('data-testID') || ''
                }));
            }
        """)
        
        # Filter hrefs if pattern provided
        if filter_pattern:
            import re
            pattern = re.compile(filter_pattern)
            hrefs = [link for link in hrefs if pattern.search(link['href'])]
        
        logger.info(f"Found {len(hrefs)} hrefs on the page")
        return hrefs
    
    async def navigate_and_return(self, hrefs: List[Dict[str, str]], 
                                 take_screenshot: bool = True,
                                 extract_data: bool = True,
                                 delay_between_navigation: float = 1.0) -> List[Dict[str, Any]]:
        """
        Navigate to each href in the list and return to the original page after each navigation.
        
        Args:
            hrefs: List of href dictionaries from get_all_hrefs()
            take_screenshot: Whether to take screenshots of each page
            extract_data: Whether to extract data from each page
            delay_between_navigation: Delay in seconds between navigations
            
        Returns:
            List of dictionaries containing results from each navigation
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        original_url = self.page.url
        results = []
        
        logger.info(f"Starting navigation through {len(hrefs)} hrefs")
        
        for i, link_info in enumerate(hrefs):
            try:
                href = link_info['href']
                link_text = link_info['text']
                
                logger.info(f"Navigating to {i+1}/{len(hrefs)}: {link_text} -> {href}")
                
                # Navigate to the href
                await self.page.goto(href, wait_until='networkidle')
                
                # Wait a bit for the page to fully load
                await asyncio.sleep(delay_between_navigation)
                
                # Prepare result for this navigation
                result = {
                    "index": i,
                    "original_link": link_info,
                    "current_url": self.page.url,
                    "page_title": await self.page.title(),
                    "timestamp": datetime.now().isoformat()
                }
                
                # Take screenshot if requested
                if take_screenshot:
                    screenshot_filename = f"navigation_{i+1:03d}_{link_text[:30].replace(' ', '_')}.png"
                    screenshot_path = await self.take_screenshot(screenshot_filename)
                    result["screenshot_path"] = screenshot_path
                
                # Extract data if requested
                if extract_data:
                    page_data = await self.get_page_data()
                    data_filename = f"navigation_{i+1:03d}_{link_text[:30].replace(' ', '_')}.json"
                    data_path = await self.save_page_data(page_data, data_filename)
                    result["data_path"] = data_path
                    result["page_data"] = page_data
                
                results.append(result)
                logger.info(f"Successfully processed {i+1}/{len(hrefs)}")
                
            except Exception as e:
                logger.error(f"Failed to navigate to {href}: {e}")
                results.append({
                    "index": i,
                    "original_link": link_info,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            
            # Go back to the original page
            try:
                await self.page.goto(original_url, wait_until='networkidle')
                await asyncio.sleep(0.5)  # Brief pause after going back
                logger.info(f"Returned to original page: {original_url}")
            except Exception as e:
                logger.error(f"Failed to return to original page: {e}")
                # Try to reconnect if we lost connection
                if not await self.connect_to_browser():
                    logger.error("Failed to reconnect to browser, stopping navigation")
                    break
        
        logger.info(f"Completed navigation through {len(hrefs)} hrefs")
        return results
    
    async def navigate_and_return_with_selector(self, selector: str,
                                              take_screenshot: bool = True,
                                              extract_data: bool = True,
                                              delay_between_navigation: float = 1.0,
                                              max_links: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Navigate through all hrefs found by a specific selector and return after each navigation.
        
        Args:
            selector: CSS selector to find links (e.g., '.product-link', 'a[href*="product"]')
            take_screenshot: Whether to take screenshots of each page
            extract_data: Whether to extract data from each page
            delay_between_navigation: Delay in seconds between navigations
            max_links: Maximum number of links to process (None for all)
            
        Returns:
            List of dictionaries containing results from each navigation
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        # Get hrefs using the selector
        hrefs = await self.page.evaluate(f"""
            () => {{
                const links = Array.from(document.querySelectorAll('{selector}'));
                return links.map(link => ({{
                    text: link.textContent.trim(),
                    href: link.href,
                    title: link.title || '',
                    className: link.className || '',
                    id: link.id || '',
                    dataTestid: link.getAttribute('data-testid') || ''
                }}));
            }}
        """)
        
        if max_links:
            hrefs = hrefs[:max_links]
        
        logger.info(f"Found {len(hrefs)} hrefs matching selector: {selector}")
        
        return await self.navigate_and_return(hrefs, take_screenshot, extract_data, delay_between_navigation)
    
    async def take_screenshot(self, filename: Optional[str] = None) -> str:
        """
        Take a screenshot of the current page.
        
        Args:
            filename: Optional filename for the screenshot
            
        Returns:
            Path to the saved screenshot
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
        
        screenshot_path = self.output_dir / "screenshots" / filename
        
        # Take screenshot
        await self.page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"Screenshot saved: {screenshot_path}")
        
        return str(screenshot_path)
    
    async def get_page_data(self) -> Dict[str, Any]:
        """
        Extract data from the current page.
        
        Returns:
            Dictionary containing page data
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        # Get page content
        content = await self.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract basic page information
        page_data = {
            "url": self.page.url,
            "title": await self.page.title(),
            "timestamp": datetime.now().isoformat(),
            "meta_tags": {},
            "links": [],
            "text_content": "",
            "images": []
        }
        
        # Extract meta tags
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content:
                page_data["meta_tags"][name] = content
        
        # Extract links
        for link in soup.find_all("a", href=True):
            page_data["links"].append({
                "text": link.get_text(strip=True),
                "href": link["href"],
                "title": link.get("title", "")
            })
        
        # Extract text content (excluding scripts and styles)
        for script in soup(["script", "style"]):
            script.decompose()
        page_data["text_content"] = soup.get_text(separator=" ", strip=True)
        
        # Extract images
        for img in soup.find_all("img"):
            page_data["images"].append({
                "src": img.get("src", ""),
                "alt": img.get("alt", ""),
                "title": img.get("title", "")
            })
        
        return page_data
    
    async def save_page_data(self, data: Dict[str, Any], filename: Optional[str] = None) -> str:
        """
        Save page data to a JSON file.
        
        Args:
            data: Page data to save
            filename: Optional filename for the data file
            
        Returns:
            Path to the saved data file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"page_data_{timestamp}.json"
        
        data_path = self.output_dir / "data" / filename
        
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Page data saved: {data_path}")
        return str(data_path)
    
    async def execute_script(self, script: str) -> Any:
        """
        Execute JavaScript in the current page.
        
        Args:
            script: JavaScript code to execute
            
        Returns:
            Result of the script execution
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        return await self.page.evaluate(script)
    
    async def wait_for_element(self, selector: str, timeout: int = 30000) -> bool:
        """
        Wait for an element to appear on the page.
        
        Args:
            selector: CSS selector for the element
            timeout: Timeout in milliseconds
            
        Returns:
            True if element found, False if timeout
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"Element {selector} not found within {timeout}ms: {e}")
            return False
    
    async def click_element(self, selector: str) -> bool:
        """
        Click an element on the page.
        
        Args:
            selector: CSS selector for the element
            
        Returns:
            True if click successful, False otherwise
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        try:
            await self.page.click(selector)
            return True
        except Exception as e:
            logger.error(f"Failed to click element {selector}: {e}")
            return False
    
    async def fill_form(self, form_data: Dict[str, str]) -> bool:
        """
        Fill form fields on the page.
        
        Args:
            form_data: Dictionary mapping selectors to values
            
        Returns:
            True if form filling successful, False otherwise
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        try:
            for selector, value in form_data.items():
                await self.page.fill(selector, value)
            return True
        except Exception as e:
            logger.error(f"Failed to fill form: {e}")
            return False
    
    async def close(self):
        """Close the browser connection."""
        if self.browser:
            await self.browser.close()
            logger.info("Browser connection closed")