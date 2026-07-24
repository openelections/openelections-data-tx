#!/usr/bin/env python3
"""
Hunt County TX Election Results Parser (Fixed Version)
Converts precinct-level election results from Excel format to CSV
Fixed to properly parse precinct names with non-numeric characters
"""

import pandas as pd
import re
import csv
import sys
from typing import List, Dict, Any, Optional, Tuple

def clean_numeric(value: Any) -> int:
    """Convert various numeric formats to integers"""
    if pd.isna(value) or value == '' or value is None:
        return 0
    if isinstance(value, (int, float)):
        # Additional check for NaN in case pd.isna doesn't catch it
        if pd.isna(value):
            return 0
        return int(value)
    if isinstance(value, str):
        # Remove commas and convert to int
        cleaned = re.sub(r'[,\s]', '', str(value))
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0
    return 0

def extract_precinct_info(sheet_data: List[List], sheet_name: str) -> Tuple[Optional[str], int, int]:
    """Extract precinct number, registered voters, and ballots cast from sheet"""
    precinct_num = None
    registered_voters = 0
    ballots_cast = 0
    
    print(f"    DEBUG: Processing sheet '{sheet_name}'")
    
    # First, check cell A25 specifically as mentioned in the issue
    if len(sheet_data) > 24 and sheet_data[24]:  # Row 25 is index 24
        cell_a25 = sheet_data[24][0] if len(sheet_data[24]) > 0 else None
        if cell_a25 and not pd.isna(cell_a25):
            cell_a25_str = str(cell_a25).strip()
            print(f"    DEBUG: Cell A25 contains: '{cell_a25_str}'")
            
            # Accept the full content of A25 as the precinct name
            # This will handle both simple numbers like "1" and compound names like "1 - Clyde"
            if cell_a25_str and cell_a25_str.lower() not in ['choice', 'votes', 'total', 'cast', 'over', 'under', 'registered', 'ballots']:
                precinct_num = cell_a25_str
                print(f"    DEBUG: Found precinct number in A25: '{precinct_num}'")
    
    # If A25 didn't contain a precinct number, try to extract from sheet name as fallback
    if not precinct_num:
        sheet_precinct_match = re.search(r'(?:precinct|pct|p)[-_\s]*([a-zA-Z0-9\s\-]+)', sheet_name, re.IGNORECASE)
        if sheet_precinct_match:
            potential_precinct = sheet_precinct_match.group(1).strip()
            print(f"    DEBUG: Found potential precinct in sheet name: '{potential_precinct}'")
            # Clean up common patterns
            if potential_precinct.lower() not in ['map', 'summary', 'total', 'index']:
                precinct_num = potential_precinct
    
    # If still no precinct from sheet name, look for it in the data (broader search)
    if not precinct_num:
        # Look for precinct number in various locations
        search_ranges = [
            (20, 30),   # Around row 25 (where A25 is)
            (0, 10),    # Top of sheet
            (10, 20),   # Middle-top
        ]
        
        for start_row, end_row in search_ranges:
            if precinct_num:
                break
            for i in range(start_row, min(end_row, len(sheet_data))):
                if precinct_num:
                    break
                if sheet_data[i]:
                    row = sheet_data[i]
                    for j, cell in enumerate(row):
                        if cell is not None and not pd.isna(cell):
                            cell_str = str(cell).strip()
                            print(f"    DEBUG: Checking row {i}, col {j}: '{cell_str}'")
                            
                            # Look for patterns like "Precinct 1", "PCT 1A", "1", "1 - Clyde", etc.
                            precinct_patterns = [
                                r'(?:precinct|pct|p)[-_\s]*([a-zA-Z0-9\s\-]+)',
                                r'^([a-zA-Z0-9\s\-]+)$'  # Any reasonable precinct identifier
                            ]
                            
                            for pattern in precinct_patterns:
                                match = re.search(pattern, cell_str, re.IGNORECASE)
                                if match:
                                    potential = match.group(1).strip()
                                    # Validate it's a reasonable precinct identifier
                                    if (potential and len(potential) <= 20 and 
                                        potential.lower() not in ['choice', 'votes', 'total', 'cast', 'over', 'under', 'registered', 'ballots']):
                                        precinct_num = potential
                                        print(f"    DEBUG: Found precinct number: '{precinct_num}'")
                                        break
                            
                            if precinct_num:
                                break
    
    # Look for voter registration and ballots cast info
    for i in range(min(100, len(sheet_data))):
        if sheet_data[i]:
            row = sheet_data[i]
            
            # Check for "Ballots Cast" row
            if row and len(row) > 0:
                first_cell = row[0]
                if first_cell and not pd.isna(first_cell) and isinstance(first_cell, str):
                    if 'ballots cast' in first_cell.lower():
                        print(f"    DEBUG: Found 'Ballots Cast' row at index {i}")
                        # Look for the total in the same row
                        for j in range(1, len(row)):
                            if row[j] and not pd.isna(row[j]):
                                try:
                                    ballots_cast = clean_numeric(row[j])
                                    if ballots_cast > 0:
                                        print(f"    DEBUG: Found ballots cast value: {ballots_cast}")
                                        break
                                except Exception:
                                    continue
            
            # Check for "registered voters" pattern
            for j, cell in enumerate(row):
                if cell and not pd.isna(cell) and isinstance(cell, str) and 'registered voters' in cell.lower():
                    print(f"    DEBUG: Found 'registered voters' in row {i}, col {j}: '{cell}'")
                    
                    # Look for pattern: "X of Y registered voters = Z%"
                    pattern = r'(\d+)\s+of\s+(\d+)\s+registered\s+voters'
                    match = re.search(pattern, str(cell), re.IGNORECASE)
                    if match:
                        ballots_cast = int(match.group(1))
                        registered_voters = int(match.group(2))
                        print(f"    DEBUG: Parsed from pattern - Ballots cast: {ballots_cast}, Registered voters: {registered_voters}")
                        break
                    else:
                        # Fallback: extract all numbers from the cell
                        numbers = re.findall(r'[\d,]+', str(cell))
                        if numbers:
                            print(f"    DEBUG: Numbers found in registered voters cell: {numbers}")
                            # Usually the first number is ballots cast, second is registered voters
                            if len(numbers) >= 2:
                                ballots_cast = clean_numeric(numbers[0])
                                registered_voters = clean_numeric(numbers[1])
                                print(f"    DEBUG: Fallback - Ballots cast: {ballots_cast}, Registered voters: {registered_voters}")
                                break
                            elif len(numbers) == 1:
                                ballots_cast = clean_numeric(numbers[0])
                                print(f"    DEBUG: Fallback - Ballots cast: {ballots_cast}")
    
    # If we still don't have ballots cast, look for "Cast Votes" rows
    if ballots_cast == 0:
        for i in range(min(100, len(sheet_data))):
            if sheet_data[i]:
                row = sheet_data[i]
                if row and len(row) > 0:
                    first_cell = row[0]
                    if first_cell and not pd.isna(first_cell) and isinstance(first_cell, str):
                        if 'cast votes' in first_cell.lower() or 'total votes cast' in first_cell.lower():
                            print(f"    DEBUG: Found 'Cast Votes' row at index {i}")
                            # Look for the total in the same row
                            for j in range(1, len(row)):
                                if row[j] and not pd.isna(row[j]):
                                    try:
                                        cast_votes = clean_numeric(row[j])
                                        if cast_votes > 0:
                                            ballots_cast = cast_votes
                                            print(f"    DEBUG: Found cast votes value: {ballots_cast}")
                                            break
                                    except Exception:
                                        continue
                            if ballots_cast > 0:
                                break
    
    print(f"    DEBUG: Final values - Precinct: '{precinct_num}', Registered: {registered_voters}, Ballots Cast: {ballots_cast}")
    return precinct_num, registered_voters, ballots_cast

