require 'remote_table'
require 'roo-xls'
require 'csv'

county = 'Floyd'
t = RemoteTable.new("/Users/derekwillis/code/openelections-sources-tx/2020/primary/Floyd TX Detailed vote totals-3-30-2020 11-13-00 AM.CSV")
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
  if row['Contest_title'].upcase == 'President' and row['candidate_name'] == 'Elizabeth Warren'
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes'], row['absentee_over_votes']]
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes'], row['absentee_under_votes']]
#    results << [county, row['Precinct_name'], 'Registered Voters', nil, row['Party_Code'], nil, row['total_ballots'], nil, nil]
#    results << [county, row['Precinct_name'], 'Ballots Cast', nil, row['Party_Code'], nil, row['total_ballots'], row['early_ballots'], row['election_ballots'], row['absentee_ballots']]
  end
  results << [county, row['Precinct_name'], office, district, row['Party_Code'], row['candidate_name'], row['total_votes'], row['early_votes'], row['election_votes'], row['absentee_votes']]
  if row['candidate_id'] == "1"
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes'], row['absentee_over_votes']]
    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes'], row['absentee_under_votes']]
  end
end

CSV.open("20200303__tx__primary__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
