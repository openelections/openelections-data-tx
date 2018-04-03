## Guidelines for contributing data
- The basic format for a generated filename is as follows:
`date__state__{party}__{special}__election_type__{jurisdiction}{office}__{office_district}__{reporting_level}.format`.
- For example, the file containing precinct-level data for the March 6, 2018 primary election in Dallas County would be named `20180306__tx__primary__dallas__precinct.csv`
- Standard common office titles are: President, U.S. Senate, U.S. House, Governor (and other statewide officers), State Senate and State House.
**NB: Is it "State Senate" and "State House" or "State Senator" and "State Representative"?**
- Data files should have Unix-style line endings (\n), not DOS-style line endings (\r\n).
- Data files should have a newline after the last line.
- Don’t include "County" in the county name.
- Don’t include "Precinct" in the name of the precinct.
- For precincts with numbers in the name, remove any leading zeros (005 becomes 5).
- There is no set order for candidates/races: even within the same election, the order of candidates can differ between counties.
- Use the following row headers: `county`, `precinct`, `office`, `district`, `party`, `candidate`, `votes`. You may include row headers for `early_voting`, `election_day`, and `provisional` if the source file contains that data. Only include a column for `winner` if the winner is clearly indicated in the original data.
