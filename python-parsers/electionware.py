import csv

county = 'Yoakum'

lines = open('/Users/dwillis/Downloads/Yoakum TX 2020 Primary Precinct (002).txt').readlines()
results = []
reg_voters = False

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
    if line[0:8] == 'PRECINCT':
        precinct = line.strip()
    elif line[0:17] == 'Registered Voters':
        office = 'Registered Voters'
        results.append([county, precinct, office, None, None, None, int(line.split('\t')[1].strip().replace(',','')), None, None, None])
        ballot_lines = 0
        reg_voters = True
    elif ballot_lines == 0:
        results.append([county, precinct, 'Ballots Cast', None, None, None] + [int(x.replace(',','')) for x in line.split('\t')[1:]])
        ballot_lines = 1
    elif ballot_lines == 1:
        results.append([county, precinct, 'Ballots Cast', None, 'REP', None] + [int(x.replace(',','')) for x in line.split('\t')[1:]])
        ballot_lines = 2
    elif ballot_lines == 2:
        results.append([county, precinct, 'Ballots Cast', None, 'DEM', None] + [int(x.replace(',','')) for x in line.split('\t')[1:]])
        ballot_lines = 3
    elif ballot_lines > 2:
        print(line)
        if line[0:4] == 'REP ' or line[0:4] == 'DEM ':
            # office & party
            party = line[0:3]
            office = line[4:-1]
        else:
            # candidate result
            candidate = line.split('\t')[0]
            results.append([county, precinct, office, None, party, candidate, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[2]), int(line.split('\t')[3]), int(line.split('\t')[4])])

with open('20200303__tx__primary__yoakum__precinct.csv', 'wt') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'mail', 'early_voting', 'election_day'])
    writer.writerows(results)
