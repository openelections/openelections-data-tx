import csv

county = 'Brazoria'

lines = open('/Users/derekwillis/code/openelections-sources-tx/2020/primary/Brazoria TX RepublicanPrimaryPrecinctR.txt').readlines()
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
    if 'Registered Voters - ' in line:
        print(line)
        precinct = line.split()[0]
        office = 'Registered Voters'
        ballot_lines = 0
        if reg_voters is False:
            results.append([county, precinct, office, None, None, None, None, None, None, int(line.split()[3].strip().replace(',',''))])
            reg_voters = True
    elif "Democratic Party" in line or "Republican Party" in line:
        office = line.strip().split(' - ')[0]
        party = 'REP'
    elif 'Cast Votes:' in line:
        if ballot_lines == 0:
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
            if candidate == 'Yes' or candidate == 'No' or candidate == 'Uncommitted':
                results.append([county, precinct, office, None, party, candidate, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[5].replace(',','')), int(line.split('\t')[7].replace(',',''))])
            else:
                results.append([county, precinct, office, None, party, candidate, int(line.split('\t')[2].replace(',','')), int(line.split('\t')[4].replace(',','')), int(line.split('\t')[6].replace(',','')), int(line.split('\t')[8].replace(',',''))])

with open('20200303__tx__primary__brazoria__precinct.csv', 'wt') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate', 'absentee', 'early_voting', 'election_day', 'votes'])
    writer.writerows(results)
