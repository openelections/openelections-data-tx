require 'remote_table'
require 'csv'

t = RemoteTable.new("/Users/derekwillis/code/openelections-sources-tx/2016/Irion\ County.csv")
rows = t.entries
results = []
offices = ['Straight Party', 'President and Vice President', 'United States Representative, District 11', 'Railroad Commissioner', 'State Senator, District 28', 'State Representative, District 72']
headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'early_votes', 'election_day']

rows.each do |row|
  # still need to add Over and Under Votes
  if row['Contest_title'] ==  'Straight Party' and row['candidate_name'] == 'Republican Party'
    results << ['Irion', row['Precinct_name'], 'Registered Voters', nil, nil, nil, row['Reg_voters'], nil, nil]
    results << ['Irion', row['Precinct_name'], 'Ballots Cast', nil, nil, nil, row['total_ballots'], row['early_ballots'], row['election_ballots']]
  end
  results << ['Irion', row['Precinct_name'], row['Contest_title'], nil, row['Party_Code'], row['candidate_name'], row['total_votes'], row['early_votes'], row['election_ballots']]
end

CSV.open("20161108__tx__general__irion__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
