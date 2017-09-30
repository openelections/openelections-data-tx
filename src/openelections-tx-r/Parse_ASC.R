library(tidyverse)

convert <- function(
  url,
  countyName,
  houseRegex = 'United States Representative, Dist (.+)',
  stateRepRegex = 'State Representative, District (.+)',
  stateSenateRegex = 'State Senator, District (.+)',
  precinctRegex = 'PRECINCT ([0-9]+)',
  longForm=FALSE
) {

  posBase <- 0
  if (longForm) {
    posBase <- 30
  }
  
  read_fwf(
  file=url,
  col_positions=fwf_positions(
    start=c(12,c(18,28,84,122)+posBase),
    end=c(17,c(20,83,121,176)+posBase),
    col_names=c('votes','party','office','candidate','precinct')
  )
) %>%
  mutate(vote=as.integer(vote),
         party=trimws(party),
         office=trimws(office),
         candidate=trimws(candidate),
         precinct=gsub(x=trimws(precinct), pattern=precinctRegex, replacement='\\1'),
         county=countyName,
         district=as.character(NA)
  ) %>%
  mutate(
    district=ifelse(grepl(x=office, pattern=houseRegex), gsub(x=office, pattern=houseRegex, replacement='\\1'), district),
    office=ifelse(grepl(x=office, pattern=houseRegex), 'U.S. House', office),
    district=ifelse(grepl(x=office, pattern=stateRepRegex), gsub(x=office, pattern=stateRepRegex, replacement='\\1'), district),
    office=ifelse(grepl(x=office, pattern=stateRepRegex), 'State Representative', office),
    district=ifelse(grepl(x=office, pattern=stateSenateRegex), gsub(x=office, pattern=stateSenateRegex, replacement='\\1'), district),
    office=ifelse(grepl(x=office, pattern=stateSenateRegex), 'State Senator', office)
  ) %>%
  select(county, precinct, office, district, party, candidate, vote)
  
}

briscoe <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/16GBRISC.ASC', 'Briscoe'
)
write_csv(briscoe, '../20161108__tx__general__briscoe__precinct.csv', na='')

colorado <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/COLORADO_COUNTY-2016_General_Election_1182016-16GCOLOR.ASC',
  'Colorado'
)
write_csv(colorado, '../20161108__tx__general__colorado__precinct.csv', na='')

goliad <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/16GGOLIAD.ASC',
  'Goliad',
  longForm=TRUE
)
write_csv(goliad, '../20161108__tx__general__goliad__precinct.csv', na='')

dallam <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/Dallam_Co_GEN_Elec_2016.ASC',
  'Dallam',
  houseRegex='United States Representative, District (.+)',
  precinctRegex='PRECINCTS ([0-9, ]+)'
)
write_csv(dallam, '../20161108__tx__general__dallam__precinct.csv', na='')

freestone <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/FREESTONE_COUNTY-2016_General_Election_1182016-16GFREES.ASC',
  'Freestone',
  houseRegex='United States Representative, District (.+)',
  precinctRegex='PRECINCT ([0-9]+)'
)
write_csv(freestone, '../20161108__tx__general__freestone__precinct.csv', na='')

moore <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/MOORE_COUNTY-2016_General_Election_1182016-16GMOORE.ASC',
  'Moore',
  houseRegex='United States Rep, District (.+)',
  precinctRegex='Precinct ([0-9]+)'
)
write_csv(moore, '../20161108__tx__general__moore__precinct.csv', na='')

morris <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/Morris%2016GMORRI.ASC',
  'Morris',
  houseRegex='United States Representative, District (.+)',
  precinctRegex='Precinct ([0-9]+)',
  longForm=TRUE
)
write_csv(morris, '../20161108__tx__general__morris__precinct.csv', na='')

orange <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/ORANGE_COUNTY-2016_General_Election_1182016-16GORANG.ASC',
  'Orange'
)
write_csv(orange, '../20161108__tx__general__orange__precinct.csv', na='')

robertson <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/ROBERTSON_COUNTY-2016_General_Election_1182016-16GROBER.ASC',
  'Robertson',
  longForm=TRUE
)
write_csv(robertson, '../20161108__tx__general__robertson__precinct.csv', na='')

sanJacinto <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/SAN_JACINTO_COUNTY-2016_General_Election_1182016-16GSANJA.ASC',
  'San Jacinto',
  houseRegex='United States Representative, District (.+)',
  precinctRegex='Precinct #([0-9]+)'
)
write_csv(sanJacinto, '../20161108__tx__general__san_jacinto__precinct.csv', na='')

yoakum <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/YOAKUM_COUNTY-2016_General_Election_1182016-16GYOAKU.ASC',
  'Yoakum',
  houseRegex='United States Representative, District (.+)',
  longForm=TRUE
)
write_csv(yoakum, '../20161108__tx__general__yoakum__precinct.csv', na='')

angelina <- convert(
  'https://raw.githubusercontent.com/openelections/openelections-sources-tx/master/2016/ANGELINA_COUNTY-2016_General_Election_1182016-ASCII%20FILE%20FOR%20GENERAL%20ELECTION%202016%20%20PCT%20by%20PCT.ASC',
  'Angelina',
  houseRegex='United States Representative, District (.+)'
)
write_csv(angelina, '../20161108__tx__general__angelina__precinct.csv', na='')


