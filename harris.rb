require 'remote_table'
require 'roo-xls'
require 'csv'

t = RemoteTable.new "/Users/derekwillis/code/openelections-sources-tx/2020/primary/Harris TX REP TOTAL Landscape_2020.xlsx", skip: 2, headers: false
rows = t.entries

offices = [
  { 'start_col' => 2, 'name' => 'Registered Voters', 'length' => 1},
  { 'start_col' => 3, 'name' => 'Ballots Cast', 'length' => 1},
  { 'start_col' => 5, 'name' => 'President', 'length' => 10},
  { 'start_col' => 15, 'name' => 'U.S. Senate', 'length' => 7},
  { 'start_col' => 22, 'name' => 'U.S. House', 'district' => 2, 'length' => 3},
  { 'start_col' => 25, 'name' => 'U.S. House', 'district' => 7, 'length' => 8},
  { 'start_col' => 33, 'name' => 'U.S. House', 'district' => 8, 'length' => 5},
  { 'start_col' => 38, 'name' => 'U.S. House', 'district' => 9, 'length' => 5},
  { 'start_col' => 43, 'name' => 'U.S. House', 'district' => 10, 'length' => 3},
  { 'start_col' => 46, 'name' => 'U.S. House', 'district' => 18, 'length' => 8},
  { 'start_col' => 54, 'name' => 'U.S. House', 'district' => 22, 'length' => 17},
  { 'start_col' => 71, 'name' => 'U.S. House', 'district' => 29, 'length' => 4},
  { 'start_col' => 75, 'name' => 'U.S. House', 'district' => 36, 'length' => 4},
  { 'start_col' => 79, 'name' => 'Railroad Commissioner', 'length' => 4},
  { 'start_col' => 111, 'name' => 'State Senate', 'district' => 4, 'length' => 3},
  { 'start_col' => 114, 'name' => 'State Senate', 'district' => 11, 'length' => 3},
  { 'start_col' => 117, 'name' => 'State Senate', 'district' => 13, 'length' => 4},
