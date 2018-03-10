#!/usr/bin/env python3
# This script creates a CSV file in the desired format for Dallas County.
# It is a horrible hack that will probably need extensive edits to work properly.
# The input is a CSV file created from the MS Access database in the results zip file located here:
# http://www.dallascountyvotes.org/election-results-and-maps/election-results/historical-election-results/#Election
# The script as written has only been confirmed to work with files from the 2014 general election.

import csv

def load_data(filename):
    with open(filename) as f:
        datadict = [{k: v for k, v in row.items()}
            for row in csv.DictReader(f, skipinitialspace=True)]
    return datadict

def create_csv(datadict, output_filename):
    with open(output_filename, 'w', newline='') as f:
        fieldnames=['county','precinct','ballot_style','office','district','party','candidate','votes','early_voting','election_day','provisional']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in datadict:
            temp = {'county': 'Dallas', 'precinct': int(d['Precinct-Ballot Style'].split('-')[0]), 'ballot_style': int(d['Pct Ballot Style']), 'office': d['Contest Title'], 'district': None, 'party': d['Party Code'], 'candidate': d['Candidate Name'], 'votes': int(d['Total Votes/Reg Voters']), 'early_voting': int(d['EV In-Person']) + int(d['EV Mail']), 'election_day': int(d['Election Day']) + int(d['ED ADA']), 'provisional': int(d['Prov EV/ED'])}
            if 'State Representative' in temp['office']:
                temp['district'] = int(temp['office'].split(None)[-1])
                temp['office'] = 'State Representative'
            elif 'State Senator' in temp['office']:
                temp['district'] = int(temp['office'].split(None)[-1])
                temp['office'] = 'State Senator'
            elif 'U. S. Representative' in temp['office']:
                temp['district'] = int(temp['office'].split(None)[-1])
                temp['office'] = 'U.S. House'
            elif 'U. S. Senator' in temp['office']:
                temp['office'] = 'U.S. Senate'
            writer.writerow(temp)
