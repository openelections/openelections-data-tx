import csv

county = 'Willacy'

lines = open('/Users/derekwillis/code/openelections-sources-tx/2020/primary/Willacy TX precinct precinct report march 03,2020.txt').readlines()
results = []

for line in lines:
    if line.strip() == '':
        continue
    if line.strip() == 'Ballots Cast - Republican Party':
        continue
    if line.strip() == 'Ballots Cast - Total':
        continue
    if line.strip() == 'Ballots Cast - Blank':
        continue
    if line.strip() == 'Voter Turnout - Total':
        continue
    if line[0:14] == 'Contest Totals':
        continue
    if 'Ballots Cast' in line:
        precinct = line.split('(')[0].strip()
    elif 'REPUBLICAN PARTY' in line or 'DEMOCRATIC PARTY' in line:
        office, party = line.split('\t')
    elif 'Cast Votes' in line:
        results.append([county, precinct, office, None, party, 'Ballots Cast', int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[5].replace(',',''))])
        ballot_lines = 1
    else:
        if len(line.split('\t')) == 4:
            continue
#            'Undervotes' in line or 'Overvotes' in line:
#            results.append([county, precinct, office, None, party, line.split('\t')[0].replace(':','')] + [int(x) for x in line.split('\t')[1:]])
        else:
            print(line)
            # candidate result
            candidate = line.split('\t')[0]
            results.append([county, precinct, office, None, party, candidate, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[5].replace(',',''))])

with open('20200303__tx__primary__willacy__precinct.csv', 'wt') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate', 'early_voting', 'election_day', 'votes'])
    writer.writerows(results)
