library(tidyverse)
library(tabulizer)

pdfFile <- tempfile()
download.file('https://github.com/openelections/openelections-sources-tx/raw/master/2016/2016%20DALLAS%201108G%20General%20Final%20PctbyPct%20Totals.pdf',
              pdfFile, mode='wb')

INTERACTIVE <- FALSE

dfs <- list()

dfs$RegisteredVoters <- extract_tables(pdfFile, 1:15) %>%
  map_df(function(pageMatrix) {
  pageMatrix %>%
    as_data_frame() %>%
    mutate(precinct=gsub(x=V1, pattern='[0-9]+ (.+)', replacement='\\1'),
           V2=gsub(x=V2, pattern=' \\.', replacement=' ')) %>%
    mutate(V2=gsub(x=V2, pattern=' [ ]*', replacement=' ')) %>%
    separate(V2, c('rv', 'bc', 'p'), sep=' ') %>%
    select(-V1, -p) %>%
    gather(key='office', value='vote', -precinct) %>%
    mutate(office=case_when(
      office=='rv' ~ 'Registered Voters',
      office=='bc' ~ 'Ballots Cast'
    )) %>%
      mutate(vote=as.integer(vote))
}) %>% bind_rows(
  # had to do this by hand...tabulizer extract_tables by area wouldn't work...
  tibble(
    precinct=rep(c('4662-6550','4664-6554','4664-6555'), 2),
    office=c(rep('Registered Voters', 3), rep('Ballots Cast', 3)),
    vote=c(249,984,723,127,608,540)
  )
) %>% mutate(candidate=office, district=NA_integer_, party=NA_character_)

parseOfficePages <- function(columnNames, partyLookup=character(), officeName, pages, district=NA_integer_, precinctCountChecksum=800) {
  ret <- extract_tables(pdfFile, pages) %>%
    map_df(parseOfficeMatrix, columnNames=columnNames, partyLookup=partyLookup, officeName=officeName, district=district)
  if (!is.null(precinctCountChecksum)) {
    if (nrow(ret)/length(columnNames) != precinctCountChecksum) {
      warning(paste0('Missing precincts detected for office ', officeName, '. Expecting ', precinctCountChecksum, ' but found ', nrow(ret), ' records and ',
                     length(columnNames), ' ballot options, or ', (nrow(ret)/length(columnNames)), ' precincts.'))
    }
  }
  ret
}

parseOfficeMatrix <- function(pageMatrix, columnNames, partyLookup=character(), officeName, district=NA_integer_) {
  lookup <- columnNames
  names(lookup) <- paste0('V', 1 + seq_len(length(columnNames)))
  pageMatrix %>%
    as_data_frame() %>%
    mutate(precinct=gsub(x=V1, pattern='[0-9]+ (.+)', replacement='\\1')) %>%
    select(-V1) %>%
    gather(key='candidate', value='vote', -precinct) %>%
    mutate(candidate=lookup[candidate]) %>%
    mutate(office=officeName, district=district, party=partyLookup[candidate], vote=as.integer(vote))
}

