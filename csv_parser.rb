require 'remote_table'
require 'csv'

county = 'Lampasas'
county_abbrev = 'LAMPA'
t = RemoteTable.new("/Users/dwillis/code/openelections-sources-tx/2020/general/LAMPASAS_COUNTY-2020_NOVEMBER_3RD_GENERAL_ELECTION_1132020-Official 20201103 General_EXPORT.CSV", headers: false)
rows = t.entries

results = []
headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'absentee', 'early_voting', 'election_day']
vote_methods = ['absentee', 'early_voting', 'election_day']
raw_offices = rows.first[4..-1]
raw_candidates = rows[2][4..-1]
combo = raw_offices.zip(raw_candidates)
raw_results = rows.select{|r| r[0] == county_abbrev}
raw_results = raw_results - [raw_results.last]
precincts = raw_results.collect{|r| r[2]}.uniq - ['COUNTY TOTALS']

office_lookup = {
  'REGISTERED VOTERS TOTAL' => ['Registered Voters', nil],
  'PRESIDENT/VICE PRESIDENT' => ['President', nil],
  'PRESIDENT/VICE-PRESIDENT' => ['President', nil],
  'President/Vice President' => ['President', nil],
  'President / Vice-President' => ['President', nil],
  'President and Vice President' => ['President', nil],
  'United States Senator' => ['U.S. Senate', nil],
  'U.S. SENATOR' => ['U.S. Senate', nil],
  'U.S. Senator' => ['U.S. Senate', nil],
  'U. S. Senator' => ['U.S. Senate', nil],
  'US Senator' => ['U.S. Senate', nil],
  'UNITED STATES SENATOR' => ['U.S. Senate', nil],
  'U. S. Congressional Dist 5' => ['U.S. House', 5],
  'United States Representative, District No. 11' => ['U.S. House', 11],
  'UNITED STATES REPRESENTATIVE, DISTRICT 11' => ['U.S. House', 11],
  'UNITED STATES REPRESENTATIVE DISTRICT 11' => ['U.S. House', 11],
  'US Representative, Dist 11' => ['U.S. House', 11],
  'U.S. REPRESENTATIVE, DISTRICT 13' => ['U.S. House', 13],
  'US Representative, Dist 13' => ['U.S. House', 13],
  'United States Representative, District 13' => ['U.S. House', 13],
  'United States Representative, District No. 13' => ['U.S. House', 13],
  'United States Representative, District No. 10' => ['U.S. House', 10],
  'United States Representative, District No. 17' => ['U.S. House', 17],
  'U.S. Representative District 17' => ['U.S. House', 17],
  'US Representative, Dist 19' => ['U.S. House', 19],
  'United States Representative, District No. 21' => ['U.S. House', 21],
  'United States Representative, District 24' => ['U.S. House', 24],
  'U. S. Congressional Dist 24' => ['U.S. House', 24],
  'US Representative, Dist 25' => ['U.S. House', 25],
  'United States Representative, District 26' => ['U.S. House', 26],
  'U. S. Congressional Dist 26' => ['U.S. House', 26],
  'United States Representative, District No. 27' => ['U.S. House', 27],
  'United States Representative, District No. 28' => ['U.S. House', 28],
  'U. S. Congressional Dist 30' => ['U.S. House', 30],
  'U. S. Congressional Dist 32' => ['U.S. House', 32],
  'U. S. Congressional Dist 33' => ['U.S. House', 33],
  'United States Representative, District No. 34' => ['U.S. House', 34],
  'Railroad Commissioner' => ['Railroad Commissioner', nil],
  'RAILROAD COMMISSIONER' => ['Railroad Commissioner', nil],
  'State Senator, District 12' => ['State Senate', 12],
  'State Senator, District 18' => ['State Senate', 18],
  'State Senator, District No. 18' => ['State Senate', 18],
  'State Senator, District 21' => ['State Senate', 21],
  'State Senator, District No. 21' => ['State Senate', 21],
  'State Senator, District No. 24' => ['State Senate', 24],
  'State Senator, Dist 24' => ['State Senate', 24],
  'STATE SENATOR, DISTRICT 28' => ['State Senate', 28],
  'State Senator, Dist 28' => ['State Senate', 28],
  'State Representative, District No. 3' => ['State Representative', 3],
  'State Representative District 12' => ['State Representative', 12],
  'State Representative, District No. 13' => ['State Representative', 13],
  'State Representative, District No. 30' => ['State Representative', 30],
  'State Representative, District No. 43' => ['State Representative', 43],
  'State Representative, District No. 53' => ['State Representative', 53],
  'State Representative, Dist 54' => ['State Representative', 54],
  'State Representative, District No. 60' => ['State Representative', 60],
  'STATE REPRESENTATIVE DISTRICT 60' => ['State Representative', 60],
  'STATE REPRESENTATIVE, DISTRICT 61' => ['State Representative', 61],
  'State Representative, District 63' => ['State Representative', 63],
  'State Representative, District 64' => ['State Representative', 64],
  'State Representative, District 65' => ['State Representative', 65],
  'State Representative, District No. 68' => ['State Representative', 68],
  'State Representative, Dist 68' => ['State Representative', 68],
  'State Representative, District No. 69' => ['State Representative', 69],
  'State Representative, Dist 69' => ['State Representative', 69],
  'STATE REPRESENTATIVE, DISTRICT 72' => ['State Representative', 72],
  'State Representative, District No. 80' => ['State Representative', 80],
  'State Representative, Dist 82' => ['State Representative', 82],
  'State Representative, District 86' => ['State Representative', 86],
  'State Representative, Dist 86' => ['State Representative', 86],
  'State Representative, District No. 88' => ['State Representative', 88],
  'State Rep, Dist 100' => ['State Representative', 100],
  'State Rep, Dist 102' => ['State Representative', 102],
  'State Rep, Dist 103' => ['State Representative', 103],
  'State Rep, Dist 104' => ['State Representative', 104],
  'State Rep, Dist 105' => ['State Representative', 105],
  'State Representative, District 106' => ['State Representative', 106],
  'State Rep, Dist 107' => ['State Representative', 107],
  'State Rep, Dist 108' => ['State Representative', 108],
  'State Rep, Dist 109' => ['State Representative', 109],
  'State Rep, Dist 110' => ['State Representative', 110],
  'State Rep, Dist 111' => ['State Representative', 111],
  'State Rep, Dist 112' => ['State Representative', 112],
  'State Rep, Dist 113' => ['State Representative', 113],
  'State Rep, Dist 114' => ['State Representative', 114],
  'State Rep, Dist 115' => ['State Representative', 115]

}