def normalize_office_name(office: str) -> str:
    """Normalize office names according to the mapping rules"""
    office = office.strip()
    
    # Handle specific mappings
    if 'President and Vice President' in office or 'President/Vice President' in office:
        return 'President'
    elif 'United States Senator' in office or 'US Senator' in office or 'U.S. Senator' in office:
        return 'U.S. Senate'
    elif 'United States Representative' in office or 'US Representative' in office or 'U.S. Representative' in office:
        return 'U.S. House'
    elif 'State Senator' in office:
        return 'State Senate'
    elif 'State Representative' in office:
        return 'State Representative'
    elif 'Railroad Commissioner' in office:
        return 'Railroad Commissioner'
    elif 'Justice, Supreme Court' in office or 'Justice of the Supreme Court' in office:
        return office
    elif 'Presiding Judge' in office or 'Judge' in office:
        return office
    elif 'Attorney General' in office:
        return 'Attorney General'
    elif 'Governor' in office:
        return 'Governor'
    elif 'Lieutenant Governor' in office:
        return 'Lieutenant Governor'
    elif 'Secretary of State' in office:
        return 'Secretary of State'
    elif 'Comptroller' in office:
        return 'Comptroller'
    elif 'Land Commissioner' in office:
        return 'Land Commissioner'
    elif 'Sheriff' in office:
        return 'Sheriff'
    elif 'County' in office:
        return office
    elif 'District' in office:
        return office
    elif 'Constable' in office:
        return office
    
    # Return the office name as-is for other offices
    return office

