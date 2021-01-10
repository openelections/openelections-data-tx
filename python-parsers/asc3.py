#!/usr/bin/env python3
# This script takes looks for an ASC file with 208-character lines in the
# current directory and outputs a CSV file in the format preferred by OpenElections.
import code
import csv
import sys

if len(sys.argv) != 2:
    print("Usage: {} <County name>".format(sys.argv[0]))
    exit(1)

County = sys.argv[1]
county = County.lower()

def print_asc(line):
    print('Contest Number: {}'.format(line[0:4]))
    print('Candidate Number: {}'.format(line[4:7]))
    print('Precinct Code: {}'.format(line[7:11]))
    print('Total Votes: {}'.format(line[12:18]))
    print('Early Voting: {}'.format(line[17:23]))
    print('Election Day: {}'.format(line[23:29]))
    print('Provisional: {}'.format(line[29:36]))
    print('Vote Group 4: {}'.format(line[35:41]))
    print('Vote Group 5: {}'.format(line[41:47]))
    print('Party Code: {}'.format(line[18:21]))
    print('District Type ID: {}'.format(line[50:53]))
    print('District Code: {}'.format(line[62:64]))
    print('Contest Title: {}'.format(line[28:83]))
    print('Candidate Name: {}'.format(line[84:121]))
    print('Precinct Name: {}'.format(line[122:176]))
    print('District Name: {}'.format(line[181:206]))
    print('Votes Allowed: {}'.format(line[206:208]))
    print('Referendum Flag: {}'.format(line[208]))

def create_csv(datafile, output_filename):
    with open(output_filename, 'w', newline='') as f:
        with open(datafile) as data:
            fieldnames=['county','precinct','office','district','party','candidate','votes','absentee','early_voting1','early_voting2', 'election_day1', 'election_day2']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            current_precinct = 0
            current_race = 0
            for line in data:
                temp = {'county': County,
                        'precinct': line[205:236].strip(),
                        'office': line[111:166].strip(),
                        'party': line[101:105].strip(),
                        'candidate': line[167:204].strip(),
                        'votes': int(line[13:17]),
                        'absentee': line[18:23],
                        'early_voting1': line[24:29],
                        'early_voting2': int(line[29:35]),
                        'election_day1': int(line[36:41]),
                        'election_day2': int(line[42:47])}
                if 'State Representative' in temp['office']:
                    temp['district'] = int(temp['office'].split(None)[-1])
                    temp['office'] = 'State Representative'
                elif 'State Senator' in temp['office']:
                    temp['district'] = int(temp['office'].split(None)[-1])
                    temp['office'] = 'State Senator'
                elif 'United States Representative' in temp['office']:
                    temp['district'] = int(temp['office'].split(None)[-1])
                    temp['office'] = 'U.S. House'
                #elif 'United States Senator' in temp['office']:
                #    temp['office'] = 'U.S. Senate'
                writer.writerow(temp)


def load_data(filename):
    with open(filename) as f:
        datadict = [{k: v for k, v in row.items()}
            for row in csv.DictReader(f, skipinitialspace=True)]
    return datadict

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

create_csv('{}.asc'.format(county), '{}-staging.csv'.format(County))

gendata = load_data('{}-staging.csv'.format(County))

code.interact(local=dict(globals(), **locals()))
