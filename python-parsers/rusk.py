import sys
import getopt
import tabula
import pandas as pd
import numpy as np
import math

short_options = "d:r:"
long_options = ["dem","rep"]

full_cmd_arguments = sys.argv
argument_list = full_cmd_arguments[1:]

def scrapper(file,title):
    headers = ['county','precinct','district','party','candidate','votes']
    voting_style = ['early_voting','election_day','provisional','mail']
    result = []
    page = 1
    data = tabula.read_pdf(file,guess=False,multiple_tables=True,pages=('all'))
    for x in data:
        print(page)
        index = 0
        df = x
        df = df.drop(df.index[[0,1,2]])
        df = df[:-2]
        df = df.drop(columns = ['OFFICIAL RESULTS'])

        #check to see if the data frame is the start of a new precinct.  If so, then remove the overall statistic data from it.
        if 'STATISTICS' in str(df.iloc[:,0][3]):
            df = df.drop(df.index[0:5])
            for index_value in df.index:
                if type(df.loc[index_value]['Unnamed: 1']) == str:
                    if len(df.loc[index_value]['Unnamed: 1']) < 4:
                        if len(df.loc[index_value]['Unnamed: 1']) == 3:
                            df.loc[index_value,'Unnamed: 0'] =str(df.loc[index_value]['Unnamed: 1']).split()[0]
                            df.loc[index_value,'Unnamed: 1'] =str(df.loc[index_value]['Unnamed: 1']).split()[1]


            df = df.dropna(subset=['Summary Results Report'])

            df = df[~df['Summary Results Report'].str.contains('Ballots')]
        df = df.reset_index(drop=True)
        if len(df.columns)== 5:
            df = df.rename(columns={
                'Unnamed: 1':'mail',
                'Unnamed: 0':'total',
                'Unnamed: 2':'early_voting',
                'Unnamed: 3':'election_day'
            })
        if len(df.columns) >= 6:
            df = df.rename(columns={
                'Unnamed: 0':'total',
                'Unnamed: 2':'mail',
                'Unnamed: 3':'early_voting',
                'Unnamed: 4':'election_day'
            })

        if len(df.columns) == 7:
            df = df.rename(columns={
                'Unnamed: 0':'total',
                'Unnamed: 2':'mail',
                'Unnamed: 3':'early_voting',
                'Unnamed: 4':'election_day',
                'Unnamed: 5':'election_day'
            })
        #clean up the first column, remove unneeded rows, and also any rows that have no values in it
        remove_strings=['Vote For 1','TOTAL']
        remove_strings_list = df.index[df['Summary Results Report'].isin(remove_strings)].tolist()
        df.drop(df.index[remove_strings_list], inplace=True)
        df.dropna(subset=['Summary Results Report'], inplace=True)

        if 'Unnamed: 1' in df.columns:
            for index in df[df['Unnamed: 1'].notna()].index.tolist():
                df.loc[index,'total'] = df.loc[index,'Unnamed: 1']
            df.drop(columns=['Unnamed: 1'],inplace=True)

        col_list = ['total','mail','early voting','election day']
        totals_index_list = df.index[df['total'].isna()].tolist()
        count_lst = df.loc[totals_index_list].isnull().sum(axis=1)
        for index, value in count_lst.items():
            if value <= 3:

                row = df.loc[[index]]
                try:
                    count = float(df.loc[index]['Summary Results Report'].rsplit(' ',1)[1])
                    name = df.loc[index]['Summary Results Report'].rsplit(' ',1)[0]
                    df.loc[index,'total'] = count
                    df.loc[index,'Summary Results Report'] = name
                except:
                    break


        df.dropna(axis='columns',how='all', inplace=True)

        df.reset_index(drop=True, inplace=True)
        df.dropna(how='all', inplace=True)
        result.append(df)
        page = page+1

    pd.concat(result).to_csv(title)

try:
    arguments, values = getopt.getopt(argument_list, short_options, long_options)
except getopt.error as err:
    # Output error, and return with an error code
    print (str(err))
    sys.exit(2)

for current_argument, current_value in arguments:
    if current_argument in ("-d", "--dem"):
        csv_title = 'dem.csv'
        pdf_file = current_value
        scrapper(pdf_file,csv_title)
    elif current_argument in ("-r", "--rep"):
        csv_title = 'rep.csv'
        pdf_file = current_value
        scrapper(pdf_file,csv_title)
