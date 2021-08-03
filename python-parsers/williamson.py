import requests
from lxml import etree
import exceptions as exc
import logging, os
import pandas as pd

class CountyScraper(object):
    """Parent class for historical and enight scraper classes."""
    COUNTY_RACE_URL = None
    logger = None
    COUNTY = None

    def __init__(self, county):
        self.logger = logging.getLogger(__name__)
        self.COUNTY = county

    def download(self, url):
        raise NotImplementedError('Must use a child class to parse content')

    def get_file_name(self, race):
        race = race.replace(' ', '_').replace(',', '').lower()

        if race == 'united_states_senator':
            race = 'u_s_senator'

        filename = 'output/{county}_{race}_precinct_level.csv'.format(county=self.COUNTY, race=race)

        return filename

class DownloadWilliamson(CountyScraper):

    def __init__(self):
        super().__init__('williamson')

    def download(self, url):
        """Downlaod the page, check whether it has changed since last download, and return content.
        """
        self.logger.debug('Downloading %s', url)
        source = url
        resp = requests.get(url)
        try:
            resp.raise_for_status()
        except requests.exceptions.SSLError as err:
            raise exc.PageDownloadError('Could not download {}: {}'.format(url, err))
        content = resp.content

        if not content:
            raise exc.EmptyPageContentError('Read no content from {}'.format(source))

        content = content.decode('latin-1')
        return content

    def _parse_table(self, table):
        def parse_row(row):
            """Takes an lxml row and parses it into columns."""
            columns = []
            for col in row:
                # Need to handle colspan so everything remains aligned
                properties = dict(zip(col.keys(), col.values()))
                colspan = properties.get('colspan')
                colspan = colspan and int(colspan)
                # Iterate to the innermost tag to get the value
                while len(col) > 0:
                    if len(col) > 1:
                        raise exc.PageStructureError(
                            'HTML column element {} has more than one child: {}'.format(
                                col.tag, col.getchildren()))
                    col = col[0]
                columns.append(col.text)
                if colspan:
                    columns.extend([None] * (colspan - 1))
            return columns

        headerrows = []
        bodyrows = []
        for i in range(0, len(table)):
            if i == 0:
                rowlist = headerrows
            else:
                rowlist = bodyrows
            rowlist.append(parse_row(table[i]))
        return headerrows, bodyrows

    def scrape_candidates(self, tree):
        self.logger.info('scrape_candidates')

        elements = tree.findall(".//div[@class='resultAreaDiv']")
        all_candidates = {}
        for element in elements:
            my_element = element[0]
            for i in range(1, len(my_element)):
                candidate = my_element[i][0].text
                party = my_element[i][1][0][0].attrib['src'].replace('./images/bluebar.png', 'DEM').\
                    replace('./images/redbar.png', 'REP').replace('./images/goldbar.png', 'LIB').\
                    replace('./images/greenbar.png', 'GREEN').replace('./images/nocolorbar.png', 'NA')
                self.logger.info('Candidate: {candidate}, Party: {party}'.format(candidate=candidate, party=party))
                all_candidates[candidate] = party

        #cache in DF
        df = pd.DataFrame.from_dict(all_candidates, orient='index', columns=['party'])
        df.to_csv('candidate_cache.csv')

        return all_candidates

def main():
    election_map = {'2020': {'e-id': '764184', 'date':'20201103'}}
    logging.basicConfig(format='%(asctime)s %(name)s |  %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)
    wilco = DownloadWilliamson()

    for year in election_map.keys():

        #Go to main URL
        main_url = 'https://apps.wilco.org/elections/results/default.aspx?e={eid}'.format(eid=election_map[year]['e-id'])
        content = wilco.download(main_url)

        #Grab contest ids
        logger.info('Parsing statewide')
        parser = etree.HTMLParser(remove_blank_text=True)
        tree = etree.fromstring(content, parser=parser)
        elements = tree.findall(".//div[@class='contestBar']")

        # Scrape candidates
        all_candidates = wilco.scrape_candidates(tree)

        all_ids = {}
        for element in elements:
            all_ids[element[0].attrib['id']] = element[0].text.rstrip()

        #Loop through contest ids to pull precinct level results
        dfs = []
        for id in all_ids.keys():
            logger.info('Parsing {race}'.format(race=all_ids[id]))
            contest_precinct_results = 'https://apps.wilco.org/elections/results/contest.aspx?' \
                                       'c={id}&e={eid}&t=0'.format(id=id, eid=election_map[year]['e-id'])
            logger.info(contest_precinct_results)

            race_content = wilco.download(contest_precinct_results)
            race_tree = etree.fromstring(race_content, parser=parser)
            precinct_elements = race_tree.findall(".//div[@class='barWrap']")
            results_elements = race_tree.findall(".//div[@class='resultAreaDiv']")
            if (len(precinct_elements)) != (len(results_elements)):
                logger.error('Results not equal')
                return

            all_race_results = []
            for i in range(0, len(precinct_elements)):
                race_results = {}
                logger.info('Precint: {pct}'.format(pct=precinct_elements[i][0].attrib['id']))
                race_results['Precinct'] = precinct_elements[i][0].attrib['id']
                table = results_elements[i][0]
                headerrows, bodyrows = wilco._parse_table(table)
                headerrows = dict(zip(headerrows[0], range(len(headerrows[0]))))

                for row in bodyrows:
                    race_results = {'precinct': precinct_elements[i][0].attrib['id'],
                                    'party': all_candidates[row[headerrows['Candidate/Choice']]],
                                    'candidate': row[headerrows['Candidate/Choice']], 'votes': row[headerrows['Votes']]}
                    all_race_results.append(race_results)

            df = pd.DataFrame(all_race_results)

            logger.info(list(df))
            df['county'] = 'Williamson'
            if all_ids[id] == 'United States Senator US REPRESENTATIVE DISTRICT 31':
                office = 'United States Senator'
            else:
                office = all_ids[id]

            office = office.split(', ')
            df['office'] = office[0]
            if len(office) == 2:
                df['district'] = office[1]
            else:
                df['district'] = ''

            df['early_votes'] = 0
            df['election_day'] = 0
            print(list(df))
            df = df[['county','precinct','office','district','party','candidate','votes','early_votes','election_day']]
            dfs.append(df)

        all_dfs = pd.concat(dfs, sort=True)
        all_dfs = all_dfs[['county','precinct','office','district','party','candidate','votes','early_votes','election_day']]
        all_dfs.to_csv('../{year}/{date}__tx__general__williamson__precinct.csv'.format(year=year, date=election_map[year]['date']), index=False)

def ensure_dir(file_path):
    if not os.path.exists(file_path):
        os.makedirs(file_path)

if __name__ == '__main__':
    main()
