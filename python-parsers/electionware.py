import csv

county = 'Montague'

lines = open('/Users/derekwillis/code/openelections-sources-tx/2020/primary/MONTAGUE_COUNTY-2020_MARCH_3RD_REPUBLICAN_PRIMARY_332020-Republican Primary Precinct by Precinct March 2020.txt').readlines()
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
    if line[0:3] == 'PCT':
        precinct = line.strip()
    elif line[0:17] == 'Registered Voters':
        continue
        office = 'Registered Voters'
#        results.append([county, precinct, office, None, None, None, int(line.split('\t')[1].strip().replace(',','')), None, None, None])
        ballot_lines = 3
    elif ballot_lines == 0:
        results.append([county, precinct, 'Ballots Cast', None, None, None] + [int(x.replace(',','')) for x in line.split()])
        ballot_lines = 1
    elif line[0:12] == 'Ballots Cast':
        continue
    elif ballot_lines == 1:
        results.append([county, precinct, 'Ballots Cast', None, 'REP', None] + [int(x.replace(',','')) for x in line.split()])
        ballot_lines = 3
    elif ballot_lines == 2:
        results.append([county, precinct, 'Ballots Cast', None, 'DEM', None] + [int(x.replace(',','')) for x in line.split()])
        ballot_lines = 3
    elif ballot_lines > 2:
        if line[0:4] == 'REP ' or line[0:4] == 'DEM ':
            # office & party
            party = line[0:3]
            office = line[4:-1]
        elif line[0] == '\t':
            continue
        else:
            print(line)
            # candidate result
            candidate = line.split('\t')[0]
            results.append([county, precinct, office, None, 'REP', candidate, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3]), int(line.split('\t')[4]), int(line.split('\t')[5]), int(line.split('\t')[6])])

with open('20200303__tx__primary__montague__precinct.csv', 'wt') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'election_day', 'early_voting', 'mail', 'provisional'])
    writer.writerows(results)
