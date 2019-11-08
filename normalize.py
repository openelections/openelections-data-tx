#!/usr/bin/env python

import sys
import csv
import io
import re
import argparse

# All csv line endings should be unix style
class excel_unix(csv.excel):
    lineterminator = '\n'
csv.register_dialect("excel-unix", excel_unix)

# preferred column order
colorder = ['county', 'precinct', 'precinct_name', 'office', 'district', 'party',
    'candidate', 'incumbent',
    'votes', 'pct', 'election_day', 'election_day_machine', 'election_day_paper',
    'election_day_ada', 'early/absentee',
    'early_voting', 'early_voting_machine', 'early_voting_paper',
    # I believe these can be mapped to machine and paper above, but not confirmed
    'early_voting_ts', 'early_voting_os',
    'absentee', 'mail', 'provisional', 'limited', 'ballot_style']


def remove_unnamed_columns(path):
    lines = []
    with open(path, 'rb') as f:
        headers = f.readline()
        eol = '\n'
        if headers[-2] == '\r':
            eol = '\r\n'
        
        if headers[-len(eol):] == eol:
            headers = headers[:-len(eol)]
        
        headers_nonempty = headers.rstrip(',')
        if headers_nonempty == headers:
            # No trailing non-empty column names
            return
        lines.append(headers_nonempty + eol)
        
        nempty = len(headers) - len(headers_nonempty)
        end = (','*nempty)
        while True:
            row = f.readline()
            if not row:
                break
            
            if row[-len(eol):] == eol:
                row = row[:-len(eol)]
            
            if not row.endswith(end):
                print("{}: Not removing unnamed columns because there is data in some of them {!r}".format(path, (nempty, row[len(row)-len(end):])))
                return
            row = row[:-len(end)] + eol
            lines.append(row)
    
    with open(path, 'wb') as f:
        for line in lines:
            f.write(line)

def normalize_column_name(colname):
    xform_map = {
        'precinct': ['precinct_number'],
        'votes': ['total', 'total votes'],
        'election_day': ['election', 'election day'],
        'election_day_machine': ['ed ivo', 'election_day_ivo'],
        'election_day_paper': ['ed m-100'],
        'early_voting': ['early', 'early_votes', 'early voting', 'early_ voting'],
        'early_voting_machine': ['ev ivo'],
        'early_voting_paper': ['early_votes_paper', 'paper_ev', 'ev m-100'],
        'early/absentee': ['early/absente'],
        'mail': ['paper_mail'],
    }
    
    colname = colname.strip().lower()
    if colname in colorder:
        return colname
    
    for (canonical, deviant_list) in xform_map.items():
        if colname in deviant_list:
            return canonical
    else:
        return colname

def column_names(path, show_unmapped=False):
    with open(path, 'r') as f:
        try:
            headers = next(csv.reader(f))
            f.seek(0)
            f.readline()
            row_data = f.read()
        except:
            print(path)
            raise
        
        norm_headers = []
        unknown_columns = []
        for colname in headers:
            colname = normalize_column_name(colname)
            norm_headers.append(colname)
            if colname and colname not in colorder:
                unknown_columns.append(colname)
        
        if unknown_columns and show_unmapped:
            for colname in unknown_columns:
                print("{!r}".format(colname))
        
        if norm_headers == headers:
            return
        
        with open(path, 'w') as wf:
            sio = io.StringIO()
            writer = csv.DictWriter(wf, fieldnames=norm_headers, dialect='excel-unix')
            writer.writeheader()
            wf.write(row_data)

def line_endings(path):
    with open(path, 'rb') as f:
        data = f.read()
        newdata, nrepl = re.subn(b'[\r\n]+', b'\n', data)
        assert newdata, nrepl
        if newdata != data:
            print(path)
            with open(path, 'wb') as f:
                f.write(newdata)

def to_utf8(path):
    with open(path, 'rb') as f:
        data = f.read()
        try:
            ddata = data.decode('utf8')
        except UnicodeDecodeError:
            # Not 7-bit ascii or utf8
            try:
                ddata = data.decode('latin')
                print("{}: latin -> utf8".format(path))
                with open(path, 'wb') as f:
                    f.write(ddata.encode('utf8'))
            except UnicodeDecodeError:
                # Not latin either, print offending file
                print("{}:Not encoded as ascii, latin, or utf8".format(path))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='subcommands',
        description='valid subcommands',dest='command',help='sub-command help')
    
    sparser = subparsers.add_parser('remove_unnamed_columns', help='remove unnamed columns',
        description="Remove unnamed columns in passed csv files.")
    sparser.add_argument('paths', nargs='+', metavar='csvfile')
    
    sparser = subparsers.add_parser('column_names', help='normalize column names',
        description="Ensure column names in csv files passed are normalized.")
    sparser.add_argument('-u', '--show_unmapped', metavar='csvfile')
    sparser.add_argument('paths', nargs='+', metavar='csvfile')
    
    sparser = subparsers.add_parser('line_endings', help='normalize to unix line endings',
        description="Ensure all paths passed are normalized to unix-style line endings.")
    sparser.add_argument('paths', nargs='+', metavar='path')
    
    sparser = subparsers.add_parser('utf8', help='normalize to utf8',
        description="Ensure all paths passed are normalized to utf8.")
    sparser.add_argument('paths', nargs='+', metavar='path')
    
    args = parser.parse_args()
    
    params = vars(args).copy()
    del params['command']
    del params['paths']
    if 'paths' in args:
        for path in args.paths:
            globals()[args.command](path, **params)
    else:
        globals()[args.command](**params)

if __name__ == "__main__":
    exit(main())