def extract_district(office: str) -> Optional[str]:
    """Extract district number from office name"""
    district_match = re.search(r'District\s+(?:No\.\s*)?(\d+)', office, re.IGNORECASE)
    if district_match:
        return district_match.group(1)
    
    place_match = re.search(r'Place\s+(?:No\.\s*)?(\d+)', office, re.IGNORECASE)
    if place_match:
        return place_match.group(1)
    
    precinct_match = re.search(r'Precinct\s+(?:No\.\s*)?(\d+)', office, re.IGNORECASE)
    if precinct_match:
        return precinct_match.group(1)
    
    return None

def parse_candidate_name(full_name: str) -> str:
    """Extract candidate name, removing write-in indicators and cleaning up"""
    if not full_name:
        return ""
    
    # Remove write-in indicators
    full_name = re.sub(r'\s*\(W\)\s*', '', full_name)
    full_name = re.sub(r'\s*\(Write-in\)\s*', '', full_name, re.IGNORECASE)
    
    # For presidential tickets, keep the full ticket
    if any(indicator in full_name for indicator in ['/', ' and ', 'Tim Walz', 'JD Vance', 'Mike ter Maat', 'Rudolph Ware']):
        return full_name.strip()
    
    return full_name.strip()

def is_office_header(cell_value: str) -> bool:
    """Determine if a cell contains an office header"""
    if not cell_value or not isinstance(cell_value, str):
        return False
    
    office_keywords = [
        'President', 'Senator', 'Representative', 'Railroad Commissioner',
        'Justice', 'Judge', 'Attorney General', 'Governor', 'Lieutenant Governor',
        'Secretary of State', 'Comptroller', 'Land Commissioner', 'Member, State Board',
        'Chief Justice', 'District Judge', 'District Attorney', 'County Attorney',
        'Sheriff', 'County Tax Assessor', 'County Commissioner', 'Constable',
        'Board of Directors', 'Board of Trustee', 'PROPOSITION', 'LOCAL OPTION ELECTION'
    ]
    
    return any(keyword in cell_value for keyword in office_keywords) and \
           'Choice' not in cell_value and 'Cast Votes' not in cell_value

