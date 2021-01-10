require 'remote_table'
require 'roo-xls'
require 'csv'

county = 'Bandera'
t = RemoteTable.new("/Users/dwillis/code/openelections-sources-tx/2020/general/BANDERA_COUNTY-2020_NOVEMBER_3RD_GENERAL_ELECTION_1132020-prctXPrct 2020.CSV")
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
  if row['race_name'].upcase == 'President' and row['candidate_name'] == 'Elizabeth Warren'
    results << [county, row['precinct_number'], office, district, row['party code'], 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes'], row['absentee_over_votes']]
    results << [county, row['precinct_number'], office, district, row['party code'], 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes'], row['absentee_under_votes']]
#    results << [county, row['Precinct_name'], 'Registered Voters', nil, row['Party_Code'], nil, row['total_ballots'], nil, nil]
#    results << [county, row['Precinct_name'], 'Ballots Cast', nil, row['Party_Code'], nil, row['total_ballots'], row['early_ballots'], row['election_ballots'], row['absentee_ballots']]
  end
  results << [county, row['precinct_number'], office, district, row['party code'], row['candidate_name'], row['total_votes'], row['early_votes'], row['election_votes'], row['absentee_votes']]
#  if row['candidate_id'] == "1"
#    results << [county, row['precinct_number'], office, district, row['party code'], 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes'], row['absentee_over_votes']]
#    results << [county, row['precinct_number'], office, district, row['party code'], 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes'], row['absentee_under_votes']]
#  end
end

CSV.open("20200303__tx__primary__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
