require 'remote_table'
require 'roo-xls'
require 'csv'

county = 'Galveston'
t = RemoteTable.new("/Users/dwillis/code/openelections-sources-tx/2020/general/GALVESTON_COUNTY-2020_NOVEMBER_3RD_GENERAL_ELECTION_1132020-Detailed vote totals-11-30-2020 10-27-32 AM.CSV")
rows = t.entries
results = []
headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'absentee', 'early_voting', 'election_day']

offices = {
  'PRESIDENTIAL ELECTORS (Vote for candidates of one party for President and Vice President)' => ['President', nil],
  'PRESIDENT / VICE-PRESIDENT' => ['President', nil],
  'President and Vice President' => ['President', nil],
  'President/Vice President' => ['President', nil],
  'United States Senator' => ['U.S. Senate', nil],
  'UNITED STATES SENATOR' => ['U.S. Senate', nil],
  'United States Representative, District 4' => ['U.S. House', 4],
  'United States Representative, District No. 13' => ['U.S. House', 13],
  'United States Representative, District 14' => ['U.S. House', 14],
  'United States Representative, District No. 19' => ['U.S. House', 19],
  'UNITED STATES REPRESENTATIVE DISTRICT 25' => ['U.S. House', 25],
  'RAILROAD COMMISSIONER' => ['Railroad Commissioner', nil],
  'State Senator, District 1' => ['State Senate', 1],
  'State Senator, District 4' => ['State Senate', 4],
  'State Senator, District 11' => ['State Senate', 11],
  'STATE SENATOR, DISTRICT 24' => ['State Senate', 24],
  'State Senator, District No. 28' => ['State Senate', 28],
  'State Representative, District 7' => ['State Representative', 7],
  'STATE REPRESENTATIVE, DISTRICT 20' => ['State Representative', 20],
  'State Representative, District 23' => ['State Representative', 23],
  'State Representative, District 24' => ['State Representative', 24],
  'State Representative, District No. 60' => ['State Representative', 60],
  'State Representative, District No. 69' => ['State Representative', 69]
}

rows.each do |row|
  if offices.key?(row['Contest_title'])
    office, district = offices[row['Contest_title']]
  else
    office = row['Contest_title']
    district = nil
  end
  if row['Contest_Id'].to_i == 85 && row['candidate_id'].to_i == 1
#    results << [county, row['Precinct_name'], 'Registered Voters', nil, nil, nil, row['Reg_voters'], nil, nil, nil]
    results << [county, row['Precinct_name'], 'Ballots Cast', nil, nil, nil, row['total_ballots'], nil,nil,nil]
  end
  if row['candidate_id'].to_i == 1
    results << [county, row['Precinct_name'], office, district, nil, 'Over Votes', row['total_over_votes'], row['absentee_over_votes'], row['early_over_votes'], row['election_over_votes']]
    results << [county, row['Precinct_name'], office, district, nil, 'Under Votes', row['total_under_votes'], row['absentee_under_votes'], row['early_under_votes'], row['election_under_votes']]
  end
  results << [county, row['Precinct_name'], office, district, row['Party_Code'], row['candidate_name'], row['total_votes'], row['absentee_votes'], row['early_votes'], row['election_votes']]
end

CSV.open("20201103__tx__general__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
