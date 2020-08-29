import csv

county = 'DeWitt'

lines = open('/Users/derekwillis/code/openelections-sources-tx/2020/primary/PARKER_COUNTY-2020_MARCH_3RD_DEMOCRATIC_PRIMARY_332020-Precinct Results-3-10-2020 01-27-09 PM.txt').readlines()
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
    if 'registered voters = ' in line:
        precinct = line.split()[0]
        office = 'Registered Voters'
        if reg_voters is False:
            results.append([county, precinct, office, None, None, None, None, None, None, None, None, int(line.split()[1].strip().replace(',',''))])
            reg_voters = True
    elif "Democratic Party" in line or "Republican Party" in line:
        office, party = line.strip().split(' - ')
    elif 'Cast Votes' in line:
        results.append([county, precinct, 'Ballots Cast', None, party, None, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[5].replace(',','')), int(line.split('\t')[7].replace(',','')), int(line.split('\t')[9].replace(',','')), int(line.split('\t')[11].replace(',',''))])
        ballot_lines = 1
    else:
        if 'Undervotes' in line or 'Overvotes' in line:
            results.append([county, precinct, office, None, party, line.split('\t')[0].replace(':','')] + [int(x) for x in line.split('\t')[1:]])
        else:
            print(line)
            # candidate result
            candidate = line.split('\t')[0]
            results.append([county, precinct, office, None, party, candidate, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[5].replace(',','')), int(line.split('\t')[7].replace(',','')), int(line.split('\t')[9].replace(',','')), int(line.split('\t')[11].replace(',',''))])

with open('20200303__tx__primary__parker__precinct.csv', 'wt') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate', 'absentee', 'early_voting', 'election_day', 'provisional', 'limited', 'votes'])
    writer.writerows(results)
