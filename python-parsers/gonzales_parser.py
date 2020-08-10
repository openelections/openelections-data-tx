#!/usr/bin/env python3

# To run:
#
# ./parser.py filename
#
# Outputs results to stdout
#
# To write to a file, run:
#
# ./parser.py filename >output.csv
#

import sys
import re

def split_csv_line(line):
    # split the line using a ',' delimiter
    parts = line.split(',')

    # Go through the parts and correctly handle values enclosed in double quotes
    handled_parts = []
    first = None
    for p in parts:
        # if the value doesn't contain a double-quote, append it to the list
        if not '"' in p:
            # Is this a subsequent part of a double-quoted value?
            if first is not None:
                # If so, add it to the existing value
                first = first + "," + p
            else:
                # Otherwise add it to the list
                handled_parts.append(p)
        elif p[0] == '"':
            # If the first and last characters are '"', append it to the list
            if p[-1] == '"':
                handled_parts.append(p)
            else:
                # otherwise we've found the first part of a double-quoted value
                first = p
        elif p[-1] == '"':
            # We've found the last part of a double-quoted value
            first = first + "," + p
            handled_parts.append(first)
            first = None

    return handled_parts

def read_data_from_csv(filename):
    with open(filename, 'r') as results_file:

        for line in results_file:
            l = line.rstrip().lstrip()
            if "COUNTY NUMBER" in l:
                break

        # Get the ballot offices
        offices = split_csv_line(l)
        #    for p in offices:
        #        print(p)
        #    print("--------------------------------------------------------------------------------")
        # Get the party for each candidate
        affiliations = split_csv_line(results_file.readline().rstrip().lstrip())
        #    for p in affiliations:
        #        print(p)
        #    print("--------------------------------------------------------------------------------")
        # Get the candidates
        candidate_names = split_csv_line(results_file.readline().rstrip().lstrip())
        #    for p in candidate_names:
        #        print(p)
        #    print("--------------------------------------------------------------------------------")

        records = []
        for i in range(8,len(candidate_names)):
            if candidate_names[i] == '':
                continue

            if affiliations[i] in offices[i]:
                # strip affilication from office
                offices[i] = offices[i].replace(affiliations[i], '').replace('" ', '"').lstrip()

            dist = ''
            if "Dist " in offices[i]:
                # strip district number from office and move it to "dist" field
                m = re.search("Dist ([0-9]*)", offices[i])
                dist = m.group(1)
                str = ", Dist %s" % (dist)
                offices[i] = offices[i].replace(str, '')
            elif "District " in offices[i]:
                # strip district number from office and move it to "dist" field
                m = re.search("District ([0-9]*)", offices[i])
                dist = m.group(1)
                str = " District %s" % (dist)
                offices[i] = offices[i].replace(str, '')

            record = { 'office': offices[i], 'affiliation': affiliations[i], 'name': candidate_names[i], 'district': dist }
            records.append(record)

        precincts = {}

        for line in results_file:
            l = line.rstrip().lstrip()
            fields = l.split(',')

            if len(fields) <= 3:
                continue
            county = fields[0]
            precinct_code = fields[1]
            if precinct_code == '' or precinct_code == 'ZZZ' or precinct_code == '"ZZZ"':
                continue
            precinct_name = fields[2]

            if not precinct_code in precincts:
                precinct = {}
                precinct['county'] = county
                precinct['precinct'] = precinct_code
                precinct['votes'] = { 'votes': [], 'election_day': [], 'early_voting': [], 'mail': [], 'provisional': [] }
                precincts[precinct_code] = precinct
            else:
                precinct = precincts[precinct_code]

            vote_type = None
            if "Election Day" in precinct_name:
                vote_type = "election_day"
            elif "EarlyVoting" in precinct_name:
                vote_type = "early_voting"
            elif "Mail" in precinct_name:
                vote_type = "mail"
            elif "Provisional" in precinct_name:
                vote_type = "provisional"

            if vote_type is not None:
                for i in range(8, len(fields)):
                    if fields[i] != '':
                        precinct['votes'][vote_type].append(int(fields[i]))
            else:
                for i in range(8, len(fields)):
                    if fields[i] != '':
                        precinct['votes']['votes'].append(int(fields[i]))

        return (precincts, records)

def write_standard_csv(data):
    precincts = data[0]
    records = data[1]
    keys = [*precincts]
    print("county,precinct,office,district,candidate,party,votes,early_voting,election_day,mail,provisional")
    for k in keys:
        precinct = precincts[k]
        county = precinct['county']
        precinct_code = precinct['precinct']
        votes = precinct['votes']['votes']
        election_day = precinct['votes']['election_day']
        early_voting = precinct['votes']['early_voting']
        mail = precinct['votes']['mail']
        provisional = precinct['votes']['provisional']

        for i in range(0, len(records)):
            record = records[i]
            if len(votes) > 0:
                total_votes = votes[i]
                early_votes = 0
                election_day_votes = 0
                mail_votes = 0
                provisional_votes = 0
            else:
                early_votes = early_voting[i]
                election_day_votes = election_day[i]
                mail_votes = mail[i]
                provisional_votes = provisional[i]
                total_votes = election_day_votes + mail_votes + early_votes + provisional_votes
            print("%s,%s,%s,%s,%s,%s,%d,%d,%d,%d,%d" % (county, precinct_code, record['office'], record['district'], record['name'], record['affiliation'], total_votes, early_votes, election_day_votes, mail_votes, provisional_votes))

#
#
#
filename = sys.argv[1]

data = read_data_from_csv(filename)
write_standard_csv(data)
