require 'remote_table'
require 'roo-xls'
require 'csv'

county = 'Jim Hogg'
t = RemoteTable.new("/Users/dwillis/code/openelections-sources-tx/2020/primary/JIM_HOGG_COUNTY-2020_MARCH_3RD_DEMOCRATIC_PRIMARY_332020-detailvotetotal 3-3-2020.xlsx")
rows = t.entries
results = []
headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'early_votes', 'election_day', 'absentee']

rows.each do |row|
  if row['Contest_title'].include?(", District")
    office, district = row['Contest_title'].split(", District ")
  else
    office = row['Contest_title']
    district = nil
  end
  if row['Contest_title'] == 'President' and row['candidate_id'] == '1'
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes'], row['absentee_over_votes']]
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes'], row['absentee_under_votes']]
    results << [county, row['Precinct_name'], 'Registered Voters', nil, row['Party_Code'], nil, row['Reg_voters'], nil, nil]
    results << [county, row['Precinct_name'], 'Ballots Cast', nil, row['Party_Code'], nil, row['total_ballots'], row['early_ballots'], row['election_ballots'], row['absentee_ballots']]
  end
  results << [county, row['Precinct_name'], office, district, row['Party_Code'], row['candidate_name'], row['total_votes'], row['early_votes'], row['election_votes'], row['']]
  if row['candidate_id'] == "1" and row['Contest_title'] != 'President'
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes']]
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes']]
  end
end

CSV.open("20200303__tx__primary__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