dfs$StraightParty <- parseOfficePages(
  columnNames=c('Republican Party', 'Democratic Party', 'Libertarian Party', 'Green Party', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Republican Party'='REP', 'Democratic Party'='DEM', 'Libertarian Party'='LIB', 'Green Party'='GRN'),
  officeName='Straight Party',
  pages=16:30
)

dfs$President <- parseOfficePages(
  columnNames=c('Donald J. Trump', 'Hillary Clinton', 'Gary Johnson', 'Jill Stein', 'WRITE-IN', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Donald J. Trump'='REP', 'Hillary Clinton'='DEM', 'Gary Johnson'='LIB', 'Jill Stein'='GRN'),
  officeName='President and Vice President',
  pages=31:46
)

dfs$House5 <- parseOfficePages(
  columnNames=c('Jeb Hensarling', 'Ken Ashby', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Jeb Hensarling'='REP', 'Ken Ashby'='DEM'),
  officeName='U.S. House',
  district=5,
  pages=47:48,
  precinctCountChecksum=103
)

dfs$House24 <- parseOfficePages(
  columnNames=c('Kenny E. Marchant', 'Jan McDowell', 'Mike Kolls', 'Kevin McCormick', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Kenny E. Marchant'='REP', 'Jan McDowell'='DEM', 'Mike Kolls'='LIB', 'Kevin McCormick'='GRN'),
  officeName='U.S. House',
  district=24,
  pages=49:51,
  precinctCountChecksum=132
)

# tabulizer wouldn't parse
dfs$House26 <- tibble(
  precinct=c(rep('2910-5709', 5), rep('2911-5710', 5)),
  candidate=rep(c('Michael C. Burgess', 'Eric Mauck', 'Mark Boler', 'OVER VOTES', 'UNDER VOTES'), 2),
  vote=c(13,9,0,0,1,89,61,6,0,3),
  office='U.S. House',
  district=26,
  party=rep(c('REP','DEM','LIB', NA_character_, NA_character_), 2)
)
  
dfs$House30 <- parseOfficePages(
  columnNames=c('Charles Lingerfelt', 'Eddie Bernice Johnson', 'Jarrett R. Woods', 'Thom Prentice', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Charles Lingerfelt'='REP', 'Eddie Bernice Johnson'='DEM', 'Jarrett R. Woods'='LIB', 'Thom Prentice'='GRN'),
  officeName='U.S. House',
  district=30,
  pages=53:57,
  precinctCountChecksum=254
)

dfs$House32 <- parseOfficePages(
  columnNames=c('Pete Sessions', 'Ed Rankin', 'Gary Stuard', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Pete Sessions'='REP', 'Ed Rankin'='DEM', 'Gary Stuard'='GRN'),
  officeName='U.S. House',
  district=32,
  pages=58:61,
  precinctCountChecksum=200
)

dfs$House33 <- parseOfficePages(
  columnNames=c('M.Mark Mitchell', 'Marc Veasey', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('M.Mark Mitchell'='REP', 'Marc Veasey'='DEM'),
  officeName='U.S. House',
  district=33,
  pages=62:63,
  precinctCountChecksum=109
)

dfs$RailroadCommissioner <- parseOfficePages(
  columnNames=c('Wayne Christian', 'Grady Yarbrough', 'Mark Miller', 'Martina Salinas', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Wayne Christian'='REP', 'Grady Yarbrough'='DEM', 'Mark Miller'='LIB', 'Martina Salinas'='GRN'),
  officeName='U.S. House',
  pages=64:78
)

dfs$Justice3 <- parseOfficePages(
  columnNames=c('Debra Lehrmann', 'Mike Westergren', 'Kathie Glass', 'Rodolfo Rivera Munoz', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Debra Lehrmann'='REP', 'Mike Westergren'='DEM', 'Kathie Glass'='LIB', 'Rodolfo Rivera Munoz'='GRN'),
  officeName='Justice, Supreme Court, Pl 3',
  pages=79:93
)

dfs$Justice5 <- parseOfficePages(
  columnNames=c('Paul Green', 'Dori Contreras Garza', 'Tom Oxford', 'Charles E. Waterbury', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Paul Green'='REP', 'Dori Contreras Garza'='DEM', 'Tom Oxford'='LIB', 'Charles E. Waterbury'='GRN'),
  officeName='Justice, Supreme Court, Pl 5',
  pages=94:108
)

dfs$Justice9 <- parseOfficePages(
  columnNames=c('Eva Guzman', 'Savannah Robinson', 'Don Fulton', 'Jim Chisholm', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Eva Guzman'='REP', 'Savannah Robinson'='DEM', 'Don Fulton'='LIB', 'Jim Chisholm'='GRN'),
  officeName='Justice, Supreme Court, Pl 9 DAL COUNTY WIDE',
  pages=109:123
)

dfs$Appeals2 <- parseOfficePages(
  columnNames=c('Mary Lou Keel', 'Lawrence "Larry" Meyers', 'Mark Ash', 'Adam King Blackwell Reposa', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Mary Lou Keel'='REP', 'Lawrence "Larry" Meyers'='DEM', 'Mark Ash'='LIB', 'Adam King Blackwell Reposa'='GRN'),
  officeName='Judge, Ct of Criminal Appeals, Pl 2',
  pages=124:138
)

dfs$Appeals5 <- parseOfficePages(
  columnNames=c('Scott Walker', 'Betsy Johnson', 'William Bryan Strange, III', 'Judith Sanders-Castro', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Scott Walker'='REP', 'Betsy Johnson'='DEM', 'William Bryan Strange, III'='LIB', 'Judith Sanders-Castro'='GRN'),
  officeName='Judge, Ct of Criminal Appeals, Pl 5',
  pages=139:153
)

dfs$Appeals6 <- parseOfficePages(
  columnNames=c('Michael E. Keasler', 'Robert Burns', 'Mark W. Bennett', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Michael E. Keasler'='REP', 'Robert Burns'='DEM', 'Mark W. Bennett'='LIB'),
  officeName='Judge, Ct of Criminal Appeals, Pl 6',
  pages=154:168
)

# have to manually find the table on page 170
if (INTERACTIVE) p170 <- extract_areas(pdfFile, 170) %>%
  .[[1]] %>%
  parseOfficeMatrix(
    columnNames=c('Eric Johnson', 'Heather Marcus', 'OVER VOTES', 'UNDER VOTES'),
    partyLookup=c('Eric Johnson'='DEM', 'Heather Marcus'='LIB'),
    officeName='State Representative',
    district=100
  )

dfs$StateRep100 <- parseOfficePages(
  columnNames=c('Eric Johnson', 'Heather Marcus', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Eric Johnson'='DEM', 'Heather Marcus'='LIB'),
  officeName='State Representative',
  district=100,
  pages=169,
  precinctCountChecksum=NULL
) %>% bind_rows(p170)

dfs$StateRep102 <- parseOfficePages(
  columnNames=c('Linda Koop', 'Laura Irvin', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Linda Koop'='REP', 'Laura Irvin'='DEM'),
  officeName='State Representative',
  district=102,
  pages=171,
  precinctCountChecksum=47
)

dfs$StateRep103 <- parseOfficePages(
  columnNames=c('Rafael M. Anchia', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Rafael M. Anchia'='DEM'),
  officeName='State Representative',
  district=103,
  pages=172:173,
  precinctCountChecksum=69
)

dfs$StateRep104 <- parseOfficePages(
  columnNames=c('Roberto R. Alonzo', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Roberto R. Alonzo'='DEM'),
  officeName='State Representative',
  district=104,
  pages=174,
  precinctCountChecksum=51
)

dfs$StateRep105 <- parseOfficePages(
  columnNames=c('Rodney Anderson', 'Terry Meza', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Rodney Anderson'='REP', 'Terry Meza'='DEM'),
  officeName='State Representative',
  district=105,
  pages=175,
  precinctCountChecksum=54
)

dfs$StateRep107 <- parseOfficePages(
  columnNames=c('Kenneth Sheets', 'Victoria Neave', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Kenneth Sheets'='REP', 'Victoria Neave'='DEM'),
  officeName='State Representative',
  district=107,
  pages=176,
  precinctCountChecksum=52
)

dfs$StateRep108 <- parseOfficePages(
  columnNames=c('Morgan Meyer', 'Scott Smith', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Morgan Meyer'='REP', 'Scott Smith'='LIB'),
  officeName='State Representative',
  district=108,
  pages=177:178,
  precinctCountChecksum=65
)

dfs$StateRep109 <- parseOfficePages(
  columnNames=c('A. Denise Russell', 'Helen Giddings', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('A. Denise Russell'='REP', 'Helen Giddings'='DEM'),
  officeName='State Representative',
  district=109,
  pages=179:180,
  precinctCountChecksum=66
)

dfs$StateRep110 <- parseOfficePages(
  columnNames=c('Toni Rose', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Toni Rose'='DEM'),
  officeName='State Representative',
  district=110,
  pages=181,
  precinctCountChecksum=52
)

if (INTERACTIVE) p183 <- extract_areas(pdfFile, 183) %>%
  .[[1]] %>%
  parseOfficeMatrix(
    columnNames=c('Chad O. Jackson', 'Yvonne Davis', 'OVER VOTES', 'UNDER VOTES'),
    partyLookup=c('Chad O. Jackson'='REP', 'Yvonne Davis'='DEM'),
    officeName='State Representative',
    district=111
  )

dfs$StateRep111 <- parseOfficePages(
  columnNames=c('Chad O. Jackson', 'Yvonne Davis', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Chad O. Jackson'='REP', 'Yvonne Davis'='DEM'),
  officeName='State Representative',
  district=111,
  pages=182,
  precinctCountChecksum=NULL
) %>% bind_rows(p183)

dfs$StateRep112 <- parseOfficePages(
  columnNames=c('Angie Chen Button', 'Jack Blackshear', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Angie Chen Button'='REP', 'Jack Blackshear'='DEM'),
  officeName='State Representative',
  district=112,
  pages=184,
  precinctCountChecksum=37
)

dfs$StateRep113 <- parseOfficePages(
  columnNames=c('Cindy Burkett', 'Rhetta Andrews Bowers', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Cindy Burkett'='REP', 'Rhetta Andrews Bowers'='DEM'),
  officeName='State Representative',
  district=113,
  pages=185,
  precinctCountChecksum=43
)

dfs$StateRep114 <- parseOfficePages(
  columnNames=c('Jason Villalba', 'Jim Burke', 'Anthony Holan', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Jason Villalba'='REP', 'Jim Burke'='DEM', 'Anthony Holan'='LIB'),
  officeName='State Representative',
  district=114,
  pages=186:187,
  precinctCountChecksum=68
)

dfs$StateRep115 <- parseOfficePages(
  columnNames=c('Matt Rinaldi', 'Dorotha M. Ocker', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Matt Rinaldi'='REP', 'Dorotha M. Ocker'='DEM'),
  officeName='State Representative',
  district=115,
  pages=188:189,
  precinctCountChecksum=66
)

dfs$CoA5Pl4 <- parseOfficePages(
  columnNames=c('Lana Myers', 'Gena Slaughter', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Lana Myers'='REP', 'Gena Slaughter'='DEM'),
  officeName='Justice, 5th Ct of App Dist, Pl 4',
  pages=190:204
)

dfs$CoA5Pl7 <- parseOfficePages(
  columnNames=c('David John Schenck', 'Dennise Garcia', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('David John Schenck'='REP', 'Dennise Garcia'='DEM'),
  officeName='Justice, 5th Ct of App Dist, Pl 7',
  pages=205:219
)

dfs$Judge14 <- parseOfficePages(
  columnNames=c('Barry Johnson', 'Eric Moye', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Barry Johnson'='REP', 'Eric Moye'='DEM'),
  officeName='Judge, 14th Judicial District',
  pages=220:234
)

dfs$Judge95 <- parseOfficePages(
  columnNames=c('Ken Molberg', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Ken Molberg'='DEM'),
  officeName='Judge, 95th Judicial District',
  pages=235:249
)

dfs$Judge162 <- parseOfficePages(
  columnNames=c('Gregory Gorman', 'Maricela Moore', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Gregory Gorman'='REP', 'Maricela Moore'='DEM'),
  officeName='Judge, 162nd Judicial District',
  pages=250:264
)

dfs$Judge195 <- parseOfficePages(
  columnNames=c('Mike Lee', 'Hector Garza', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Mike Lee'='REP', 'Hector Garza'='DEM'),
  officeName='Judge, 195th Judicial Dist Unexpired',
  pages=265:279
)

dfs$Judge254 <- parseOfficePages(
  columnNames=c('Susan Rankin', 'Darlene Ewing', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Susan Rankin'='REP', 'Darlene Ewing'='DEM'),
  officeName='Judge, 254th Judicial Dist Unexpired',
  pages=280:294
)

dfs$CrimJudge2 <- parseOfficePages(
  columnNames=c('Tom Spackman', 'Nancy Kennedy', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Tom Spackman'='REP', 'Nancy Kennedy'='DEM'),
  officeName='Criminal Dist Judge, Ct No. 2',
  pages=295:309
)

dfs$CrimJudge3 <- parseOfficePages(
  columnNames=c('Gracie Lewis', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Gracie Lewis'='DEM'),
  officeName='Criminal Dist Judge, Ct No. 3',
  pages=310:324
)

dfs$CrimJudge4 <- parseOfficePages(
  columnNames=c('Dominique Collins', 'William R. Barr', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Dominique Collins'='DEM', 'William R. Barr'='GRN'),
  officeName='Criminal Dist Judge, Ct No. 4',
  pages=325:339
)

dfs$Sheriff <- parseOfficePages(
  columnNames=c('Kirk Launius', 'Lupe Valdez', 'David Geoffrey Morris', 'J. C. Osborne', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Kirk Launius'='REP', 'Lupe Valdez'='DEM', 'David Geoffrey Morris'='LIB', 'J. C. Osborne'='GRN'),
  officeName='Sheriff',
  pages=340:354
)

dfs$Assessor <- parseOfficePages(
  columnNames=c('John R. Ames', 'James Birchfield', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('John R. Ames'='DEM', 'James Birchfield'='LIB'),
  officeName='County Tax Assessor-Collector',
  pages=355:369
)

dfs$Commissioner1 <- parseOfficePages(
  columnNames=c('Steven Rayshell', 'Theresa Daniel', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Steven Rayshell'='REP', 'Theresa Daniel'='DEM'),
  officeName='County Commissioner, Pct No. 1',
  pages=370:373,
  precinctCountChecksum=186
)

dfs$Commissioner3 <- parseOfficePages(
  columnNames=c('S.T. Russell', 'John Wiley Price', 'Ona Marie Hendricks', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('S.T. Russell'='REP', 'John Wiley Price'='DEM', 'Ona Marie Hendricks'='GRN'),
  officeName='County Commissioner, Pct No. 3',
  pages=374:377,
  precinctCountChecksum=200
)

dfs$JP2Pl1 <- parseOfficePages(
  columnNames=c('Brian Hutcheson', 'Latonya D. Shavers', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Brian Hutcheson'='REP', 'Latonya D. Shavers'='DEM'),
  officeName='Justice Peace, Pct No. 2, Pl 1 Unexpired',
  pages=378:380,
  precinctCountChecksum=131
)

dfs$Constable1 <- parseOfficePages(
  columnNames=c('Tracey Gulley', 'OVER VOTES', 'UNDER VOTES'),
  partyLookup=c('Tracey Gulley'='DEM'),
  officeName='Constable, Pct No. 1 Unexpired Term',
  pages=381:383,
  precinctCountChecksum=155
)

balchList <- map(1:8, function(propNumber) {
  parseOfficePages(
    columnNames=c('For (A Favor)', 'Against (En Contra)', 'OVER VOTES', 'UNDER VOTES'),
    officeName=paste0('Balch Springs Proposition ', propNumber),
    pages=383 + propNumber,
    precinctCountChecksum=13
  )
})

names(balchList) <- paste0('Balch', 1:8)

dfs <- c(dfs, balchList)
rm(balchList)

if (INTERACTIVE) p392 <- extract_areas(pdfFile, 392) %>%
  .[[1]] %>%
  parseOfficeMatrix(
    columnNames=c('Leon Payton Tate', 'WRITE-IN', 'OVER VOTES', 'UNDER VOTES'),
    officeName='Glenn Heights-Mayor'
  )

dfs$GlennHeightsMayor <- p392

if (INTERACTIVE) p393 <- extract_areas(pdfFile, 393) %>%
  .[[1]] %>%
  parseOfficeMatrix(
    columnNames=c('Tony L. Bradley', 'OVER VOTES', 'UNDER VOTES'),
    officeName='Glenn Heights- Council Member Pl 2'
  )

dfs$GlennHeightsCouncil2 <- p393

if (INTERACTIVE) p394 <- extract_areas(pdfFile, 394) %>%
  .[[1]] %>%
  parseOfficeMatrix(
    columnNames=c('Ron Adams', 'OVER VOTES', 'UNDER VOTES'),
    officeName='Glenn Heights- Pl 4'
  )

dfs$GlennHeightsCouncil4 <- p394

if (INTERACTIVE) p395 <- extract_areas(pdfFile, 395) %>%
  .[[1]] %>%
  parseOfficeMatrix(
    columnNames=c('Glenn George', 'OVER VOTES', 'UNDER VOTES'),
    officeName='Glenn Heights- Council Member Pl 6'
  )

dfs$GlennHeightsCouncil6 <- p395

dfs$DallasProposition <- parseOfficePages(
  columnNames=c('For (A Favor)', 'Against (En Contra)', 'OVER VOTES', 'UNDER VOTES'),
  officeName='City of Dallas Proposition',
  pages=396:403,
  precinctCountChecksum=419
)

dfs$GPProposition <- parseOfficePages(
  columnNames=c('Yes (Si)', 'No (No)', 'OVER VOTES', 'UNDER VOTES'),
  officeName='Grand Prairie Proposition 1',
  pages=404,
  precinctCountChecksum=38
)

dfs$CFBISD <- parseOfficePages(
  columnNames=c('For (A Favor)', 'Against (En Contra)', 'OVER VOTES', 'UNDER VOTES'),
  officeName='CFBISD Proposition 1',
  pages=405,
  precinctCountChecksum=38
)

dallas <- bind_rows(dfs) %>%
  mutate(county='Dallas') %>%
  select(county,precinct,office,district,party,candidate,vote)

write_csv(dallas, '../20161108__tx__general__dallas__precinct.csv', na='')
