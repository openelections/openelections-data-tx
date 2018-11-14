#!/usr/bin/env python3
# Note: This script requires the installation of the following pip packages:
# camelot-py[cv] chardet

from collections import OrderedDict
import csv
import camelot
import PyPDF2
import re
import sys

county = '[COUNTY NAME HERE]'
filename = '[SOURCE FILE HERE].pdf'

if len(sys.argv) > 1 and sys.argv[1] == 'paranoiac':
    verbose = True
else:
    verbose = False

def create_csv(source_filename, output_filename):
    reg = None
    cast = None
    over = None
    under = None
    candidates = None
    current_precinct = None
    page = None
    with open(source_filename, 'rb') as f:
        file = PyPDF2.PdfFileReader(open(source_filename, 'rb'))
        num_pages = file.getNumPages()
    with open(output_filename, 'w', newline='') as f:
        # Probably need to be modified depending on what fields are present in the PDF
        fieldnames=['county','precinct','office','district','party','candidate','votes','early_voting','election_day','election_day_paper','absentee']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for page in range(num_pages):
            print(f'processing page {page+1}')
            # table_areas should be selected such that the race is the first set of coordinates, and the header (candidate names) is the second set.
            race, header = camelot.read_pdf(filename, flavor='stream', row_close_tol=50, table_areas=['0,675,1000,650', '0,650,1000,600'], pages=str(page+1), margins=(0.5,0.5,0.1), suppress_warnings=True)
            race_name = race.data[0][0]
            headers = header.data[0]
            # table_areas should be the area encompassing the tabular results
            data = camelot.read_pdf(filename, flavor='stream', table_areas=['0,600,1000,0'], pages=str(page+1), margins=(0.5,0.5,0.1), suppress_warnings=True)
            rows = data[0].data
            if race_name == 'TURN OUT':
                # write registered voters and ballots cast - this assumes the information is present on the first few pages
                for row in rows:
                    if row[0] == 'Jurisdiction Wide':   # Skip processing of this informational row - might be Collin County specific
                        continue
                    elif row[0].startswith('PCT'):  # New precinct, initialize a new pair of rows
                        current_precinct = int(row[0].split(None, 1)[1])
                        reg =  {'county': county,
                                'precinct': current_precinct,
                                'office': 'Registered Voters - Total',
                                'candidate': 'Registered Voters - Total',
                                'votes': None}
                        cast = {'county': county,
                                'precinct': current_precinct,
                                'office': 'Ballots Cast - Total',
                                'candidate': 'Ballots Cast - Total',
                                'votes': None,
                                'early_voting': None,
                                'election_day': None,
                                'election_day_paper': None,
                                'absentee': None}
                    elif row[0] == 'Polling':
                        reg['votes'] = int(row[1])
                        cast['election_day'] = int(row[2])
                    elif row[0] == 'Paper':
                        cast['election_day_paper'] = int(row[2])
                    elif row[0] == 'Mail':
                        cast['absentee'] = int(row[2])
                    elif row[0] == 'Early':
                        cast['early_voting'] = int(row[2])
                    elif row[0] == 'Total':
                        if not any([x for x in row[1:]]):   # If all fields after "Total" are blank, i.e., we've reached the cumulative results and should stop
                            break
                        cast['votes'] = int(row[2])
                        if cast['votes'] != sum([cast[key] for key in ['early_voting', 'election_day', 'election_day_paper', 'absentee']]): # Basic error-checking - can never be too careful
                            print(f'Error in turn out numbers for precinct {current_precinct}', file=sys.stderr)
                        if verbose:
                            print(f'writing row {reg}')
                            print(f'writing row {cast}')
                        writer.writerow(reg)
                        writer.writerow(cast)
                    else:
                        print(f'Unknown field name {row[0]} on page {page+1}, precinct {current_precinct}')
            else:   # Regular races, with statistical numbers (over/under votes)
                # Replace special race names - probably different for other counties
                if race_name.startswith('US Senator'):
                    district = None
                    race_name = 'U.S. Senate'
                if race_name.startswith('US Representative D'):
                    district = int(race_name.replace('US Representative D', ''))
                    race_name = 'U.S. House'
                elif race_name.startswith('State Representative D'):
                    district = int(race_name.replace('State Representative D', ''))
                    race_name = 'State Representative'
                elif race_name.startswith('State Senator D'):
                    district = int(race_name.replace('State Senator D', ''))
                    race_name = 'State Senator'
                else:
                    district = None
                if headers[0] == 'Reg. Voters': # Assume that this indicates the presence of race statistics
                    for row in rows:
                        if row[0] == 'Jurisdiction Wide':
                            continue
                        elif all([element == '-' for element in row[1:]]):  # Dashes for all fields - i.e. the current precinct is not within the race's jurisdiction
                            continue
                        elif row[0].startswith('PCT'):
                            current_precinct = int(row[0].split(None, 1)[1])
                            over = {'county': county,
                                    'precinct': current_precinct,
                                    'office': race_name,
                                    'district': district,
                                    'candidate': 'OVER VOTES',
                                    'votes': None,
                                    'early_voting': None,
                                    'election_day': None,
                                    'election_day_paper': None,
                                    'absentee': None}
                            under = {'county': county,
                                     'precinct': current_precinct,
                                     'office': race_name,
                                     'district': district,
                                     'candidate': 'UNDER VOTES',
                                     'votes': None,
                                     'early_voting': None,
                                     'election_day': None,
                                     'election_day_paper': None,
                                     'absentee': None}
                            candidates = OrderedDict()
                            for x in headers[7:]:   # This assumes that there are 7 non-candidate fields
                                party = re.match(r'^[^\(\)]+\((.+)\)$', x)
                                if party:   # Detect party info, formatted as "John C. Candidate (PTY)"
                                    party_name = party.group(1)
                                    if race_name == 'Straight Party':   # Trim off extra information
                                        candidate = None
                                    else:
                                        candidate = x.replace(f' ({party_name})', '')
                                else:
                                    party_name = None
                                    candidate = x
                                candidates[x] = {'county': county,
                                                 'precinct': current_precinct,
                                                 'office': race_name,
                                                 'district': district,
                                                 'candidate': candidate,
                                                 'party': party_name,
                                                 'votes': None,
                                                 'early_voting': None,
                                                 'election_day': None,
                                                 'election_day_paper': None,
                                                 'absentee': None}
                        elif row[0] == 'Polling':
                            over['election_day'] = int(row[6])
                            under['election_day'] = int(row[5]) + int(row[7])
                            if (len(row) - 8) % 2 != 0:
                                print(f'Error: non-even number of fields on page {page+1}, precinct {current_precinct}, type {row[0]}', file=sys.stderr)
                            else:
                                for index in range((len(row) - 7) // 2):    # Assumption: there will be 2 * number of candidates + 7 non-candidate columns
                                    candidates[headers[7 + index]]['election_day'] = int(row[7 + 2 * index + 1]) # Get the candidate name from the header, then the correct vote tally
                        elif row[0] == 'Paper':
                            over['election_day_paper'] = int(row[6])
                            under['election_day_paper'] = int(row[5]) + int(row[7])
                            if (len(row) - 8) % 2 != 0:
                                print(f'Error: non-even number of fields on page {page+1}, precinct {current_precinct}, type {row[0]}', file=sys.stderr)
                            else:
                                for index in range((len(row) - 7) // 2):
                                    candidates[headers[7 + index]]['election_day_paper'] = int(row[7 + 2 * index + 1]) # Get the candidate name from the header, then the correct vote tally
                        elif row[0] == 'Mail':
                            over['absentee'] = int(row[6])
                            under['absentee'] = int(row[5]) + int(row[7])
                            if (len(row) - 8) % 2 != 0:
                                print(f'Error: non-even number of fields on page {page+1}, precinct {current_precinct}, type {row[0]}', file=sys.stderr)
                            else:
                                for index in range((len(row) - 7) // 2):
                                    candidates[headers[7 + index]]['absentee'] = int(row[7 + 2 * index + 1]) # Get the candidate name from the header, then the correct vote tally
                        elif row[0] == 'Early':
                            over['early_voting'] = int(row[6])
                            under['early_voting'] = int(row[5]) + int(row[7])
                            if (len(row) - 8) % 2 != 0:
                                print(f'Error: non-even number of fields on page {page+1}, precinct {current_precinct}, type {row[0]}', file=sys.stderr)
                            else:
                                for index in range((len(row) - 7) // 2):
                                    candidates[headers[7 + index]]['early_voting'] = int(row[7 + 2 * index + 1]) # Get the candidate name from the header, then the correct vote tally
                        elif row[0] == 'Total':
                            if not any([x for x in row[1:]]):
                                break
                            over['votes'] = int(row[6])
                            if over['votes'] != sum([over[key] for key in ['early_voting', 'election_day', 'election_day_paper', 'absentee']]):
                                print(f'Error in overvote numbers for race {race_name}, precinct {current_precinct}', file=sys.stderr)
                            under['votes'] = int(row[5]) + int(row[7])
                            if under['votes'] != sum([under[key] for key in ['early_voting', 'election_day', 'election_day_paper', 'absentee']]):
                                print(f'Error in undervote numbers for race {race_name}, precinct {current_precinct}', file=sys.stderr)
                            if (len(row) - 8) % 2 != 0:
                                print(f'Error: non-even number of fields on page {page+1}, precinct {current_precinct}, type {row[0]}', file=sys.stderr)
                            else:
                                for index in range((len(row) - 7) // 2):
                                    candidate_name = headers[7 + index] # Get the candidate name from the header
                                    candidates[candidate_name]['votes'] = int(row[7 + 2 * index + 1]) # Undervotes @ [7], index starting at 0, votes first element after percentage/undervotes
                                    if candidates[candidate_name]['votes'] != sum([candidates[candidate_name][key] for key in ['early_voting', 'election_day', 'election_day_paper', 'absentee']]):
                                        print(f'Error in candidate {candidate_name} numbers for race {race_name}, precinct {current_precinct}', file=sys.stderr)
                            if verbose:
                                print(f'writing row {over}')
                                print(f'writing row {under}')
                            writer.writerow(over)
                            writer.writerow(under)
                            for candidate in candidates.values():
                                if verbose:
                                    print(f'writing row {candidate}')
                                writer.writerow(candidate)
                        else:
                            print(f'Unknown field name {row[0]} on page {x+1}, precinct {current_precinct}')
                else: # Row structure is [vote type, then candidates' info]
                    for row in rows:
                        if row[0] == 'Jurisdiction Wide':
                            continue
                        elif all([element == '-' for element in row[1:]]):
                            continue
                        elif row[0].startswith('PCT'):
                            current_precinct = int(row[0].split(None, 1)[1])
                            candidates = OrderedDict()
                            for x in headers:
                                party = re.match(r'^[^\(\)]+\((.+)\)$', x)
                                if party:
                                    party_name = party.group(1)
                                    if race_name == 'Straight Party':
                                        candidate = None
                                    else:
                                        candidate = x.replace(f' ({party_name})', '')
                                else:
                                    party_name = None
                                    candidate = x
                                candidates[x] = {'county': county,
                                                 'precinct': current_precinct,
                                                 'office': race_name,
                                                 'district': district,
                                                 'candidate': candidate,
                                                 'party': party_name,
                                                 'votes': None,
                                                 'early_voting': None,
                                                 'election_day': None,
                                                 'election_day_paper': None,
                                                 'absentee': None}
                        elif row[0] == 'Polling':                            
                            if (len(row) - 1) % 2 != 0:
                                print(f'Error: non-even number of fields on page {page+1}, precinct {current_precinct}, type {row[0]}', file=sys.stderr)
                            else:
                                for index in range((len(row) - 1) // 2):
                                    candidates[headers[index]]['election_day'] = int(row[2 * index + 1]) # Get the candidate name from the header, then the correct vote tally
                        elif row[0] == 'Paper':
                            if (len(row) - 1) % 2 != 0:
                                print(f'Error: non-even number of fields on page {page+1}, precinct {current_precinct}, type {row[0]}', file=sys.stderr)
                            else:
                                for index in range((len(row) - 1) // 2):
                                    candidates[headers[index]]['election_day_paper'] = int(row[2 * index + 1])
                        elif row[0] == 'Mail':
                            if (len(row) - 1) % 2 != 0:
                                print(f'Error: non-even number of fields on page {page+1}, precinct {current_precinct}, type {row[0]}', file=sys.stderr)
                            else:
                                for index in range((len(row) - 1) // 2):
                                    candidates[headers[index]]['absentee'] = int(row[2 * index + 1])
                        elif row[0] == 'Early':
                            if (len(row) - 1) % 2 != 0:
                                print(f'Error: non-even number of fields on page {page+1}, precinct {current_precinct}, type {row[0]}', file=sys.stderr)
                            else:
                                for index in range((len(row) - 1) // 2):
                                    candidates[headers[index]]['early_voting'] = int(row[2 * index + 1])
                        elif row[0] == 'Total':
                            if not any([x for x in row[1:]]):
                                break
                            if (len(row) - 1) % 2 != 0:
                                print(f'Error: non-even number of fields on page {page+1}, precinct {current_precinct}, type {row[0]}', file=sys.stderr)
                            else:
                                for index in range((len(row) - 1) // 2):
                                    candidate_name = headers[index]
                                    candidates[candidate_name]['votes'] = int(row[2 * index + 1])
                                    if candidates[candidate_name]['votes'] != sum([candidates[candidate_name][key] for key in ['early_voting', 'election_day', 'election_day_paper', 'absentee']]):
                                        print(f'Error in candidate {candidate_name} numbers for race {race_name}, precinct {current_precinct}', file=sys.stderr)
                            for candidate in candidates.values():
                                if verbose:
                                    print(f'writing row {candidate}')
                                writer.writerow(candidate)
                        else:
                            print(f'Unknown field name {row[0]} on page {x+1}, precinct {current_precinct}')

create_csv(filename, '{}-staging.csv'.format(county))
