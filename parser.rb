require 'remote_table'
require 'roo-xls'
require 'csv'

county = 'Karnes'
t = RemoteTable.new("/Users/dwillis/code/openelections-sources-tx/2014/KARNES_COUNTY-2014_Republican_Party_Primary_Election_342014-DetailVoteTotals03-14-14_Republican.xlsx")
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
  if row['Contest_title'].upcase == 'UNITED STATES SENATOR' and row['candidate_id'].to_i == 1
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes']]
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes']]
    results << [county, row['Precinct_name'], 'Registered Voters', nil, row['Party_Code'], nil, row['Reg_voters'], nil, nil]
    results << [county, row['Precinct_name'], 'Ballots Cast', nil, row['Party_Code'], nil, row['total_ballots'], row['early_ballots'], row['election_votes']]
  end
  results << [county, row['Precinct_name'], office, district, row['Party_Code'], row['candidate_name'], row['total_votes'], row['early_votes'], row['election_votes']]
  if row['candidate_id'] == "1"
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes']]
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes']]
  end
end

CSV.open("20140304__tx__primary__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
