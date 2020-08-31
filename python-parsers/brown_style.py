import csv

county = 'Cass'

lines = open('/Users/dwillis/code/openelections-sources-tx/2020/primary/CASS_COUNTY-2020_MARCH_3RD_DEMOCRATIC_PRIMARY_332020-precinct.official precinct report primary election 03-03-2020.txt').readlines()
results = []

for line in lines:
    if line.strip() == '':
        continue
    if line.strip() == 'Ballots Cast - NONPARTISAN':
        continue
    if line.strip() == 'Ballots Cast - Blank':
        continue
    if line.strip() == 'Voter Turnout - Total':
        continue
    if line[0:14] == 'Contest Totals':
        continue
    if 'Ballots Cast' in line:
        precinct = line.split('(')[0].strip()
        ballots = int(line.split('(')[1].split(': ')[1].strip().replace(')','').replace(',',''))
        results.append([county, precinct, 'Ballots Cast', None, 'REP', None, None, None, None, ballots])
    elif 'DEMOCRATIC PARTY' in line or 'REPUBLICAN PARTY' in line:
        office = line.split('\t')[0]
        if 'DEMOCRATIC PARTY' in line:
            party = 'DEM'
        else:
            party = 'REP'
    elif 'Cast Votes' in line:
        results.append([county, precinct, office, None, party, 'Ballots Cast', int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[5].replace(',','')), int(line.split('\t')[7].replace(',',''))])
        ballot_lines = 1
    else:
        if 'Undervotes' in line or 'Overvotes' in line:
            results.append([county, precinct, office, None, party, line.split('\t')[0].replace(':','')] + [int(x) for x in line.split('\t')[1:]])
        else:
            print(line)
            # candidate result
            candidate = line.split('\t')[0]
            results.append([county, precinct, office, None, party, candidate, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[5].replace(',','')), int(line.split('\t')[7].replace(',',''))])

with open('20200303__tx__primary__cass__precinct2.csv', 'wt') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate','absentee', 'early_voting', 'election_day', 'votes'])
    writer.writerows(results)
