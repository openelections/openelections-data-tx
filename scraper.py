import requests
from BeautifulSoup import BeautifulSoup
import unicodecsv

def get_elections():
    r = requests.get('http://elections.sos.state.tx.us/index.htm')
    soup = BeautifulSoup(r.text)
    return [{'election_code': o['value'], 'title': o.text} for o in soup.select('option')]

def get_counties():
    r = requests.get('http://elections.sos.state.tx.us/elchist175_countyselect.htm')
    soup = BeautifulSoup(r.text)
    return [{'id': o['value'], 'name': o.text} for o in soup.select('option')]

def get_countylist(election_code):
    r = requests.get('http://elections.sos.state.tx.us/elchist%s_countyselect.htm' % election_code)
    soup = BeautifulSoup(r.text)
    return [{'id': o['value'], 'name': o.text} for o in soup.select('option')]

def get_elections_by_type(election_type):
    return [(x['value'], x.string) for x in get_elections() if election_type in x.string.lower()]

def get_results(election_code, county=None, counties=None):
    results = []
    if county:
        base_url = "http://elections.sos.state.tx.us/elchist%s_county%s.htm" % (election_code, county)
    else:
        base_url = "http://elections.sos.state.tx.us/elchist%s_state.htm" % (election_code)
    r = requests.get(base_url)
    soup = BeautifulSoup(r.text)
    table = soup.find('table')
    if not table:
        return None
    for row in table.findAll('tr')[1:]:
        cells = [x.text.replace("-","") for x in row.findAll('td') if x.text.replace("-","") != '']
        if len(cells) == 0:
            continue
        elif len(cells) == 1:
            office = cells[0]
            if "Criminal District Judge" in office and "Number" in office:
                office, district = office.split(' Number ')
            elif "Criminal District Judge" in office:
                district = None
            elif "District Judge" in office:
                district = office.split('District Judge, ')[1]
                office = 'District Judge'
            elif "Chief Justice" in office:
                district = None
            elif "Justice" in office:
                district = None
            elif "Judicial District" in office:
                office, district = office.split(',')
            elif "Place" in office:
                office, district = office.split(' Place ')
                office = office.replace(",","")
            elif " District" in office:
                office, district = office.split(' District ')
                office = office.replace(",","")
            else:
                district = None
        elif len(cells) == 2:
            r = [office, district, 'Total', None, None, cells[1].replace(',',''), None]
            if county:
                county_name = (c['name'] for c in counties if c['id'] == county).next()
                r.insert(0, county_name)
            results.append(r)
        elif len(cells) == 3:
            r = [office, district, cells[0], None, None, cells[1].replace(',',''), cells[2].replace('%','')]
            if county:
                county_name = (c['name'] for c in counties if c['id'] == county).next()
                r.insert(0, county_name)
            results.append(r)
        else:
            candidate = cells[0]
            if '(I)' in cells[0]:
                incumbent = True
                candidate = candidate.split('(')[0]
            else:
                incumbent = False
            party = cells[1]
            votes = cells[2].replace(',','')
            pct = cells[3].replace('%','')
            r = [office, district, candidate, incumbent, party, votes, pct]
            if county:
                county_name = (c['name'] for c in counties if c['id'] == county).next()
                r.insert(0, county_name)
            results.append(r)
    return results

def statewide_results(code, filename):
    with open(filename, 'wb') as csvfile:
        w = unicodecsv.writer(csvfile, encoding='utf-8')
        w.writerow(['office', 'district', 'candidate', 'incumbent', 'party', 'votes', 'pct'])
        results = get_results(code, county=False)
        for result in results:
            w.writerow(result)

def county_results(code, filename):
    with open(filename, 'wb') as csvfile:
        w = unicodecsv.writer(csvfile, encoding='utf-8')
        w.writerow(['county', 'office', 'district', 'candidate', 'incumbent', 'party', 'votes', 'pct'])
        counties = get_counties()
        county_list = get_countylist(code)
        election_counties = [c for c in counties if c in county_list]
        for county in election_counties:
            results = get_results(code, county=county['id'], counties=counties)
            for result in results:
                w.writerow(result)

def process_elections(end_code=None):
    elections = get_elections()
    if end_code:
        elections = [e for e in elections if int(e['election_code']) < end_code]
    for election in elections:
        statewide_results(election['election_code'], election['election_code']+'.csv')
        county_results(election['election_code'], election['election_code']+'__county.csv')
