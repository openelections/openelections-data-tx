import csv

source = '/Users/derekwillis/code/openelections-sources-tx/2020/primary/JASPER_COUNTY-2020_MARCH_3RD_DEMOCRATIC_PRIMARY_332020-PCT REPORT WITH DETAIL.txt'
offices = ['Straight Party', 'President', 'US Senator', 'GOVERNOR', 'US Representative, District 34', 'Governor', 'Lieutenant Governor', 'Attorney General', 'Comptroller of Public Accounts', 'Commissioner of the General Land Office', 'Commissioner of Agriculture', 'Railroad Commissioner', 'State Representative, District 43']

lines = open(source).readlines()
results = []

for line in lines:
    if line == '\n':
        continue
    if line == 'DISTRICT\n':
        continue
    if "<" in line:
        continue
    if "PREC REPORT-GROUP DETAIL" in line:
        continue
    if "General Election" in line:
        continue
    if "NOVEMBER 6, 2018" in line:
        continue
    if "Report EL30A" in line:
        continue
    if "Run Date" in line:
        precinct = None
        continue
    if "TOTAL VOTES" in line:
        continue
    if 'Vote for  1' in line:
        continue
    if 'VOTER TURNOUT - TOTAL' in line:
        continue
    if any(o in line for o in offices):
        office = line.strip()
    if not ".  ." in line and not any(o in line for o in offices):
        precinct = line.strip()
    if ".  ." in line:
        if "REGISTERED VOTERS" in line:
            office = None
            candidate = "Registered Voters"
            party = None
            votes = line.split('.  .', 1)[1].split(' ',1)[1].replace('.','').strip()
            election_day, early_votes, mail, provisional, limited = ["", "", "", "", ""]
        elif "BALLOTS CAST" in line:
            office = None
            candidate = "Ballots Cast"
            party = None
            if len([x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']) == 6:
                votes, election_day, early_votes, mail, provisional, limited = [x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']
            else:
                fill, votes, election_day, early_votes, mail, provisional, limited = [x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']
        elif 'WRITE-IN' in line:
            candidate = 'Write-ins'
            party = None
            if len([x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']) == 6:
                fill, votes, election_day, absentee, emergency, provisional, federal = [x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']
            else:
                fill, votes, pct, election_day, absentee, emergency, provisional, federal = [x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']
        elif 'Total' in line:
            continue
        elif 'Over Votes' in line:
            candidate = 'Over Votes'
            party = None
            if len([x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']) == 6:
                fill, votes, election_day, absentee, emergency, provisional, federal = [x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']
            else:
                fill, votes, pct, election_day, absentee, emergency, provisional, federal = [x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']
        elif 'Under Votes' in line:
            candidate = 'Under Votes'
            party = None
            if len([x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']) == 6:
                fill, votes, election_day, absentee, emergency, provisional, federal = [x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']
            else:
                fill, votes, pct, election_day, absentee, emergency, provisional, federal = [x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']
        else:
            print(line)
            if '(' in line:
                candidate, party = line.split('(', 1)
                party = party[0:3]
            else:
                candidate = line.split(' .')[0]
                party = None
            candidate = candidate.strip()
            if len([x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']) == 7:
                fill, votes, election_day, early_votes, mail, provisional, limited = [x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']
            else:
                fill, votes, pct, election_day, early_votes, mail, provisional, limited = [x.strip() for x in line.split('.  .', 1)[1].split(' ',1)[1].split('   ') if x !='']
        results.append(['Kleberg', precinct, office, None, party, candidate, votes.replace(',','').strip(), election_day.replace(',','').strip(), early_votes.replace(',','').strip(), mail.replace(',','').strip(), provisional.replace(',','').strip(), limited.replace(',','').strip()])

with open('20181106__tx__general__kleberg__precinct.csv', 'wt') as csvfile:
    w = csv.writer(csvfile)
    headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'election_day', 'early_voting', 'mail', 'provisional', 'limited']
    w.writerow(headers)
    w.writerows(results)
