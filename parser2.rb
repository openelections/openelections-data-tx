require 'remote_table'
require 'roo-xls'
require 'csv'

county = 'Tarrant'
t = RemoteTable.new("/Users/derekwillis/code/openelections-sources-tx/2014/TARRANT_COUNTY-2014_General_Election_1142014-1114_01-Tarrant.xlsx")
rows = t.entries
results = []
headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'early_votes', 'election_day']

rows.each do |row|
  if row['Contest_title'].include?(", District")
    office, district = row['Contest_title'].split(", District ")
  else
    office = row['Contest_title']
    district = nil
  end
  if row['Contest_title'] == 'Straight Party' and row['candidate_name'].upcase == 'REPUBLICAN PARTY'
    results << [county, row['Precinct_name'], 'Registered Voters', nil, nil, nil, row['Reg_voters'], nil, nil]
  end
  total_votes = row['Early_votes'].to_i + row['election_votes'].to_i
  results << [county, row['Precinct_name'], office, district, row['Party_Code'], row['candidate_name'], total_votes, row['Early_votes'], row['election_votes']]
end

CSV.open("20141104__tx__general__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
