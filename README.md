# Turo Crawler

A web crawler using Playwright and Chrome DevTools Protocol (CDP) to connect to Chrome browser instances with remote debugging enabled.

## Features

- Connect to existing Chrome browser instances with remote debugging
- Take full-page screenshots
- Extract comprehensive page data (links, images, meta tags, text content)
- Execute custom JavaScript on pages
- Wait for and interact with page elements
- Fill forms automatically
- Save data in structured JSON format

## Prerequisites

- Python 3.9 or higher
- Google Chrome browser
- macOS or Linux (Windows support can be added)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd turo_crawler
```

2. Install dependencies:
```bash
pip install -e .
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

## Usage

### Step 1: Start Chrome with Remote Debugging

First, start Chrome with remote debugging enabled on port 9222:

**Option A: Using the provided script**
```bash
./script/start_chrome.sh
```

**Option B: Manual command**
```bash
# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9222 \
    --user-data-dir=/tmp/chrome-debug \
    --no-first-run \
    --no-default-browser-check

# Linux
google-chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=/tmp/chrome-debug \
    --no-first-run \
    --no-default-browser-check
```

### Step 2: Load a Website

Once Chrome is running, navigate to the website you want to crawl. The crawler will connect to whatever page is currently loaded.

### Step 3: Run the Crawler

```bash
python main.py
```

The crawler will:
1. Connect to the Chrome browser instance
2. Take a screenshot of the current page
3. Extract and save page data
4. Display basic information about the page

## Output

The crawler creates an `output` directory with the following structure:

```
output/
├── screenshots/
│   └── screenshot_YYYYMMDD_HHMMSS.png
└── data/
    └── page_data_YYYYMMDD_HHMMSS.json
```

### Screenshots
- Full-page screenshots saved as PNG files
- Timestamped filenames for easy identification

### Page Data (JSON)
- Page URL and title
- Meta tags
- All links with text and href
- Image information (src, alt, title)
- Clean text content (without scripts and styles)
- Timestamp of extraction

## Advanced Usage

### Custom Script Example

```python
import asyncio
from main import TuroCrawler

async def custom_crawler():
    crawler = TuroCrawler(debug_port=9222)
    
    # Connect to browser
    if await crawler.connect_to_browser():
        # Wait for a specific element
        await crawler.wait_for_element(".search-button", timeout=5000)
        
        # Click an element
        await crawler.click_element(".search-button")
        
        # Fill a form
        form_data = {
            "input[name='search']": "your search term",
            "input[name='email']": "your@email.com"
        }
        await crawler.fill_form(form_data)
        
        # Execute custom JavaScript
        result = await crawler.execute_script("""
            return {
                pageHeight: document.body.scrollHeight,
                pageWidth: document.body.scrollWidth,
                userAgent: navigator.userAgent
            }
        """)
        print(f"Page dimensions: {result}")
        
        # Take screenshot and get data
        await crawler.take_screenshot("custom_screenshot.png")
        data = await crawler.get_page_data()
        await crawler.save_page_data(data, "custom_data.json")
        
        await crawler.close()

# Run the custom crawler
asyncio.run(custom_crawler())
```

### Available Methods

- `connect_to_browser()`: Connect to Chrome browser
- `take_screenshot(filename)`: Take a screenshot
- `get_page_data()`: Extract page data
- `save_page_data(data, filename)`: Save data to JSON
- `execute_script(script)`: Run JavaScript
- `wait_for_element(selector, timeout)`: Wait for element
- `click_element(selector)`: Click an element
- `fill_form(form_data)`: Fill form fields
- `close()`: Close browser connection

## Configuration

You can customize the crawler by modifying the `TuroCrawler` class initialization:

```python
crawler = TuroCrawler(
    debug_port=9222,      # Chrome debug port
    output_dir="output"   # Output directory
)
```

## Troubleshooting

### Connection Issues
- Make sure Chrome is running with `--remote-debugging-port=9222`
- Check that the port 9222 is not blocked by firewall
- Verify Chrome is not running in incognito mode

### Permission Issues
- Make sure the script has execute permissions: `chmod +x script/start_chrome.sh`
- Check that the output directory is writable

### Browser Not Found
- Ensure Chrome is installed and accessible
- On macOS, the default path is `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- On Linux, make sure `google-chrome` is in your PATH

## Dependencies

- `playwright`: Browser automation
- `requests`: HTTP requests for CDP connection
- `beautifulsoup4`: HTML parsing
- `lxml`: XML/HTML parser
- `pillow`: Image processing
- `python-dotenv`: Environment variable management

## License

This project is licensed under the MIT License.