def find_vote_columns(sheet_data: List[List]) -> Dict[str, int]:
    """Find the column indices for different vote types"""
    vote_columns = {
        'total': -1,
        'absentee': -1,
        'early_voting': -1,
        'election_day': -1,
        'provisional': -1,
        'limited': -1,
        'party': -1
    }
    
    # Look for header rows that might contain vote type labels
    # Based on the structure, these should be around row 30
    for i in range(min(40, len(sheet_data))):
        if sheet_data[i]:
            for j, cell in enumerate(sheet_data[i]):
                if cell and not pd.isna(cell) and isinstance(cell, str):
                    cell_lower = cell.lower()
                    if 'absentee voting' in cell_lower or 'absentee' in cell_lower:
                        vote_columns['absentee'] = j
                        print(f"    DEBUG: Found Absentee column at index {j}")
                    elif 'early voting' in cell_lower or 'early' in cell_lower:
                        vote_columns['early_voting'] = j
                        print(f"    DEBUG: Found Early Voting column at index {j}")
                    elif 'election day voting' in cell_lower or 'election day' in cell_lower:
                        vote_columns['election_day'] = j
                        print(f"    DEBUG: Found Election Day column at index {j}")
                    elif 'provisional' in cell_lower:
                        vote_columns['provisional'] = j
                        print(f"    DEBUG: Found Provisional column at index {j}")
                    elif 'limited' in cell_lower:
                        vote_columns['limited'] = j
                        print(f"    DEBUG: Found Limited column at index {j}")
                    elif 'total' in cell_lower and vote_columns['total'] == -1:
                        vote_columns['total'] = j
                        print(f"    DEBUG: Found Total column at index {j}")
                    elif 'party' in cell_lower:
                        vote_columns['party'] = j
                        print(f"    DEBUG: Found Party column at index {j}")
    
    # If we didn't find the columns with the search above, use the known positions
    # Based on the structure analysis: H=Absentee, K=Early, P=Election Day, U=Total, F=Party
    if vote_columns['absentee'] == -1:
        vote_columns['absentee'] = 7  # Column H (index 7)
        print(f"    DEBUG: Using default Absentee column at index 7")
    if vote_columns['early_voting'] == -1:
        vote_columns['early_voting'] = 10  # Column K (index 10)
        print(f"    DEBUG: Using default Early Voting column at index 10")
    if vote_columns['election_day'] == -1:
        vote_columns['election_day'] = 15  # Column P (index 15)
        print(f"    DEBUG: Using default Election Day column at index 15")
    if vote_columns['total'] == -1:
        vote_columns['total'] = 20  # Column U (index 20)
        print(f"    DEBUG: Using default Total column at index 20")
    if vote_columns['party'] == -1:
        vote_columns['party'] = 5  # Column F (index 5)
        print(f"    DEBUG: Using default Party column at index 5")
    
    return vote_columns

