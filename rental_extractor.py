#!/usr/bin/env python3
"""
Rental Extractor - Extracts rental information from Turo vehicle rental pages.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import re

from crawler import TuroCrawler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RentalExtractor(TuroCrawler):
    """
    Extracts rental information from Turo vehicle rental pages.
    """
    
    def __init__(self, debug_port: int = 9222, output_dir: str = "output"):
        super().__init__(debug_port, output_dir)
        self.rental_data = {}
        self.target_month = None
        
    def set_target_month(self, month: str):
        """
        Set the target month for filtering rentals.
        
        Args:
            month: Month name (e.g., "Jul", "Aug", "Dec")
        """
        self.target_month = month
        logger.info(f"Target month set to: {month}")
    
    def parse_date_range(self, date_text: str) -> Optional[Dict[str, str]]:
        """
        Parse date range text like "Jul 3 - Jul 13" into start and end dates.
        
        Args:
            date_text: Date range text
            
        Returns:
            Dictionary with start_date and end_date, or None if parsing fails
        """
        try:
            # Pattern to match "Jul 3 - Jul 13" or "Jul 3 - Aug 5"
            pattern = r'(\w{3})\s+(\d{1,2})\s*-\s*(\w{3})\s+(\d{1,2})'
            match = re.match(pattern, date_text.strip())
            
            if match:
                start_month, start_day, end_month, end_day = match.groups()
                return {
                    "start_date": f"{start_month} {start_day}",
                    "end_date": f"{end_month} {end_day}",
                    "end_month": end_month
                }
            return None
        except Exception as e:
            logger.error(f"Failed to parse date range '{date_text}': {e}")
            return None
    
    def is_rental_in_target_month(self, date_info: Dict[str, str]) -> bool:
        """
        Check if rental ends in the target month.
        
        Args:
            date_info: Parsed date information
            
        Returns:
            True if rental ends in target month
        """
        if not self.target_month or not date_info:
            return False
        
        return date_info.get("end_month") == self.target_month
    
    async def extract_rentals_from_page(self, vehicle_url: str) -> List[Dict[str, Any]]:
        """
        Extract rental information from a vehicle's rental page.
        
        Args:
            vehicle_url: URL of the vehicle's rental page
            
        Returns:
            List of rental information dictionaries
        """
        if not self.page:
            raise RuntimeError("No page connected. Call connect_to_browser() first.")
        
        try:
            # Navigate to the rental page
            rental_url = f"{vehicle_url}/rentals"
            logger.info(f"Navigating to rental page: {rental_url}")

            new_page = await self.open_new_tab()
            
            await new_page.goto(rental_url, wait_until='networkidle')
            await asyncio.sleep(2)  # Wait for content to load
            
            # Extract rental information using JavaScript
            rentals = await new_page.evaluate("""
                () => {
                    const rentals = [];
                    
                    // Find all rental links
                    const rentalLinks = document.querySelectorAll('a.css-kigjj2-linkStyles');
                    
                    rentalLinks.forEach((link, index) => {
                        const href = link.href;
                        
                        // Find the date element within this link
                        const dateElement = link.querySelector('p.css-19geuym-ActivityDates-ActivityDates-getTitleMessageDatesStyles');
                        
                        if (dateElement) {
                            const dateText = dateElement.textContent.trim();
                            
                            // Extract additional information if available
                            const tripNameElement = link.querySelector('p.css-n9k3tg-StyledText');
                            const vehicleNameElement = link.querySelector('p.css-ap2irb-StyledText');
                            
                            const rentalInfo = {
                                href: href,
                                date_text: dateText,
                                trip_name: tripNameElement ? tripNameElement.textContent.trim() : '',
                                vehicle_name: vehicleNameElement ? vehicleNameElement.textContent.trim() : ''
                            };
                            
                            rentals.push(rentalInfo);
                        }
                    });
                    
                    return rentals;
                }
            """)
            
            logger.info(f"Found {len(rentals)} rentals on page")
            await new_page.close()
            return rentals
            
        except Exception as e:
            logger.error(f"Failed to extract rentals from {vehicle_url}: {e}")
            return []
    
    async def process_vehicle_rentals(self, vehicle_url: str, vehicle_info: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Process rentals for a single vehicle.
        
        Args:
            vehicle_url: URL of the vehicle
            vehicle_info: List of vehicle details
            
        Returns:
            Dictionary with vehicle_url as key and list of rental information as value
        """
        try:
            # Extract all rentals from the page
            all_rentals = await self.extract_rentals_from_page(vehicle_url)
            
            # Filter rentals by target month
            matching_rentals = []
            
            for rental in all_rentals:
                date_info = self.parse_date_range(rental['date_text'])
                
                if date_info and self.is_rental_in_target_month(date_info):
                    matching_rental = {
                        "vehicle_info": vehicle_info,
                        "rental_href": rental['href'],
                        "parsed_dates": date_info
                    }
                    matching_rentals.append(matching_rental)
            
            logger.info(f"Found {len(matching_rentals)} rentals in target month for vehicle")
            return {vehicle_url: matching_rentals}
            
        except Exception as e:
            logger.error(f"Failed to process rentals for {vehicle_url}: {e}")
            return {}
    
    async def process_all_vehicles(self, vehicle_listings_file: str, vehicle_owners_file: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Process all vehicles from the JSON file and extract matching rentals.
        Only processes vehicles whose license plates are in the vehicle_owners.json file.
        
        Args:
            vehicle_listings_file: Path to the vehicle listings JSON file
            vehicle_owners_file: Path to the vehicle owners JSON file
            
        Returns:
            Dictionary with vehicle_url as key and list of rental information as value
        """
        if not self.target_month:
            raise ValueError("Target month not set. Call set_target_month() first.")
        
        # Load vehicle listings
        try:
            with open(vehicle_listings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                vehicles = data.get('vehicles', {})

            with open(vehicle_owners_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                vehicle_owners = data.get('vehicle_owners', {})
        except Exception as e:
            logger.error(f"Failed to load vehicle listings file: {e}")
            return {}
        
        # Create a set of all license plates from vehicle_owners.json
        allowed_license_plates = set()
        for owner, plates in vehicle_owners.items():
            allowed_license_plates.update(plates)
        
        logger.info(f"Found {len(allowed_license_plates)} license plates in vehicle_owners.json")
        logger.info(f"Processing {len(vehicles)} vehicles for rentals in {self.target_month}")
        
        # Filter vehicles based on license plates
        filtered_vehicles = {}
        for vehicle_url, vehicle_info in vehicles.items():
            if len(vehicle_info) >= 3:  # Ensure we have at least 3 items (license plate is 3rd)
                license_plate = vehicle_info[2]  # Third item is the license plate
                if license_plate in allowed_license_plates:
                    filtered_vehicles[vehicle_url] = vehicle_info
                    logger.info(f"Vehicle {vehicle_info[0]} with license plate {license_plate} is in owners list")
                else:
                    logger.debug(f"Skipping vehicle {vehicle_info[0]} with license plate {license_plate} - not in owners list")
            else:
                logger.warning(f"Skipping vehicle with insufficient info: {vehicle_info}")
        
        logger.info(f"Filtered to {len(filtered_vehicles)} vehicles that are in the owners list")
        
        all_matching_rentals = {}
        
        for i, (vehicle_url, vehicle_info) in enumerate(filtered_vehicles.items()):
            try:
                logger.info(f"Processing vehicle {i+1}/{len(filtered_vehicles)}: {vehicle_info[0] if vehicle_info else 'Unknown'} (License: {vehicle_info[2] if len(vehicle_info) >= 3 else 'Unknown'})")
                
                vehicle_rentals = await self.process_vehicle_rentals(vehicle_url, vehicle_info)
                all_matching_rentals.update(vehicle_rentals)
                
                # Brief pause between vehicles
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to process vehicle {vehicle_url}: {e}")
                continue
        
        total_rentals = sum(len(rentals) for rentals in all_matching_rentals.values())
        logger.info(f"Total matching rentals found: {total_rentals} across {len(all_matching_rentals)} vehicles")
        return all_matching_rentals
    
    async def save_rental_data(self, rental_data: Dict[str, List[Dict[str, Any]]], filename: Optional[str] = None) -> str:
        """
        Save rental data to a JSON file.
        
        Args:
            rental_data: Dictionary with vehicle_url as key and list of rental information as value
            filename: Optional filename for the data file
            
        Returns:
            Path to the saved data file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rentals_{self.target_month}_{timestamp}.json"
        
        data_path = self.output_dir / "data" / filename
        
        # Calculate total rentals
        total_rentals = sum(len(rentals) for rentals in rental_data.values())
        
        # Prepare data for saving
        save_data = {
            "target_month": self.target_month,
            "timestamp": datetime.now().isoformat(),
            "total_vehicles": len(rental_data),
            "total_rentals": total_rentals,
            "rentals": rental_data
        }
        
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Rental data saved: {data_path}")
        return str(data_path)


async def main():
    """Main function to demonstrate the rental extractor."""
    
    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python rental_extractor.py <month>")
        print("Example: python rental_extractor.py Jul")
        print("Valid months: Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec")
        return
    
    target_month = sys.argv[1]
    
    # Validate month format
    valid_months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    if target_month not in valid_months:
        print(f"Invalid month: {target_month}")
        print("Valid months:", ", ".join(valid_months))
        return
    
    extractor = RentalExtractor(debug_port=9222)
    
    try:
        # Set target month
        extractor.set_target_month(target_month)
        
        # Connect to the browser
        logger.info("Attempting to connect to Chrome browser...")
        if not await extractor.connect_to_browser():
            logger.error("Failed to connect to browser. Make sure Chrome is running with --remote-debugging-port=9222")
            return
        
        # Process all vehicles
        vehicle_listings_file = "output/data/vehicle_listings.json"
        
        if not Path(vehicle_listings_file).exists():
            logger.error(f"Vehicle listings file not found: {vehicle_listings_file}")
            logger.info("Please run the vehicle extractor first to generate vehicle_listings.json")
            return

        vehicle_owners_file = "output/data/vehicle_owners.json"
        
        if not Path(vehicle_owners_file).exists():
            logger.error(f"Vehicle owners file not found: {vehicle_owners_file}")
            logger.info("Please run the vehicle extractor first to generate vehicle_owners.json")
            return
        
        # Extract rental data
        rental_data = await extractor.process_all_vehicles(vehicle_listings_file, vehicle_owners_file)
        
        if rental_data:
            total_rentals = sum(len(rentals) for rentals in rental_data.values())
            print(f"\nFound {total_rentals} rentals ending in {target_month} across {len(rental_data)} vehicles:")
            
            for vehicle_url, rentals in rental_data.items():
                vehicle_name = rentals[0]['vehicle_info'][0] if rentals else 'Unknown'
                license_plate = rentals[0]['vehicle_info'][2] if rentals and len(rentals[0]['vehicle_info']) >= 3 else 'Unknown'
                print(f"\nVehicle: {vehicle_name} (License: {license_plate})")
                print(f"  Vehicle URL: {vehicle_url}")
                for rental in rentals:
                    print(f"  Rental URL: {rental['rental_href']}")
                    print(f"  End Date: {rental['parsed_dates']['end_date']}")
            
            # Save the data
            data_path = await extractor.save_rental_data(rental_data)
            print(f"\nRental data saved to: {data_path}")
        else:
            print(f"No rentals found ending in {target_month}")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        await extractor.close()


if __name__ == "__main__":
    asyncio.run(main()) 