import os
import glob
import csv

year = '2020'
election = '20201103'
path = election+'*precinct.csv'
output_file = election+'__tx__general__precinct.csv'

def generate_headers(year, path):
    os.chdir(year)
    os.chdir('counties')
    vote_headers = []
    for fname in glob.glob(path):
        print(fname)
        with open(fname, "r") as csvfile:
            dict_reader = csv.DictReader(csvfile)
            row = next(dict_reader)
            headers = list(row.keys())
            print(set(list(h for h in headers if h not in ['county','precinct', 'office', 'district', 'candidate', 'party'])))
            c = { 'county': row['county'], 'votes': False, 'mail': False, 'absentee': False, 'early_voting': False, 'election_day': False, 'provisional': False, 'limited': False, 'other': False}
            if 'votes' in headers:
                c['votes'] = True
                headers.remove('votes')
            if 'mail' in headers:
                c['mail'] = True
                headers.remove('mail')
            if 'absentee' in headers:
                c['absentee'] = True
                headers.remove('absentee')
            if 'early_voting' in headers:
                c['early_voting'] = True
                headers.remove('early_voting')
            if 'election_day' in headers:
                c['election_day'] = True
                headers.remove('election_day')
            if 'provisional' in headers:
                c['provisional'] = True
                headers.remove('provisional')
            if 'limited' in headers:
                c['limited'] = True
                headers.remove('limited')
            if len(headers) > 6:
                c['other'] = True
            vote_headers.append(c)
    with open(f"../{election}__tx__general__headers.csv", "w") as csv_outfile:
        outfile = csv.writer(csv_outfile)
        outfile.writerow(['county', 'votes', 'mail', 'absentee', 'early_voting', 'election_day', 'provisional', 'limited', 'other'])
        for row in sorted(vote_headers, key = lambda i: i['county']):
            outfile.writerow([row['county'], row['votes'], row['mail'], row['absentee'], row['early_voting'], row['election_day'], row['provisional'], row['limited'], row['other']])

def generate_offices(year, path):
    os.chdir(year)
    os.chdir('counties')
    offices = []
    for fname in glob.glob(path):
        with open(fname, "r") as csvfile:
            print(fname)
            reader = csv.DictReader(csvfile)
            for row in reader:
                if not row['office'] in offices:
                    offices.append(row['office'])
    with open('offices.csv', "w") as csv_outfile:
        outfile = csv.writer(csv_outfile)
        outfile.writerows(offices)

def generate_consolidated_file(year, path, output_file):
    results = []
    os.chdir(year)
    os.chdir('counties')
    for fname in glob.glob(path):
        with open(fname, "r") as csvfile:
            print(fname)
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['office'].strip() in ['Straight Party', 'President', 'Governor', 'Lieutenant Governor', 'Attorney General', 'Comptroller of Public Accounts', 'Commissioner of Agriculture', 'Commissioner of the General Land Office', 'Railroad Commissioner', 'U.S. House', 'State Senate','U.S. Senate', 'State Representative', 'Registered Voters', 'Ballots Cast', 'Blank Ballots Cast']:
                    if all(k in set(row) for k in ['absentee', 'election_day', 'early_voting', 'provisional', 'limited']):
                        results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], row['absentee'], row['election_day'], row['early_voting'], None, row['provisional'], row['limited']])
                    elif all(k in set(row) for k in ['absentee', 'election_day', 'early_voting', 'mail', 'provisional']):
                        results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], row['absentee'], row['election_day'], row['early_voting'], row['mail'], row['provisional'], None])
                    elif all(k in set(row) for k in ['absentee', 'election_day', 'early_voting', 'mail']):
                        results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], row['absentee'], row['election_day'], row['early_voting'], row['mail'], None, None])
                    elif all(k in set(row) for k in ['absentee', 'election_day', 'early_voting', 'provisional']):
                        results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], row['absentee'], row['election_day'], row['early_voting'], row['provisional'], None, None])
                    elif all(k in set(row) for k in ['absentee', 'election_day', 'early_voting']):
                        results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], row['absentee'], row['election_day'], row['early_voting'], None, None, None])
                    elif all(k in set(row) for k in ['provisional', 'election_day', 'early_voting']):
                        results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], None, row['election_day'], row['early_voting'], None, None, None])
                    elif all(k in set(row) for k in ['election_day', 'early_voting', 'mail']):
                        results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], None, row['election_day'], row['early_voting'], None, None, None])
                    elif all(k in set(row) for k in ['election_day', 'early_voting']):
                        results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], None, row['election_day'], row['early_voting'], None, None, None, None])
                    else:
                        results.append([row['county'], row['precinct'], row['office'], row['district'], row['candidate'], row['party'], row['votes'], None, None, None, None, None, None])

    os.chdir('..')
    os.chdir('..')
    with open(output_file, "w") as csv_outfile:
        outfile = csv.writer(csv_outfile)
        outfile.writerow(['county','precinct', 'office', 'district', 'candidate', 'party', 'votes', 'absentee', 'election_day', 'early_voting', 'mail', 'provisional', 'limited'])
        outfile.writerows(results)
