import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

from crawler import TuroCrawler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReceiptProcessor(TuroCrawler):
    """
    Process rental receipts to calculate income for each vehicle owner.
    """
    
    def __init__(self, debug_port: int = 9222, output_dir: str = "output"):
        super().__init__(debug_port, output_dir)
        self.vehicle_owners = {}
        self.rental_data = {}
        self.owner_folders = {}
        
    def load_vehicle_owners(self, vehicle_owners_file: str) -> bool:
        """
        Load vehicle owners data from JSON file.
        
        Args:
            vehicle_owners_file: Path to vehicle owners JSON file
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(vehicle_owners_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.vehicle_owners = data.get('vehicle_owners', {})
            
            logger.info(f"Loaded {len(self.vehicle_owners)} vehicle owners")
            return True
        except Exception as e:
            logger.error(f"Failed to load vehicle owners file: {e}")
            return False
    
    def load_rental_data(self, rental_data_file: str) -> bool:
        """
        Load rental data from JSON file.
        
        Args:
            rental_data_file: Path to rental data JSON file
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(rental_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.rental_data = data.get('rentals', {})
            
            logger.info(f"Loaded rental data for {len(self.rental_data)} vehicles")
            return True
        except Exception as e:
            logger.error(f"Failed to load rental data file: {e}")
            return False
    
    def create_folder_structure(self) -> bool:
        """
        Create folder structure for each owner and their vehicles.
        
        Returns:
            True if created successfully, False otherwise
        """
        try:
            base_dir = self.output_dir / "receipts"
            base_dir.mkdir(exist_ok=True)
            
            for owner_name, license_plates in self.vehicle_owners.items():
                # Create owner folder
                owner_folder = base_dir / owner_name
                owner_folder.mkdir(exist_ok=True)
                self.owner_folders[owner_name] = owner_folder
                
                # Create license plate folders for each vehicle
                for license_plate in license_plates:
                    vehicle_folder = owner_folder / license_plate
                    vehicle_folder.mkdir(exist_ok=True)
                    logger.info(f"Created folder: {vehicle_folder}")
            
            logger.info(f"Created folder structure for {len(self.vehicle_owners)} owners")
            return True
        except Exception as e:
            logger.error(f"Failed to create folder structure: {e}")
            return False
    
    def get_owner_for_license_plate(self, license_plate: str) -> Optional[str]:
        """
        Find the owner for a given license plate.
        
        Args:
            license_plate: License plate to search for
            
        Returns:
            Owner name if found, None otherwise
        """
        for owner_name, plates in self.vehicle_owners.items():
            if license_plate in plates:
                return owner_name
        return None
    
    def extract_cost_details(self, cost_details_html: str) -> Dict[str, float]:
        """
        Extract cost details from the cost-details-section div.
        
        Args:
            cost_details_html: HTML content of the cost details section
            
        Returns:
            Dictionary with cost breakdown
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(cost_details_html, 'html.parser')
        cost_breakdown = {}
        
        # Find the cost-details-section div
        cost_section = soup.find('div', {'data-testid': 'cost-details-section'})
        if not cost_section:
            return cost_breakdown
        
        # Find all first-level child divs (each represents a row)
        row_divs = cost_section.find_all('div', recursive=False)
        
        for row_div in row_divs:
            # Find the two child divs: first is label, second is value
            child_divs = row_div.find_all('div', recursive=False)
            if len(child_divs) >= 2:
                # First div contains the label
                label_div = child_divs[0]
                # Second div contains the value
                value_div = child_divs[1]
                
                # Extract label text
                label_span = label_div.find('span')
                if label_span:
                    label = label_span.get_text(strip=True)
                else:
                    label = label_div.get_text(strip=True)
                
                # Extract value text
                value_span = value_div.find('span')
                if value_span:
                    value_text = value_span.get_text(strip=True)
                else:
                    value_text = value_div.get_text(strip=True)
                
                if label and value_text:
                    # Extract numeric value from the price text
                    # Handle patterns like "$490.00", "- $21.56", "$0.00"
                    numeric_match = re.search(r'[\$]?([\d,]+\.?\d*)', value_text)
                    if numeric_match:
                        numeric_value = float(numeric_match.group(1).replace(',', ''))
                        
                        # Handle negative values (discounts)
                        if '-' in value_text or 'discount' in label.lower():
                            numeric_value = -abs(numeric_value)
                        
                        cost_breakdown[label] = numeric_value
                        logger.debug(f"Extracted: {label} = {numeric_value}")
        
        return cost_breakdown
    
    def calculate_income(self, cost_breakdown: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate income from cost breakdown.
        
        Args:
            cost_breakdown: Dictionary with cost breakdown
            
        Returns:
            Dictionary with calculated income details
        """
        trip_price = cost_breakdown.get('Trip price', 0)
        discounts = sum(value for key, value in cost_breakdown.items() 
                       if 'discount' in key.lower() and value < 0)
        
        # Calculate net amount before Turo fee
        net_amount = trip_price + discounts
        
        # Calculate Turo fee (10%)
        turo_fee = net_amount * 0.10
        
        # Calculate final income
        final_income = net_amount - turo_fee
        
        return {
            'trip_price': trip_price,
            'discounts': discounts,
            'net_amount': net_amount,
            'turo_fee': turo_fee,
            'final_income': final_income
        }
    
    async def process_receipt(self, rental_href: str, vehicle_info: List[str], 
                            owner_name: str, license_plate: str) -> Dict[str, Any]:
        """
        Process a single receipt.
        
        Args:
            rental_href: URL of the rental
            vehicle_info: Vehicle information
            owner_name: Name of the vehicle owner
            license_plate: License plate of the vehicle
            
        Returns:
            Dictionary with receipt processing results
        """
        try:
            # Construct receipt URL
            receipt_url = rental_href + "/receipt"
            logger.info(f"Processing receipt: {receipt_url}")
            
            # Open new tab and navigate to receipt
            new_page = await self.open_new_tab()
            if not new_page:
                raise RuntimeError("Failed to open new tab")
            
            await new_page.goto(receipt_url, wait_until='domcontentloaded')

            # Wait a bit for the page to fully load
            await asyncio.sleep(5)
            
            # Take screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_filename = f"receipt_{timestamp}.png"
            screenshot_path = self.owner_folders[owner_name] / license_plate / screenshot_filename
            
            # Take screenshot of the entire receipt
            await new_page.screenshot(path=str(screenshot_path), full_page=True)
            
            # Extract cost details
            cost_details_html = await new_page.evaluate("""
                () => {
                    const costSection = document.querySelector('div[data-testid="cost-details-section"]');
                    return costSection ? costSection.outerHTML : '';
                }
            """)
            
            if not cost_details_html:
                logger.warning(f"No cost details found for {receipt_url}")
                await new_page.close()
                return {
                    'rental_href': rental_href,
                    'vehicle_info': vehicle_info,
                    'owner': owner_name,
                    'license_plate': license_plate,
                    'screenshot_path': str(screenshot_path),
                    'error': 'No cost details found'
                }
            
            # Extract cost breakdown
            cost_breakdown = self.extract_cost_details(cost_details_html)
            
            # Calculate income
            income_calculation = self.calculate_income(cost_breakdown)
            
            # Save cost details to JSON
            details_filename = f"cost_details_{timestamp}.json"
            details_path = self.owner_folders[owner_name] / license_plate / details_filename
            
            details_data = {
                'rental_href': rental_href,
                'vehicle_info': vehicle_info,
                'owner': owner_name,
                'license_plate': license_plate,
                'timestamp': datetime.now().isoformat(),
                'cost_breakdown': cost_breakdown,
                'income_calculation': income_calculation,
                'screenshot_path': str(screenshot_path)
            }
            
            with open(details_path, 'w', encoding='utf-8') as f:
                json.dump(details_data, f, indent=2, ensure_ascii=False)
            
            await new_page.close()
            
            logger.info(f"Processed receipt for {license_plate}: ${income_calculation['final_income']:.2f}")
            
            return details_data
            
        except Exception as e:
            logger.error(f"Failed to process receipt {rental_href}: {e}")
            return {
                'rental_href': rental_href,
                'vehicle_info': vehicle_info,
                'owner': owner_name,
                'license_plate': license_plate,
                'error': str(e)
            }
    
    async def process_all_receipts(self) -> List[Dict[str, Any]]:
        """
        Process all receipts for all vehicles.
        
        Returns:
            List of processed receipt data
        """
        if not self.vehicle_owners or not self.rental_data:
            logger.error("Vehicle owners or rental data not loaded")
            return []
        
        all_results = []
        
        for vehicle_url, rentals in self.rental_data.items():
            if not rentals:
                continue
                
            # Get vehicle info from first rental
            vehicle_info = rentals[0]['vehicle_info']
            if len(vehicle_info) < 3:
                logger.warning(f"Insufficient vehicle info: {vehicle_info}")
                continue
            
            license_plate = vehicle_info[2]
            owner_name = self.get_owner_for_license_plate(license_plate)
            
            if not owner_name:
                logger.warning(f"No owner found for license plate: {license_plate}")
                continue
            
            logger.info(f"Processing {len(rentals)} receipts for {vehicle_info[0]} ({license_plate}) - Owner: {owner_name}")
            
            for rental in rentals:
                rental_href = rental['rental_href']
                result = await self.process_receipt(rental_href, vehicle_info, owner_name, license_plate)
                all_results.append(result)
                
                # Brief pause between receipts
                await asyncio.sleep(1)
        
        return all_results
    
    def generate_income_table(self, receipt_results: List[Dict[str, Any]]) -> str:
        """
        Generate a summary table of income for all vehicles.
        
        Args:
            receipt_results: List of processed receipt results
            
        Returns:
            Formatted table string
        """
        # Group by owner and license plate
        owner_summary = {}
        
        for result in receipt_results:
            if 'error' in result:
                continue
                
            owner = result['owner']
            license_plate = result['license_plate']
            vehicle_name = result['vehicle_info'][0]
            income = result['income_calculation']['final_income']
            
            if owner not in owner_summary:
                owner_summary[owner] = {}
            
            if license_plate not in owner_summary[owner]:
                owner_summary[owner][license_plate] = {
                    'vehicle_name': vehicle_name,
                    'total_income': 0,
                    'receipt_count': 0
                }
            
            owner_summary[owner][license_plate]['total_income'] += income
            owner_summary[owner][license_plate]['receipt_count'] += 1
        
        # Generate table
        table_lines = []
        table_lines.append("=" * 100)
        table_lines.append("RENTAL INCOME SUMMARY")
        table_lines.append("=" * 100)
        table_lines.append(f"{'Owner':<15} {'License':<10} {'Vehicle':<25} {'Receipts':<10} {'Total Income':<15}")
        table_lines.append("-" * 100)
        
        grand_total = 0
        
        for owner, vehicles in owner_summary.items():
            owner_total = 0
            for license_plate, data in vehicles.items():
                income = data['total_income']
                owner_total += income
                grand_total += income
                
                table_lines.append(
                    f"{owner:<15} {license_plate:<10} {data['vehicle_name']:<25} "
                    f"{data['receipt_count']:<10} ${income:>13,.2f}"
                )
            
            table_lines.append(f"{'':<15} {'':<10} {'':<25} {'':<10} {'':<15}")
            table_lines.append(f"{owner} TOTAL:{'':<10} {'':<25} {'':<10} ${owner_total:>13,.2f}")
            table_lines.append("-" * 100)
        
        table_lines.append(f"{'GRAND TOTAL':<15} {'':<10} {'':<25} {'':<10} ${grand_total:>13,.2f}")
        table_lines.append("=" * 100)
        
        return "\n".join(table_lines)
    
    async def save_summary_report(self, receipt_results: List[Dict[str, Any]], filename: Optional[str] = None) -> str:
        """
        Save a summary report of all processed receipts.
        
        Args:
            receipt_results: List of processed receipt results
            filename: Optional filename for the report
            
        Returns:
            Path to the saved report
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"receipt_summary_{timestamp}.json"
        
        report_path = self.output_dir / "data" / filename
        
        # Calculate summary statistics
        total_receipts = len(receipt_results)
        successful_receipts = len([r for r in receipt_results if 'error' not in r])
        failed_receipts = total_receipts - successful_receipts
        
        total_income = sum(
            r['income_calculation']['final_income'] 
            for r in receipt_results 
            if 'error' not in r
        )
        
        summary_data = {
            'timestamp': datetime.now().isoformat(),
            'total_receipts': total_receipts,
            'successful_receipts': successful_receipts,
            'failed_receipts': failed_receipts,
            'total_income': total_income,
            'receipts': receipt_results
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Summary report saved: {report_path}")
        return str(report_path)


async def main():
    """Main function to process rental receipts."""
    
    processor = ReceiptProcessor(debug_port=9222)
    
    try:
        # Load data files
        vehicle_owners_file = "output/data/vehicle_owners.json"
        rental_data_file = "output/data/rentals_Jun_20250722_194649.json"
        
        if not processor.load_vehicle_owners(vehicle_owners_file):
            logger.error("Failed to load vehicle owners file")
            return
        
        if not processor.load_rental_data(rental_data_file):
            logger.error("Failed to load rental data file")
            return
        
        # Create folder structure
        if not processor.create_folder_structure():
            logger.error("Failed to create folder structure")
            return
        
        # Connect to browser
        logger.info("Attempting to connect to Chrome browser...")
        if not await processor.connect_to_browser():
            logger.error("Failed to connect to browser. Make sure Chrome is running with --remote-debugging-port=9222")
            return
        
        # Process all receipts
        logger.info("Starting receipt processing...")
        receipt_results = await processor.process_all_receipts()
        
        # Generate and display summary table
        summary_table = processor.generate_income_table(receipt_results)
        print("\n" + summary_table)
        
        # Save summary report
        report_path = await processor.save_summary_report(receipt_results)
        print(f"\nSummary report saved to: {report_path}")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        await processor.close()


if __name__ == "__main__":
    asyncio.run(main()) 