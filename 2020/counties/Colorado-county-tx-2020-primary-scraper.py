import os
import pdfplumber
import csv
import re

####
# Takes two pdf files:
#
# COLORADO_COUNTY-2020_MARCH_3RD_REPUBLICAN_PRIMARY_332020-Republican Precinct Summary.pdf
# COLORADO_COUNTY-2020_MARCH_3RD_DEMOCRATIC_PRIMARY_332020-Democrat Precinct Summary.pdf
#
# Returns a csv
# 20200303__tx__primary__colorado__precinct.csv
# with headers:
# header_row = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'total_votes', 'election_day_votes',
#               'early_voting', 'ballots_by_mail']
#
# Note to self: PyPDF didn't work
#####

# get just the pdfs in the directory

all_files = os.listdir()
pdfs = []
for item in all_files:
    if 'pdf' in item:
        pdfs.append(item)

header_row = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'total_votes', 'election_day_votes',
              'early_voting', 'ballots_by_mail']

# all the possible offices we will see
offices = ['President', 'Senator', 'Representative', 'Judge', 'Justice', 'Proposition', 'County', 'Commissioner',
           'Constable', 'Sheriff']

# all the offices we want
state_fed_offices = ['President', 'Senate', 'House', 'Judge', 'Justice', 'Proposition', 'Railroad']

county = 'Colorado'
precinct = 'precinct not found'
office = 'office not found'
district = ''
party = 'party not found'
candidate = 'cand not found'
total_votes = ''
election_day_votes = ''
early_voting = ''
ballots_by_mail = ''


with open('20200303__tx__primary__colorado__precinct.csv', 'a') as csvfile:
    csvwriter = csv.writer(csvfile)
    csvwriter.writerow(header_row)

    for item in pdfs:
        pdf = pdfplumber.open(item)
        if 'Republican' in item:
            party = 'Republican'
        elif 'Democrat' in item:
            party = 'Democrat'
        else:
            party = 'No party found'

        # set up an temporary empty list to which to append all the rows that will come off all the pages

        all_rows = []
        for page in pdf.pages:
            # get the text
            single_page = page.extract_text()
            # split it on \n
            split = single_page.splitlines()
            for row in split:
                working_row = [county, party] + [row]
                all_rows.append(working_row)

        # OK now let's remove the rows that are extraneous
        # set up another temporary empty list to hold just what we need

        rows_with_results = []

        for row in all_rows:
            if any('Report' in s for s in row):
                pass
            elif any('TOTAL' in s for s in row):
                pass
            elif any('Day Voting Mail' in s for s in row):
                pass
            elif any('Registered Voters' in s for s in row):
                pass
            elif any('Ballots Cast' in s for s in row):
                pass
            elif any('Summary Results' in s for s in row):
                pass
            elif any('Primary Election' in s for s in row):
                pass
            elif any('Colorado County' in s for s in row):
                pass
            elif any('Vote For 1' in s for s in row):
                pass
            elif any('Total' in s for s in row):
                pass
            elif any('Party' in s for s in row):
                pass
            else:
                rows_with_results.append(row)

        # set up another temporary list that will hold rows, laid out in tabular format

        rows_tabular = []
        last_chunk = ''
        for row in rows_with_results:

            if any('Precinct' in s for s in row):
                substring = 'Precinct'
                result = list(filter(lambda x: substring in x, row))
                precinct = result[0].replace('Precinct ', '')

            # else if any of the offices we want is in the row, update the office variable
            elif any(single_office in row[2] for single_office in offices):
                unparsed_office = row[2].replace('REP ', '').replace('DEM ', '')

                # now unpick the offices
                if 'Chief Justice' in unparsed_office:
                    office = unparsed_office
                    district = ''

                # if it's not a chief justice of something, find the last comma in any given string.
                # The last comma will set of a district or judicial "place"
                else:
                    result = unparsed_office.rsplit(', ', 1)
                    if len(result) > 1:
                        office = result[0].replace('#', '')\
                            .replace('US Senator', 'U.S. Senate')\
                            .replace('US Representative', 'U.S.House')\
                            .replace('State Senator', 'State Senate')\
                            .replace('State Representative', 'State House')
                        district = result[1].replace('Dist', '').replace('Pl', '')
                    else:
                        office = result[0].replace('#', '')\
                            .replace('US Senator', 'U.S. Senate')\
                            .replace('US Representative', 'U.S.House')\
                            .replace('State Senator', 'State Senate')\
                            .replace('State Representative', 'State House')
                        district = ''
            else:
                # the only kind of row left is a row with names and results
                chunk = row[2]

                # split the name from the votes
                first_digit = (re.search('\d+', chunk).start())

                candidate = chunk[:first_digit].strip()

                vote_chunk = chunk[first_digit:]
                votes_separate = vote_chunk.split(' ')
                total_votes = int(votes_separate[0])
                election_day_votes = int(votes_separate[2])
                early_voting = int(votes_separate[3])
                ballots_by_mail = int(votes_separate[4])

                # test here
                if total_votes != election_day_votes + early_voting + ballots_by_mail:
                    print("total problem here: ", row)
                    break

                row_to_write = [county, precinct, office, district, party, candidate, total_votes, election_day_votes,
                                early_voting, ballots_by_mail]
                rows_tabular.append(row_to_write)

        # one last step, write only the state & federal offices
        # skip the local offices
        for row in rows_tabular:
            if any(single_state_fed_office in row[2] for single_state_fed_office in state_fed_offices):
                csvwriter.writerow(row)
            else:
                pass

csvfile.close()