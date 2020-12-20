import xlrd
import unicodecsv

OFFICES = ['REGISTERED VOTERS', 'STRAIGHT PARTY', 'PRESIDENT', 'U.S. REPRESENTATIVE', 'RAILROAD COMMISSIONER', 'State Senate', 'STATE REPRESENTATIVE']


wb=xlrd.open_workbook()
toc = wb.sheets()[0]

contents = []
for row in range(4,toc.nrows):
        for col in range(toc.ncols):
            if toc.cell(row,col).value != '':
                contents.append(toc.cell(row,col).value)

sheets_to_load = []
