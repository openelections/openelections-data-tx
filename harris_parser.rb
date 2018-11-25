require 'remote_table'
require 'roo-xls'
require 'csv'

offices = { 'President and Vice President' => 'President', 'United States Senator' => 'United States Senator',
            'Lieutenant Governor' => 'Lieutenant Governor', 'Attorney General' => 'Attorney General',
            'Governor' => 'Governor',
            'Straight Party' => 'Straight Party',
            'United States Representative' => 'U.S. House', 'Railroad Commissioner' => 'Railroad Commissioner', 'State Senator' => 'State Senate', 'State Representative' => 'State Representative'}

results = []
file = ARGV[0]
year = ARGV[1]
eday = ARGV[2]

puts 'running harris parser with file: %s for year: %s' % [file, year]
t = RemoteTable.new(file)
puts 'opened file'
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
      if row[result] != ''
        results << ['Harris', row['PCT'], office, district, candidate, row[result], '']
      end
    end
  end
end

filename = "%s/%s__tx__general__harris__precinct.csv" % [year, eday]
CSV.open(filename, "w") do |csv|
  csv << ['county', 'precinct', 'office', 'district', 'candidate', 'votes', 'party']
  results.map{|r| csv << r}
end

puts 'done parsing'
