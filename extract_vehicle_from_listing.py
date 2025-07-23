#!/usr/bin/env python3
"""
Turo Vehicle Extractor - Specialized crawler for extracting vehicle listing information from Turo pages.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from crawler import TuroCrawler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TuroVehicleExtractor(TuroCrawler):
    """
    Specialized crawler for extracting vehicle listing information from Turo pages.
    """
    def __init__(self, debug_port: int = 9222, output_dir: str = "output"):
        super().__init__(debug_port, output_dir)
        self.vehicle_data = {}
    
    async def extract_vehicle_listings(self) -> Dict[str, List[str]]:
        """
        Extract vehicle listing information from the current page.
        
        Returns:
            Dictionary with href as key and list of details as value
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        try:
            # Extract vehicle listing information using JavaScript
            vehicle_data = await self.page.evaluate("""
                () => {
                    const vehicles = {};
                    
                    // Find all vehicle listing cards
                    const vehicleCards = document.querySelectorAll('a[data-testid=vehicle-listing-details-card]');
                    
                    vehicleCards.forEach((card, index) => {
                        const href = card.href;
                        const details = [];
                        
                        // Extract main title (vehicle name and year)
                        const mainTitleElement = card.querySelector('p.css-1s9awq7-StyledText');
                        if (mainTitleElement) {
                            const title = mainTitleElement.getAttribute('title') || mainTitleElement.textContent.trim();
                            if (title) {
                                details.push(`${title}`);
                            }
                        }
                        
                        // Extract subtitle details (trim and license plate)
                        const subtitleElements = card.querySelectorAll('p.css-1u90aiw-StyledText-VehicleDetailsCard');
                        const subtitle1 = subtitleElements[0].getAttribute('title');
                        details.push(`${subtitle1}`);
                        const subtitle2 = subtitleElements[1].getAttribute('title');
                        details.push(`${subtitle2}`);
                        
                        // Only add if we have details
                        if (details.length > 0) {
                            vehicles[href] = details;
                        }
                    });
                    
                    return vehicles;
                }
            """)
            
            self.vehicle_data = vehicle_data
            logger.info(f"Extracted {len(vehicle_data)} vehicle listings")
            return vehicle_data
            
        except Exception as e:
            logger.error(f"Failed to extract vehicle listings: {e}")
            return {}
    
    async def save_vehicle_data(self, filename: Optional[str] = None) -> str:
        """
        Save extracted vehicle data to a JSON file.
        
        Args:
            filename: Optional filename for the data file
            
        Returns:
            Path to the saved data file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"vehicle_listings.json"
        
        data_path = self.output_dir / "data" / filename
        
        # Prepare data for saving
        save_data = {
            "timestamp": datetime.now().isoformat(),
            "total_vehicles": len(self.vehicle_data),
            "vehicles": self.vehicle_data
        }
        
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Vehicle data saved: {data_path}")
        return str(data_path)

async def main():
    """Main function to demonstrate the vehicle extractor."""
    extractor = TuroVehicleExtractor(debug_port=9222)
    
    try:
        # Connect to the browser
        logger.info("Attempting to connect to Chrome browser...")
        if not await extractor.connect_to_browser():
            logger.error("Failed to connect to browser. Make sure Chrome is running with --remote-debugging-port=9222")
            return
        
        # Wait for page to load
        await asyncio.sleep(2)
        
        # Extract vehicle listings from current page
        logger.info("Extracting vehicle listings from current page...")
        vehicle_data = await extractor.extract_vehicle_listings()
        
        if vehicle_data:
            print(f"\nFound {len(vehicle_data)} vehicle listings:")
            for href, details in vehicle_data.items():
                print(f"\nVehicle: {href}")
                for detail in details:
                    print(f"  {detail}")
            
            # Save the data
            data_path = await extractor.save_vehicle_data()
            print(f"\nVehicle data saved to: {data_path}")
        else:
            print("No vehicle listings found on the current page.")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        await extractor.close()


if __name__ == "__main__":
    asyncio.run(main()) 