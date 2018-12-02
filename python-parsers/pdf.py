import csv
import re

# This script operates on precinct results files in e.g. this format
# https://github.com/openelections/openelections-sources-tx/blob/master/2016/Archer%20TX%20prect.%20by%20prect.%20report%20Nov%202016.pdf
# To turn the PDF into a usable text file, using Ghostscript (`gs -sDEVICE=txtwrite -o [county].txt [input pdf]`) is recommended.

County = 'County'
county = County.lower()

precinct_regex = r'^ *Precinct ([^\(]+) +\(Ballots Cast: ([\d,]+)\) *$'
office_regex = r'^ *([\w ,:\.-]+), Vote For \d+ *$'
candidate_regex = r'^ *([\w\'" ,:\.-]+?) *([\d,]+) *\d+\.\d+% *([\d,]+) *\d+\.\d+% *([\d,]+) *\d+\.\d+% *([\d,]+) *\d+\.\d+% *$'
extra_regex = r'^ *(\w+) Votes: *([\d,]+) *\d+\.\d+% *([\d,]+) *\d+\.\d+% *([\d,]+) *\d+\.\d+% *([\d,]+) *\d+\.\d+% *$'

def create_csv(datafile, output_filename):
    with open(output_filename, 'w', newline='') as f:
        with open(datafile) as data:
            fieldnames=['county','precinct','office','district','party','candidate','votes','early_voting','election_day','absentee']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            party = None
            precinct = None
            office = None
            district = None
            staging = {'early': None,
                       'ed': None,
                       'absentee': None}

            for line in data:
                match = re.match(precinct_regex, line)
                if match:
                    try:
                        if precinct['number'] != match.group(1).strip():    # this is a new precinct
                            if not all([precinct['early'], precinct['ed'], precinct['absentee']]):  # *none* of the races' sums matched the ballots cast number - pernicious!!
                                print(f'ERROR: No total matched for precinct {precinct["number"]}!')
                            temp = {'county': County,
                                    'precinct': precinct['number'],
                                    'office': 'Ballots Cast',
                                    'district': None,
                                    'party': party,
                                    'candidate': None,
                                    'votes': precinct['total'],
                                    'early_voting': precinct['early'],
                                    'election_day': precinct['ed'],
                                    'absentee': precinct['absentee']}
                            writer.writerow(temp)   # write the precinct statistical information
                            # reset the helper data structures
                            staging = {'early': None,
                                       'ed': None,
                                       'absentee': None}
                            precinct = {'number': match.group(1).strip(),
                                        'total': int(match.group(2).replace(',','')),
                                        'early': None,
                                        'ed': None,
                                        'absentee': None}
                        else:   # same precinct; keep going
                            continue
                    except TypeError: # precinct is None - this is the first precinct
                        precinct = {'number': match.group(1).strip(),
                                    'total': int(match.group(2).replace(',','')),
                                    'early': None,
                                    'ed': None,
                                    'absentee': None}
                        continue

                match = re.match(office_regex, line)
                if match:   # set office and optionally district
                    office = match.group(1)
                    if 'State Representative' in office:
                        district = int(office.split(None)[-1])
                        office = 'State Representative'
                    elif 'State Senator' in office:
                        district = int(office.split(None)[-1])
                        office = 'State Senator'
                    elif 'United States Rep' in office or 'US Rep' in office:
                        district = int(office.split(None)[-1])
                        office = 'U.S. House'
                    elif 'United States Sen' in office or 'US Sen' in office:
                        office = 'U.S. Senate'
                        district = None
                    else:
                        district = None
                    continue
                
                match = re.match(extra_regex, line)
                if match:   # per-race statistics - cast/over/under votes
                    if match.group(1) == 'Cast':
                        if staging['absentee'] and staging['early'] and staging['ed']:
                            if staging['absentee'] + staging['early'] + staging['ed'] == precinct['total']: # sanity check to make sure we're storing numbers that add up in `precinct`
                                precinct['absentee'] = staging['absentee']
                                precinct['early'] = staging['early']
                                precinct['ed'] = staging['ed']
                        # set values for `staging`
                        staging['absentee'] = int(match.group(2).replace(',',''))
                        staging['early'] = int(match.group(3).replace(',',''))
                        staging['ed'] = int(match.group(4).replace(',',''))
                        if int(match.group(5).replace(',','')) != staging['absentee'] + staging['early'] + staging['ed']:
                            print('ERROR: PRECINCT BALLOTS CAST BAD FOR PCT {} (Office {})'.format(staging['number'], office))
                        continue
                    elif match.group(1) == 'Over' or match.group(1) == 'Under': # we actually want to write this information
                        temp = {'county': County,
                                'precinct': precinct['number'],
                                'office': office,
                                'district': district,
                                'party': party,
                                'candidate': '{} Votes'.format(match.group(1)),
                                'votes': int(match.group(5).replace(',','')),
                                'early_voting': int(match.group(3).replace(',','')),
                                'election_day': int(match.group(4).replace(',','')),
                                'absentee': int(match.group(2).replace(',',''))}
                        staging['absentee'] += int(match.group(2).replace(',',''))
                        staging['early'] += int(match.group(3).replace(',',''))
                        staging['ed'] += int(match.group(4).replace(',',''))
                        if temp['votes'] != temp['early_voting'] + temp['election_day'] + temp['absentee']:
                            print('ERROR: MISC TOTALS BAD FOR {}\n(extras)'.format(temp))
                        writer.writerow(temp)
                        continue
                    else:
                        print('ERROR: unknown group {}'.format(match.group(1)))
                        continue

                match = re.match(candidate_regex, line)
                if match:
                    if office == 'Straight Party':  # this makes an assumption as to the format of the "candidate names"
                        party = match.group(1)[:3].upper()
                    temp = {'county': County,
                            'precinct': precinct['number'],
                            'office': office,
                            'district': district,
                            'party': party,
                            'candidate': match.group(1),
                            'votes': int(match.group(5).replace(',','')),
                            'early_voting': int(match.group(3).replace(',','')),
                            'election_day': int(match.group(4).replace(',','')),
                            'absentee': int(match.group(2).replace(',',''))}
                    party = None
                    if temp['votes'] != temp['early_voting'] + temp['election_day'] + temp['absentee']:
                        print('ERROR: TOTALS BAD FOR {}\n(candidate)'.format(temp))
                    writer.writerow(temp)
                    continue

            # write stats for the final precinct
            temp = {'county': County,
                    'precinct': precinct['number'],
                    'office': 'Ballots Cast',
                    'district': None,
                    'party': party,
                    'candidate': None,
                    'votes': precinct['total'],
                    'early_voting': precinct['early'],
                    'election_day': precinct['ed'],
                    'absentee': precinct['absentee']}
            if temp['votes'] != temp['early_voting'] + temp['election_day'] + temp['absentee']:
                print('ERROR: TOTALS BAD FOR {}\n(final precinct stats)'.format(temp))
            writer.writerow(temp)

create_csv('{}.txt'.format(county), '{}-staging.csv'.format(County))

def load_data(filename):
    with open(filename) as f:
        datadict = [{k: v for k, v in row.items()}
            for row in csv.DictReader(f, skipinitialspace=True)]
    return datadict

# this function helps verify precinct results (i.e. sums) against cumulative county results
def sum_keys(datadict, office, candidate=None, field='votes'):
    total = 0 
    for row in datadict:
        if row['office'] == office:
            if candidate:
                if row['candidate'] == candidate:
                    total += int(row[field])
            else:
                    total += int(row[field])
    return total

gendata = load_data('{}-staging.csv'.format(County))
