require 'remote_table'
require 'roo-xls'
require 'csv'

county = 'Red River'
t = RemoteTable.new("/Users/dwillis/code/openelections-sources-tx/2016/RedRiverCounty_DetailVoteTotals11082016.xlsx")
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
    results << [county, row['Precinct_name'], office, district, nil, 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes']]
    results << [county, row['Precinct_name'], office, district, nil, 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes']]
    results << [county, row['Precinct_name'], 'Registered Voters', nil, nil, nil, row['Reg_voters'], nil, nil]
    results << [county, row['Precinct_name'], 'Ballots Cast', nil, nil, nil, row['total_ballots'], row['early_ballots'], row['election_ballots']]
  end
  results << [county, row['Precinct_name'], office, district, row['Party_Code'], row['candidate_name'], row['total_votes'], row['early_votes'], row['election_ballots']]
  if row['candidate_id'] == "1"
    results << [county, row['Precinct_name'], office, district, nil, 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes']]
    results << [county, row['Precinct_name'], office, district, nil, 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes']]
  end
end

CSV.open("20161108__tx__general__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
