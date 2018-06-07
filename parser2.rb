require 'remote_table'
require 'roo-xls'
require 'csv'

county = 'Wilbarger'
t = RemoteTable.new("/Users/dwillis/code/openelections-sources-tx/2014/WILBARGER_COUNTY-2014_General_Election_1142014-votes 11-4-2014 final.csv")
rows = t.entries
results = []
headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'early_votes', 'election_day']

rows.each do |row|
  if row['race_name'].include?(", District")
    office, district = row['race_name'].split(", District ")
  else
    office = row['race_name']
    district = nil
  end
  if row['race_name'] == 'Straight Party' and row['candidate_name'].upcase == 'REPUBLICAN PARTY'
    results << [county, row['Precinct_name'], 'Registered Voters', nil, nil, nil, row['Reg_voters'], nil, nil]
  end
  total_votes = row['early_votes'].to_i + row['election_votes'].to_i
  results << [county, row['Precinct_name'], office, district, row['Party_Code'], row['candidate_name'], total_votes, row['early_votes'], row['election_votes']]
end

CSV.open("20141104__tx__general__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
