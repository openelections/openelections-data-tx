require 'remote_table'
require 'roo-xls'
require 'csv'

county = 'Denton'
t = RemoteTable.new("/Users/dwillis/code/openelections-sources-tx/2020/general/DENTON_COUNTY-2020_NOVEMBER_3RD_GENERAL_ELECTION_1132020-1120_Denton_Pct.xlsx")
rows = t.entries
results = []
headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'early_votes', 'election_day']

offices = {
  'PRESIDENT/VICE PRESIDENT' => ['President', nil],
  'PRESIDENT/VICE-PRESIDENT' => ['President', nil],
  'President/Vice President' => ['President', nil],
  'President / Vice-President' => ['President', nil],
  'President and Vice President' => ['President', nil],
  'United States Senator' => ['U.S. Senate', nil],
  'U.S. SENATOR' => ['U.S. Senate', nil],
  'U.S. Senator' => ['U.S. Senate', nil],
  'UNITED STATES SENATOR' => ['U.S. Senate', nil],
  'United States Representative, District No. 11' => ['U.S. House', 11],
  'UNITED STATES REPRESENTATIVE, DISTRICT 11' => ['U.S. House', 11],
  'UNITED STATES REPRESENTATIVE DISTRICT 11' => ['U.S. House', 11],
  'U.S. REPRESENTATIVE, DISTRICT 13' => ['U.S. House', 13],
  'United States Representative, District 13' => ['U.S. House', 13],
  'United States Representative, District No. 13' => ['U.S. House', 13],
  'United States Representative, District No. 10' => ['U.S. House', 10],
  'United States Representative, District No. 17' => ['U.S. House', 17],
  'U.S. Representative District 17' => ['U.S. House', 17],
  'United States Representative, District No. 21' => ['U.S. House', 21],
  'United States Representative, District 24' => ['U.S. House', 24],
  'United States Representative, District 26' => ['U.S. House', 26],
  'United States Representative, District No. 27' => ['U.S. House', 27],
  'United States Representative, District No. 28' => ['U.S. House', 28],
  'United States Representative, District No. 34' => ['U.S. House', 34],
  'RAILROAD COMMISSIONER' => ['Railroad Commissioner', nil],
  'State Senator, District 12' => ['State Senate', 12],
  'State Senator, District 18' => ['State Senate', 18],
  'State Senator, District No. 18' => ['State Senate', 18],
  'State Senator, District 21' => ['State Senate', 21],
  'State Senator, District No. 21' => ['State Senate', 21],
  'State Senator, District No. 24' => ['State Senate', 24],
  'STATE SENATOR, DISTRICT 28' => ['State Senate', 28],
  'State Representative, District No. 3' => ['State Representative', 3],
  'State Representative District 12' => ['State Representative', 12],
  'State Representative, District No. 13' => ['State Representative', 13],
  'State Representative, District No. 30' => ['State Representative', 30],
  'State Representative, District No. 43' => ['State Representative', 43],
  'State Representative, District No. 53' => ['State Representative', 53],
  'State Representative, District No. 60' => ['State Representative', 60],
  'STATE REPRESENTATIVE DISTRICT 60' => ['State Representative', 60],
  'STATE REPRESENTATIVE, DISTRICT 61' => ['State Representative', 61],
  'State Representative, District 63' => ['State Representative', 63],
  'State Representative, District 64' => ['State Representative', 64],
  'State Representative, District 65' => ['State Representative', 65],
  'State Representative, District No. 68' => ['State Representative', 68],
  'State Representative, District No. 69' => ['State Representative', 69],
  'STATE REPRESENTATIVE, DISTRICT 72' => ['State Representative', 72],
  'State Representative, District No. 80' => ['State Representative', 80],
  'State Representative, District 86' => ['State Representative', 86],
  'State Representative, District No. 88' => ['State Representative', 88],
  'State Representative, District 106' => ['State Representative', 106],
}

rows.each do |row|
  if offices.key?(row['Contest_title'])
    office, district = offices[row['Contest_title']]
  else
    office = row['Contest_title']
    district = nil
  end
  if row['race_name'] == 'President/Vice President' and row['candidate_name'] == 'Donald J. Trump/ Michael R. Pence'
    results << [county, row['Precinct_name'], 'Registered Voters', nil, nil, nil, row['Reg_voters'], nil, nil]
#    results << [county, row['precinct_number'], 'Ballots Cast', nil, nil, nil, row['Ballots Cast'], nil, nil, nil]
  end
  total_votes = row['early_votes'].to_i + row['election_votes'].to_i
  results << [county, row['Precinct_name'], office, district, row['party-code'], row['candidate_name'], total_votes, row['early_votes'], row['election_votes']]
end

CSV.open("20201103__tx__general__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
