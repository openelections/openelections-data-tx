library(openxlsx)
library(tidyverse)

# To run this script, you'll need to download the 2016 results zip from
# http://www.dallascountyvotes.org/election-results-and-maps/election-results/historical-election-results/#ElectionResults

# unzip the contents of the zipfile for the 2016 general election, under the /tmp directory

# before running the script, you'll need to open the file in Microsoft Excel (Dallas County stored it in an old xml format that can only be opened
# in Excel itself).  Save it as .xlsx, then proceed.

excelFile <- '/tmp/161108 SOE General Final Canvassed Results.xlsx'

toc <- read.xlsx(excelFile, sheet=1, colNames=TRUE, startRow=4)

rv <- read.xlsx(excelFile, sheet=2) %>%
  gather(key='office', value='vote', -Precinct) %>%
  mutate(office=gsub(x=office, pattern='\\.', replacement=' ')) %>%
  mutate(district=NA, party=NA, candidate=office) %>%
  rename(precinct=Precinct)

dallas <- map2_df(tail(toc$Page, -1), tail(toc$Contest, -1), function(tocPage, tocContest) {
  
  sheetNum <- tocPage+1
  
  candidates <- read.xlsx(excelFile, sheet=sheetNum, colNames=FALSE, rows=2) %>%
    gather() %>% .$value
  
  page <- read.xlsx(excelFile, sheet=sheetNum, startRow=4, colNames=FALSE) %>%
    select(c(1, 8 + 6*(seq(0, length(candidates)-1)))) %>%
    gather(key='X', value='vote', -X1) %>%
    select(-X) %>%
    rename(precinct=X1)
  
  candidate <- rep(candidates, rep(nrow(page)/length(candidates), length(candidates)))
  
  page %>% mutate(candidate=candidate, office=tocContest, district=NA, party=NA)
  
})

stateRepRegex <- 'State Representative, Dist ([0-9]+)'
usRepRegex <- 'U\\. S\\. Representative Dist ([0-9]+)'

dallas2 <- dallas %>%
  mutate(office=gsub(x=office, pattern='(.+) \\(Vote.+', replacement='\\1')) %>%
  mutate(office=gsub(x=office, pattern=stateRepRegex, 'State Representative'),
         district=gsub(x=office, pattern=stateRepRegex, '\\1')) %>%
  mutate(office=gsub(x=office, pattern=usRepRegex, 'U.S. House'),
         district=gsub(x=office, pattern=stateRepRegex, '\\1'))