import csv

county = 'San Jacinto'

lines = open('/Users/dwillis/code/openelections-sources-tx/2020/primary/San Jacinto TX Precinct Results PRIM 20.txt').readlines()
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
    if len(line.strip()) < 3:
        precinct = line.strip()
    elif "Democratic Party" in line or "Republican Party" in line:
        print(line)
        office, party = line.strip().split(' - ')
    elif 'Cast Votes' in line and office == 'President':
        results.append([county, precinct, 'Ballots Cast', None, party, None, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[5].replace(',','')), int(line.split('\t')[7].replace(',',''))])
        ballot_lines = 1
    else:
        if 'Undervotes' in line or 'Overvotes' in line:
            print(line)
            results.append([county, precinct, office, None, party, line.split('\t')[0].replace(':','')] + [int(x) for x in line.split('\t')[1:]])
        else:
            print(line)
            # candidate result
            candidate = line.split('\t')[0]
            results.append([county, precinct, office, None, party, candidate, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[5].replace(',','')), int(line.split('\t')[7].replace(',',''))])

with open('20200303__tx__primary__san_jacinto__precinct.csv', 'wt') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate', 'election_day', 'absentee', 'early_voting', 'votes'])
    writer.writerows(results)
