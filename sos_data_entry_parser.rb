require 'remote_table'
require 'roo-xls'
require 'csv'

t = RemoteTable.new "/Users/dwillis/code/openelections-sources-tx/2020/general/pctcpct_dataentry_20201130.xlsx"
rows = t.entries

headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'early_voting', 'election_day', 'votes']

county =  "Val Verde"

county_rows = rows.select{|r| r['PS_NAME'] == "#{county.upcase} COUNTY"}

results = []

county_rows.each do |cr|
  result = results.detect{|r| r[:office] == cr['RACE_NAME'] and r[:candidate] == cr['CANDIDATE_NAME'] and r[:precinct] == cr['PRECINCT_NUMBER']}
  if not result
    new_record = true
    result = {'office': cr['RACE_NAME'], 'candidate': cr['CANDIDATE_NAME'], 'precinct': cr['PRECINCT_NUMBER']}
  end
  if cr['XTYPE'] == 'ElecDay'
    result['election_day'] = cr['XCOUNT']
  else
    result['early_voting'] = cr['XCOUNT']
  end
  results << result if new_record
  new_record = false
end


CSV.open("20201103__tx__general__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.each do |result|
    csv << [county, result[:precinct], result[:office].titleize, nil, nil, result[:candidate].titleize, result['early_voting'], result['election_day'], nil]
  end
end