def parse_sheet_data(sheet_data: List[List], precinct_num: str) -> List[Dict]:
    """Parse election data from a single sheet"""
    results = []
    current_office = None
    current_district = None
    
    # Add registered voters and ballots cast first
    precinct_info = extract_precinct_info(sheet_data, precinct_num)
    registered_voters = precinct_info[1]
    ballots_cast = precinct_info[2]
    
    print(f"    DEBUG: Processing precinct '{precinct_num}' - Registered: {registered_voters}, Ballots Cast: {ballots_cast}")
    
    # Only add registered voters if it's greater than 0
    if registered_voters > 0:
        results.append({
            'county': 'Hunt',
            'precinct': precinct_num,
            'office': 'Registered Voters',
            'district': '',
            'party': '',
            'candidate': '',
            'votes': registered_voters,
            'absentee': '',
            'early_voting': '',
            'election_day': '',
            'provisional': '',
            'limited': ''
        })
        print(f"    DEBUG: Added Registered Voters row with {registered_voters} votes")
    
    # Add ballots cast - always add this row
    results.append({
        'county': 'Hunt',
        'precinct': precinct_num,
        'office': 'Ballots Cast',
        'district': '',
        'party': '',
        'candidate': '',
        'votes': ballots_cast,
        'absentee': '',
        'early_voting': '',
        'election_day': '',
        'provisional': '',
        'limited': ''
    })
    print(f"    DEBUG: Added Ballots Cast row with {ballots_cast} votes")
    
    # Find vote column positions
    vote_columns = find_vote_columns(sheet_data)
    
    i = 0
    while i < len(sheet_data):
        row = sheet_data[i]
        if not row:
            i += 1
            continue
            
        # Check if this is an office header
        if row[0] and not pd.isna(row[0]) and is_office_header(str(row[0])):
            current_office = normalize_office_name(str(row[0]))
            current_district = extract_district(str(row[0]))
            print(f"    DEBUG: Found office header: '{current_office}' (district: {current_district})")
            i += 1
            continue
        
        # Check if this is a candidate row (has a name and potential vote data)
        if (current_office and row[0] and not pd.isna(row[0]) and isinstance(row[0], str) and 
            row[0].strip() and
            'Choice' not in str(row[0]) and
            'Cast Votes' not in str(row[0]) and
            'Undervotes' not in str(row[0]) and
            'Overvotes' not in str(row[0]) and
            not is_office_header(str(row[0]))):
            
            candidate_name = parse_candidate_name(str(row[0]))
            
            # Try to find party information using the party column
            party = ''
            if vote_columns['party'] != -1 and vote_columns['party'] < len(row):
                party_cell = row[vote_columns['party']]
                if party_cell and not pd.isna(party_cell) and isinstance(party_cell, str):
                    party_text = str(party_cell).strip()
                    if party_text in ['REP', 'DEM', 'LIB', 'GRN', 'IND', 'Republican', 'Democratic', 'Libertarian', 'Green']:
                        party = party_text[:3].upper()  # Standardize to 3-letter abbreviations
            
            # If party not found in party column, try early columns as fallback
            if not party:
                for j in range(1, min(7, len(row))):
                    if row[j] and not pd.isna(row[j]) and isinstance(row[j], str):
                        party_text = str(row[j]).strip()
                        if party_text in ['REP', 'DEM', 'LIB', 'GRN', 'IND', 'Republican', 'Democratic', 'Libertarian', 'Green']:
                            party = party_text[:3].upper()  # Standardize to 3-letter abbreviations
                            break
            
            # Extract vote counts using the identified columns
            vote_data = {
                'total': 0,
                'absentee': 0,
                'early_voting': 0,
                'election_day': 0,
                'provisional': 0,
                'limited': 0
            }
            
            # Extract vote counts from specific columns
            if vote_columns['total'] != -1 and vote_columns['total'] < len(row):
                vote_data['total'] = clean_numeric(row[vote_columns['total']])
            
            if vote_columns['absentee'] != -1 and vote_columns['absentee'] < len(row):
                vote_data['absentee'] = clean_numeric(row[vote_columns['absentee']])
            
            if vote_columns['early_voting'] != -1 and vote_columns['early_voting'] < len(row):
                vote_data['early_voting'] = clean_numeric(row[vote_columns['early_voting']])
            
            if vote_columns['election_day'] != -1 and vote_columns['election_day'] < len(row):
                vote_data['election_day'] = clean_numeric(row[vote_columns['election_day']])
            
            if vote_columns['provisional'] != -1 and vote_columns['provisional'] < len(row):
                vote_data['provisional'] = clean_numeric(row[vote_columns['provisional']])
            
            if vote_columns['limited'] != -1 and vote_columns['limited'] < len(row):
                vote_data['limited'] = clean_numeric(row[vote_columns['limited']])
            
            # If total is 0 but we have vote breakdowns, calculate total
            if vote_data['total'] == 0:
                vote_data['total'] = vote_data['absentee'] + vote_data['early_voting'] + vote_data['election_day'] + vote_data['provisional'] + vote_data['limited']
            
            results.append({
                'county': 'Hunt',
                'precinct': precinct_num,
                'office': current_office,
                'district': current_district or '',
                'party': party,
                'candidate': candidate_name,
                'votes': vote_data['total'],
                'absentee': vote_data['absentee'],
                'early_voting': vote_data['early_voting'],
                'election_day': vote_data['election_day'],
                'provisional': vote_data['provisional'],
                'limited': vote_data['limited']
            })
        
        # Check for Undervotes and Overvotes
        elif (current_office and row[0] and not pd.isna(row[0]) and isinstance(row[0], str) and 
              ('Undervotes' in str(row[0]) or 'Overvotes' in str(row[0]))):
            
            vote_type = 'Under Votes' if 'Undervotes' in str(row[0]) else 'Over Votes'
            
            # Extract vote counts using the identified columns
            vote_data = {
                'total': 0,
                'absentee': 0,
                'early_voting': 0,
                'election_day': 0,
                'provisional': 0,
                'limited': 0
            }
            
            # Extract vote counts from specific columns
            if vote_columns['total'] != -1 and vote_columns['total'] < len(row):
                vote_data['total'] = clean_numeric(row[vote_columns['total']])
            
            if vote_columns['absentee'] != -1 and vote_columns['absentee'] < len(row):
                vote_data['absentee'] = clean_numeric(row[vote_columns['absentee']])
            
            if vote_columns['early_voting'] != -1 and vote_columns['early_voting'] < len(row):
                vote_data['early_voting'] = clean_numeric(row[vote_columns['early_voting']])
            
            if vote_columns['election_day'] != -1 and vote_columns['election_day'] < len(row):
                vote_data['election_day'] = clean_numeric(row[vote_columns['election_day']])
            
            if vote_columns['provisional'] != -1 and vote_columns['provisional'] < len(row):
                vote_data['provisional'] = clean_numeric(row[vote_columns['provisional']])
            
            if vote_columns['limited'] != -1 and vote_columns['limited'] < len(row):
                vote_data['limited'] = clean_numeric(row[vote_columns['limited']])
            
            # If total is 0 but we have vote breakdowns, calculate total
            if vote_data['total'] == 0:
                vote_data['total'] = vote_data['absentee'] + vote_data['early_voting'] + vote_data['election_day'] + vote_data['provisional'] + vote_data['limited']
            
            results.append({
                'county': 'Hunt',
                'precinct': precinct_num,
                'office': current_office,
                'district': current_district or '',
                'party': '',
                'candidate': vote_type,
                'votes': vote_data['total'],
                'absentee': vote_data['absentee'],
                'early_voting': vote_data['early_voting'],
                'election_day': vote_data['election_day'],
                'provisional': vote_data['provisional'],
                'limited': vote_data['limited']
            })
        
        i += 1
    
    return results