range = (0..raw_results.size-1)

raw_results.each_with_index do |raw_result, idx|
  votes = raw_result[4..83]
  registered_voters = raw_result[3]
  results << {'county': county, 'precinct': raw_result[2], 'office': 'Registered Voters', 'district': nil, 'party': nil, 'candidate': nil, 'absentee': nil, 'early_voting': nil, 'election_day': nil, 'votes': registered_voters}

  if range.step(3).to_a.include?(idx)
    vote_type = :absentee
  elsif range.step(3).to_a.map{|x| x+1}.include?(idx)
    vote_type = :early_voting
  elsif range.step(3).to_a.map{|x| x+2}.include?(idx)
    vote_type = :election_day
#  else
#    vote_type = :provisional
  end

  combo.zip(votes).each do |office_candidate, c_votes|
    raw_office, raw_candidate = office_candidate
    if office_lookup.key?(raw_office)
      office, district = office_lookup[raw_office]
    else
      office = raw_office
      district = nil
    end

    if raw_candidate == 'BALLOTS CAST'
      candidate = nil
      party = nil
    else
      candidate = raw_candidate.split(' (')[0]
      party = raw_candidate.split(' (')[1]
    end

    c = results.detect{|r| r[:candidate] == candidate && r[:precinct] == raw_result[2] && r[:office] == office}
    if c
      c[vote_type] = c_votes
    else
      c = {'county': county, 'precinct': raw_result[2], 'office': office, 'district': district, 'party': party, 'candidate': candidate}
      c[vote_type.to_sym] = c_votes
      results << c
    end
  end
end

CSV.open("20201103__tx__general__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.uniq.each do |result|
    if not result.has_key?(:votes)
      result[:votes] = result[:absentee].to_i + result[:early_voting].to_i + result[:election_day].to_i
    end
    csv << [result[:county], result[:precinct], result[:office], result[:district], result[:party], result[:candidate], result[:votes], result[:absentee], result[:early_voting], result[:election_day]]
  end
end
