require 'remote_table'
require 'roo-xls'
require 'csv'

offices = { 'President and Vice President' => 'President', 'Straight Party' => 'Straight Party', 'United States Representative' => 'U.S. House', 'Railroad Commissioner' => 'Railroad Commissioner', 'State Senator' => 'State Senate', 'State Representative' => 'State Representative'}

results = []

t = RemoteTable.new("/Users/DW-admin/code/openelections-sources-tx/2016/Harris\ County\ TX\ 2016\ general\ Total\ Landscape.xlsx")
rows = t.entries
rows.each do |row|
  row.keys[11..-1].each do |result|
    if result == 'Straight Party Republican Party'
      results << ['Harris', row['PCT'], 'Registered Voters', nil, nil, row['Total Registered Voters']]
      results << ['Harris', row['PCT'], 'Ballots Cast', nil, nil, row['Total Ballots Cast']]
    end
    office = offices[offices.keys.detect{|o| result.include?(o) == true}]
    if office
      if result.include?('District')
        m = /\d+/.match(result)
        district = m[0]
        candidate = result.split(district).last.strip
      else
        district = nil
        candidate = result.split(office).last.strip
      end
      results << ['Harris', row['PCT'], office, district, candidate, row[result]]
    end
  end
end

CSV.open("harris_total.csv", "w") do |csv|
  csv << ['county', 'precinct', 'office', 'district', 'candidate', 'absentee']
  results.map{|r| csv << r}
end