def main():
    """Main function to process the Excel file and create CSV output"""
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = '~/code/openelections-sources-tx/2024/general/2024 Hardin County, TX precinct-level results.xlsx'
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        output_file = '20241105__tx__general__hardin__precinct.csv'
    
    try:
        # Read all sheets from the Excel file
        excel_file = pd.ExcelFile(input_file)
        all_results = []
        processed_precincts = set()
        
        print(f"Processing {len(excel_file.sheet_names)} sheets...")
        print(f"Sheet names: {excel_file.sheet_names}")
        
        for sheet_name in excel_file.sheet_names:
            # Skip certain sheets that might not contain precinct data
            if any(skip_word in sheet_name.lower() for skip_word in ['document map', 'summary', 'totals', 'index']):
                print(f"Skipping {sheet_name}")
                continue
                
            print(f"Processing {sheet_name}...")
            
            try:
                # Read sheet data as raw values
                df = pd.read_excel(input_file, sheet_name=sheet_name, header=None)
                sheet_data = df.values.tolist()
                
                print(f"  Sheet has {len(sheet_data)} rows and {len(sheet_data[0]) if sheet_data else 0} columns")
                
                # Extract precinct number
                precinct_info = extract_precinct_info(sheet_data, sheet_name)
                precinct_num = precinct_info[0]
                
                if precinct_num:
                    # Check if we've already processed this precinct
                    if precinct_num in processed_precincts:
                        print(f"  WARNING: Precinct {precinct_num} already processed, skipping duplicate")
                        continue
                    
                    processed_precincts.add(precinct_num)
                    sheet_results = parse_sheet_data(sheet_data, precinct_num)
                    all_results.extend(sheet_results)
                    print(f"  Found precinct {precinct_num} with {len(sheet_results)} records")
                else:
                    print(f"  Could not determine precinct number for {sheet_name}")
            
            except Exception as e:
                print(f"  Error processing {sheet_name}: {e}")
                print(f"  Error type: {type(e).__name__}")
                continue
        
        # Write results to CSV
        if all_results:
            fieldnames = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 
                         'votes', 'absentee', 'early_voting', 'election_day', 'provisional', 'limited']
            
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerows(all_results)
            
            print(f"\nSuccessfully wrote {len(all_results)} records to {output_file}")
            
            # Show summary statistics
            unique_precincts = set(row['precinct'] for row in all_results)
            ballots_cast_count = sum(1 for row in all_results if row['office'] == 'Ballots Cast')
            print(f"Unique precincts processed: {sorted(unique_precincts)}")
            print(f"Ballots Cast rows created: {ballots_cast_count}")
            print(f"Total precincts: {len(unique_precincts)}")
        else:
            print("No data was extracted from the Excel file")
            
    except Exception as e:
        print(f"Error processing file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()