import csv

county = 'Jasper'

lines = open('/Users/derekwillis/code/openelections-sources-tx/2020/primary/JASPER_COUNTY-2020_MARCH_3RD_DEMOCRATIC_PRIMARY_332020-PCT REPORT WITH DETAIL.txt').readlines()
results = []
reg_voters = False

for line in lines:
    if line.strip() == '':
        continue
    if 'BALLOTS CAST - NONPARTISAN' in line:
        continue
    if 'BALLOTS CAST - BLANK' in line:
        continue
    if line.strip() == 'Voter Turnout - Total':
        continue
    if "VOTER TURNOUT" in line:
        continue
    if line[0:14] == 'Contest Totals':
        continue
    if line[len(line.strip())-1] == '%':
        continue
    if " BOX " in line:
        precinct = line[5:].strip()
        ballot_lines = 0
    elif 'REGISTERED VOTERS - TOTAL' in line:
        office = 'Registered Voters'
        results.append([county, precinct, office, None, None, None, int(line.split('\t')[1].strip().replace(',','')), None, None, None])
    elif 'BALLOTS CAST - TOTAL' in line:
        results.append([county, precinct, 'Ballots Cast', None, None, None, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[2].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[4].replace(',',''))])
    elif 'BALLOTS CAST - Republican Party' in line:
        results.append([county, precinct, 'Ballots Cast', None, 'REP', None, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[4].replace(',','')), int(line.split('\t')[5].replace(',',''))])
    elif 'BALLOTS CAST - Democratic Party' in line:
        results.append([county, precinct, 'Ballots Cast', None, 'DEM', None, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[4].replace(',','')), int(line.split('\t')[5].replace(',',''))])
    elif len(line.split('\t')) == 4:
        continue
    else:
        if line[0:4] == 'REP ' or line[0:4] == 'DEM ':
            # office & party
            party = line[0:3]
            office = line[4:-1]
        else:
            # candidate result
            candidate = line.split('\t')[0]
            if len(line.split('\t')) > 5:
                results.append([county, precinct, office, None, party, candidate, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[4].replace(',','')), int(line.split('\t')[5].replace(',',''))])
            else:
                results.append([county, precinct, office, None, party, candidate, int(line.split('\t')[1].replace(',','')), int(line.split('\t')[2].replace(',','')), int(line.split('\t')[3].replace(',','')), int(line.split('\t')[4].replace(',',''))])

with open('20200303__tx__primary__jasper__precinct.csv', 'wt') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'mail', 'early_voting', 'election_day'])
    writer.writerows(results)
