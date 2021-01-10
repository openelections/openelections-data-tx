'''This python script is to extract each sheet in an Excel workbook as a new csv file'''

import csv
import xlrd
import sys

def ExceltoCSV(excel_file, csv_file_base_path):
    workbook = xlrd.open_workbook(excel_file)
    for sheet_name in workbook.sheet_names():
        print('processing - ' + sheet_name)
        worksheet = workbook.sheet_by_name(sheet_name)
        csv_file_full_path = csv_file_base_path + sheet_name.lower().replace(" - ", "_").replace(" ","_") + '.csv'
        csvfile = open(csv_file_full_path, 'wt')
        writetocsv = csv.writer(csvfile, delimiter='\t')
        for rownum in range(worksheet.nrows):
            writetocsv.writerow(
                list(x if type(x) == type(u'') else x for x in worksheet.row_values(rownum)
                )
            )
        csvfile.close()
        print(sheet_name + ' has been saved at - ' + csv_file_full_path)
if __name__ == '__main__':
    ExceltoCSV(excel_file = sys.argv[1], csv_file_base_path = sys.argv[2])
