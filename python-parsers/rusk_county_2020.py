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
    #the following is a list of the headings for the columns.  The order of the headings is also how they appear in the final output.  To change the output order change it here.
    # Note A): that Summary Results Report is taken from the actual pdf, and is therefore never actually set.
    #Note B): the order here, is also referenced in lines 50-71.  Any changes to the order, will also need to be adjusted there as well.
    column_headings = ['precinct','office','Summary Results Report','total','mail','early_voting','election_day']
    result = []
    page = 1
    office_index = [0]
    office = ''
    data = tabula.read_pdf(file,guess=False,multiple_tables=True,pages=('all'))
    for x in data:
        print(page)
        index = 0
        df = x
        pct = df.iloc[2,0]
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
        #change column titles to comply with openelections criteria
        if len(df.columns)== 5:

            df = df.rename(columns={
                'Unnamed: 1':column_headings[4],
                'Unnamed: 0':column_headings[3],
                'Unnamed: 2':column_headings[5],
                'Unnamed: 3':column_headings[6]
            })
        if len(df.columns) >= 6:
            df = df.rename(columns={
                'Unnamed: 0':column_headings[3],       
                'Unnamed: 2':column_headings[4],
                'Unnamed: 3':column_headings[5],
                'Unnamed: 4':column_headings[6]
            })
            
        if len(df.columns) == 7:
            df = df.rename(columns={
                'Unnamed: 0':column_headings[3],       
                'Unnamed: 2':column_headings[4],
                'Unnamed: 3':column_headings[5],
                'Unnamed: 4':column_headings[6],
                'Unnamed: 5':column_headings[6]
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
        df.dropna(how='all', inplace=True)
        df.dropna(axis='columns',how='all', inplace=True)
        df.reset_index(drop=True, inplace=True)

        #add in the last column which is the race for each result
        for x in df.index:
            df.loc[x,column_headings[1]]=''
            df.loc[x,column_headings[0]] = pct
            if 'DEM' in str(df.iloc[x,0]):
                office_index.append(x)
                office = df.iloc[x,0]
            df.loc[x,'office'] = office
            if 'REP' in str(df.iloc[x,0]):
                office_index.append(x)
                office = df.iloc[x,0]
            df.loc[x,'office'] = office
        #next two lines remove tbe heading row for each race.  To show the race above the results comment out the following block
        df.drop(office_index,inplace=True)
        df.reset_index(drop=True, inplace=True)
        #the following line re-orders the column.  
        df = df[column_headings]

        office=''
        office_index=[]
        result.append(df)
        page +=1

    pd.concat(result).to_csv(title)

try:
    arguments, values = getopt.getopt(argument_list, short_options, long_options)
except getopt.error as err:
    # Output error, and return with an error code
    print (str(err))
    sys.exit(2)

for current_argument, current_value in arguments:
    if current_argument in ("-d", "--dem"):
        csv_title = '20200303__tx__primary__rusk__precinct_d.csv'
        pdf_file = current_value
        scrapper(pdf_file,csv_title)
    elif current_argument in ("-r", "--rep"):
        csv_title = '20200303__tx__primary__rusk__precinct_r.csv'
        pdf_file = current_value
        scrapper(pdf_file,csv_title)