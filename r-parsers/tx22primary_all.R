# This program will parse all files of known format. Following are some of the goals for this parser:
#
# Using Tabula, OCR or whatever method you can, parse precinct-level results for the following counties.
# Original sources are in the sources-tx repository.
# 
# The goal is to create a single CSV file for each county, with the following headers:
#     
#     county, precinct, office, district, party, candidate, votes
# 
# If the county file also provides a breakdown of votes by method, include that using the following headers:
#     
#     early_voting, election_day, provisional, mail
# 
# If there are other possible vote types, include them, using a lowercase version of the vote type with
# underscores instead of spaces for the column name.

library("tidyverse")
library("readxl")

# Source files expected to be at following location relative to directory r-parsers.
# The working directory should be set to r-parsers. It can be set via the setwd command.
# If you get the message "nfiles=0", the value of dir below is incorrect. Modify it to match the directory.
# Add an out subdirectory to this directory to contain the output files.
# NOTE: Had to use just the subdirectory 2022- 1 March Primary PctxPct due to file paths becoming too long for Windows.
#dir <- "..\\2022- 1 March Primary PctxPct-20220808T225503Z-001\\2022- 1 March Primary PctxPct\\"
dir <- "..\\2022- 1 March Primary PctxPct\\"
###############################################################################
# set to county in upper case (like "EL PASO") to limit search;
# set to "" to search all counties
###############################################################################
match_county <- "" # set to county in upper case (like "EL PASO") to limit search; set to "" to search all counties

def <- read_csv("TX22county_defs.csv")

# Use PopulationEstimates.csv to get county names
filename <- "PopulationEstimates.csv"
us <- read_csv(filename, skip = 4)
names(us)[1:9] <- c("FIPS","State","Area","Rucode","Pop90","Pop00","Pop10","Pop20","Pop21")
tx <- us[us$State == "TX" & us$Area != "Texas",]
counties <- tx$Area
counties <- gsub(" County","",counties) # not currently needed

list <- list.files(dir, pattern = "*", full.names = FALSE)
len <- length(list)
print(paste0("nfiles=",len))
for (f in list){
    mm <- str_match(f, "^([A-Z_]+)_COUNTY")
    if(!is.na(mm[1,1])){
        county0 <- mm[1,2]
        county <- gsub("_"," ",county0)
        if (match_county != ""){
            if (county != match_county) next
        }
        if (grepl("DEMOCRATIC",f)){
            party <- "DEM"
            #print(paste0("DEM ",county)) #DEBUG
        }
        else if (grepl("REPUBLICAN",f)){
            party <- "REP"
            #print(paste0("REP ",county)) #DEBUG
        }
        else{
            party <- ""
            #print(paste0("########## NO PARTY FOUND IN ",f)) #DEBUG
        }
        nn <- str_match(f, "\\.([A-Za-z]+)$")
        ext <- ""
        if (!is.na(nn[1,1])){
            ext <- nn[1,1]
        }
        gotxx <- FALSE
        xvotes <- FALSE
        #######################################################################
        # Check for known fixed-width formats 
        #######################################################################
        if (party != "" & toupper(ext) %in% c(".TXT",".ASC")){
            file_txt <- paste0(dir,f)
            rr <- readLines(file_txt)
            nc <- nchar(rr[1])
            print(paste0(nc,"  ",county0))
            gotxx <- TRUE
            if (nc == 179){
                start <- c(1,5, 8,12,18,21,28, 84,122,152,177)
                end   <- c(4,7,11,17,20,27,83,121,151,176,179)
                nms   <- c("irace","icandidate","iprecinct","votes",
                           "party","party2","office","candidate","precinct","precinct2","racetype")
                nmsxx <- c("county","precinct","office","district","party","candidate","votes")
                xx <- read_fwf(file_txt, fwf_positions(start, end, nms), col_types = "ccccccccccc")
                xx$county <- str_to_title(county) # match standard
                xx$district <- ""
                xx <- xx[nmsxx]
                xvotes <- FALSE
            }
            else if (nc == 263){
                start <- c(1,5, 8,12,18,24,30,36, 42,102,105,112,168,206,236,261)
                end   <- c(4,7,11,17,23,29,35,41,101,104,111,167,205,235,260,263)
                nms   <- c("irace","icandidate","iprecinct","votes","absentee","early_voting","election_day","provisional",
                           "unused","party","party2","office","candidate","precinct","precinct2","racetype")
                nmsxx <- c("county","precinct","office","district","party","candidate","votes",
                           "absentee","early_voting","election_day","provisional")
                xx <- read_fwf(file_txt, fwf_positions(start, end, nms), col_types = "cccccccccccccccc")
                xx$county <- str_to_title(county) # match standard
                xx$district <- ""
                xx <- xx[nmsxx]
                xvotes <- TRUE
            }
            else{
                gotxx <- FALSE
            }
        }
        #######################################################################
        # Check for all known csv and xlsx formats
        #######################################################################
        else if (party != "" & toupper(ext) %in% c(".CSV",".XLSX")){
            dd <- def[toupper(def$counties) == toupper(county),]
            zdd <<- dd #DEBUG-RM
            if (is.na(dd$desc[1]) | dd$desc[1] == "NA") next
            gotxx <- FALSE
            if (NROW(dd) == 1){
                filename <- paste0(dir,f)
                nskip <- 0
                if (!is.na(dd$skip[1])){
                    nskip <- as.numeric(dd$skip[1])
                }
                nsheet <- 1
                if (!is.na(dd$sheet[1])){
                    nsheet <- dd$sheet[1]
                }
                if (!is.na(dd$desc2[1]) & dd$desc2[1] == "long"){
                    if (toupper(ext) == ".CSV"){
                        vv <- read_csv(filename, col_types = "c", skip = nskip)
                    }
                    else{
                        vv <- read_excel(filename, sheet = nsheet, skip = nskip)
                    }
                    if (county == "BEE"){
                        if (grepl("^election_name",names(vv)[11])){
                            names(vv)[11] <- "election_day_votes"
                        }
                    }
                    zvv <<- vv #DEBUG
                    xx <- vv[c(dd$precinct[1],dd$office[1],dd$candidate[1])]
                    names(xx) <- c("precinct","office","candidate")
                    xx$county <- str_to_title(county) # match standard
                    xx$district <- ""
                    if (!is.na(dd$party[1]) & substr(dd$party[1],1,1) != "|"){
                        xx$party <- vv[[dd$party[1]]]
                    }
                    else{
                        xx$party <- party
                    }
                    nmsxx <- c("county","precinct","office","district","party","candidate")
                    xx <- xx[nmsxx]
                    #nmsxx <- c("county","precinct","office","district","party","candidate","votes",
                    #           "absentee","early_voting","election_day","provisional")
                    xvotes <- FALSE
                    xx$votes <- 0
                    if (!is.na(dd$absentee[1])){
                        xx$absentee <- as.numeric(vv[[dd$absentee[1]]])
                        xx$absentee[is.na(xx$absentee)] <- 0
                        xx$votes <- xx$votes + xx$absentee
                        got_absentee <- TRUE
                        xvotes <- TRUE
                    }
                    else{
                        xx$absentee <- 0
                        got_absentee <- FALSE
                    }
                    if (!is.na(dd$early_voting[1])){
                        xx$early_voting <- as.numeric(vv[[dd$early_voting[1]]])
                        xx$early_voting[is.na(xx$early_voting)] <- 0
                        xx$votes <- xx$votes + xx$early_voting
                        got_early_voting <- TRUE
                        xvotes <- TRUE
                    }
                    else{
                        xx$early_voting <- 0
                        got_early_voting <- FALSE
                    }
                    if (!is.na(dd$election_day[1])){
                        xx$election_day <- as.numeric(vv[[dd$election_day[1]]])
                        xx$election_day[is.na(xx$election_day)] <- 0
                        xx$votes <- xx$votes + xx$election_day
                        got_election_day <- TRUE
                        xvotes <- TRUE
                    }
                    else{
                        xx$election_day <- 0
                        got_election_day <- FALSE
                    }
                    if (!is.na(dd$provisional_counted[1])){
                        xx$provisional <- as.numeric(vv[[dd$provisional_counted[1]]])
                        xx$provisional[is.na(xx$provisional)] <- 0
                        xx$votes <- xx$votes + xx$provisional
                        got_provisional <- TRUE
                        xvotes <- TRUE
                    }
                    else{
                        xx$provisional <- 0
                        got_provisional <- FALSE
                    }
                    if (!is.na(dd$votes[1])){
                        xx$votes <- vv[[dd$votes[1]]]
                        got_votes <- TRUE
                    }
                    gotxx <- TRUE
                }
                else if (!is.na(dd$desc2[1]) & dd$desc2[1] == "opc_hdr"){
                    if (toupper(ext) == ".CSV"){
                        #xxparty <- read_delim(filenamex, ' ', col_names = FALSE, n_max = 1)
                        ohdr <- read_csv(filename, col_names = FALSE, skip = nskip, n_max = 1)
                        phdr <- read_csv(filename, col_names = FALSE, skip = (nskip+1), n_max = 1)
                        chdr <- read_csv(filename, col_names = FALSE, skip = (nskip+2), n_max = 1)
                        vv <- read_csv(filename, col_types = "c", skip = (nskip+2))
                    }
                    # else{
                    #     vv <- read_excel(filename, sheet = nsheet, skip = nskip)
                    # }
                    # Additional logic here
                    gotxx <- FALSE
                } 
                else{
                    gotxx <- FALSE
                }
                xx <- xx[!is.na(xx$office),] # remove blank lines for Austin County
                zdd <<- dd #DEBUG-RM
                zxx <<- xx #DEBUG-RM
            }
            else{
                gotxx <- FALSE
            }
        }
        gxx1 <<- xx #DEBUG-RM
        if (gotxx){
            file_csv <- paste0(dir,"out/",f)
            file_csv <- gsub(ext,".csv",file_csv)
            f_std <- paste0("20220301__tx__primary__",tolower(county0),"__precinct.csv")
            file_std <- paste0(dir,"out/",f_std)
            # Changes to match standard
            xx$precinct <- gsub("^Precinct [0]*","",xx$precinct, ignore.case = TRUE)
            #xx$precinct <- gsub("^PCT ","",xx$precinct, ignore.case = TRUE) # Wharton County
            xx$party[xx$party == "(D)"] <- "DEM" # El Paso County
            xx$party[xx$party == "(R)"] <- "REP" # El Paso County
            xx$party[grepl("^Democratic",xx$party, ignore.case = TRUE)] <- "DEM" #Brazos County
            xx$party[grepl("^Republican",xx$party, ignore.case = TRUE)] <- "REP" #Brazos County
            xx$office <- str_to_title(xx$office)
            
            xx$office[xx$office == "Registered Voters - Total"] <- "Registered Voters"
            xx$candidate[grepl("^REGISTERED VOTERS",xx$candidate,ignore.case = TRUE)] <- ""
            
            #xx$office[xx$office == "Ballots Cast - Blank"] <- "BALLOTS CAST - BLANK" # avoids next statement
            #xx$office[grepl("^Ballots Cast -",xx$office)] <- "Ballots Cast"
            xx$office[grepl("^Ballots Cast - Republican",xx$office)] <- "Ballots Cast"
            xx$office[grepl("^Ballots Cast - Democratic",xx$office)] <- "Ballots Cast"
            xx$office[grepl("^Ballots Cast - Nonpartisan",xx$office)] <- "Ballots Cast"
            xx$office[grepl("^Ballots Cast - Total",xx$office)] <- "Ballots Cast"
            xx$candidate[grepl("^BALLOTS CAST",xx$candidate,ignore.case = TRUE)] <- ""
            xx$party[grepl("^\\(R\\) ",xx$office, ignore.case = TRUE)] <- "REP" # El Paso County
            xx$party[grepl("^\\(D\\) ",xx$office, ignore.case = TRUE)] <- "DEM" # El Paso County
            xx$party[grepl("^Rep ",xx$office, ignore.case = TRUE)] <- "REP"
            xx$party[grepl("^Dem ",xx$office, ignore.case = TRUE)] <- "DEM"
            xx$office <- gsub("^\\(R\\) ","",xx$office, ignore.case = TRUE) # El Paso County
            xx$office <- gsub("^\\(D\\) ","",xx$office, ignore.case = TRUE) # El Paso County
            xx$office <- gsub("^Rep\\.? ","",xx$office, ignore.case = TRUE)
            xx$office <- gsub("^Dem\\.? ","",xx$office, ignore.case = TRUE)
            xx$office <- gsub("^Rep ","",xx$office, ignore.case = TRUE) # delete double Rep
            xx$office <- gsub("^Dem ","",xx$office, ignore.case = TRUE) # delete double Dem
            xx$office <- gsub(" Of "," of ",xx$office)
            xx$office <- gsub(" At "," at ",xx$office)
            xx$office <- gsub("-At-","-at-",xx$office) # Austin County
            xx$office <- gsub(" The "," the ",xx$office) # Clay County
            xx$office <- gsub(" And "," and ",xx$office) # Goliad County
            xx$office <- gsub("^Jop ","JOP ",xx$office) # Donley County
            xx$office <- gsub("State Boe","State BoE",xx$office)
            xx$office <- gsub("State Senator","State Senate",xx$office) # Clay County
            xx$office <- gsub("^U\\.? ?s\\.? Representative","U.S. House",xx$office, ignore.case = TRUE) # Brazos County
            xx$office <- gsub("^U\\.? ?s\\.? Rep,","U.S. House,",xx$office, ignore.case = TRUE) # Goliad County
            xx$office <- gsub("^United States Representative","U.S. House",xx$office, ignore.case = TRUE) # Guadalupe County
            xx$office <- gsub("^County  Commissioner","County Commissioner",xx$office, ignore.case = TRUE) # Guadalupe County
            
            for (i in 1:NROW(xx)){
                mm <- str_match(xx$office[i], "U.S. House\\,? Dist\\.?(?:rict)? (\\d+)")
                if(!is.na(mm[1,1])){
                    xx$district[i] <- mm[1,2]
                    xx$office[i] <- "U.S. House"
                    next
                }
                mm <- str_match(xx$office[i],"Us Rep(?: \\d+ Us)\\,? Dist\\.?(?:rict)? (\\d+)")
                if(!is.na(mm[1,1])){
                    xx$district[i] <- mm[1,2]
                    xx$office[i] <- "U.S. House"
                    next
                }
                mm <- str_match(xx$office[i], "State Senate\\,? Dist\\.?(?:rict)? (\\d+)")
                if(!is.na(mm[1,1])){
                    xx$district[i] <- mm[1,2]
                    xx$office[i] <- "State Senate"
                    next
                }
                mm <- str_match(xx$office[i], "State Representative\\,? Dist\\.?(?:rict)? (\\d+)")
                if(!is.na(mm[1,1])){
                    xx$district[i] <- mm[1,2]
                    xx$office[i] <- "State House"
                    next
                }
            }
            gxx <<- xx #DEBUG-RM

            xx$votes        <- as.numeric(xx$votes)
            if (xvotes){
                xx$absentee     <- as.numeric(xx$absentee)
                xx$early_voting <- as.numeric(xx$early_voting)
                xx$election_day <- as.numeric(xx$election_day)
                xx$provisional  <- as.numeric(xx$provisional)
            }
            
            # Only delete if all votes for all lines in an office group are zero
            #xx <- xx[xx$office != "Registered Voters - Nonpartisan",] # Robertson County
            lastoffice <- ""
            nonzero <- TRUE
            for (i in 1:NROW(xx)){
                if (xx$office[i] != lastoffice){
                    if (is.na(nonzero) | !nonzero){
                        if (grepl("Registered Voter",xx$office[i]) | grepl("Ballots Cast",xx$office[i])){
                            for (j in firsti:(i-1)){ #mark for removal
                                xx$county[j] <- NA
                            }
                        }
                    }
                    if (xvotes){
                        nonzero <- (xx$votes[i] != 0 | xx$absentee[i] != 0 | xx$early_voting[i] != 0 | xx$election_day[i] != 0 | xx$provisional[i] != 0)
                    }
                    else{
                        nonzero <- (xx$votes[i] != 0)
                    }
                    lastoffice <- xx$office[i]
                    firsti <- i
                }
                else{
                    if (is.na(nonzero) | !nonzero){
                        if (xvotes){
                            nonzero <- (xx$votes[i] != 0 | xx$absentee[i] != 0 | xx$early_voting[i] != 0 | xx$election_day[i] != 0 | xx$provisional[i] != 0)
                        }
                        else{
                            nonzero <- (xx$votes[i] != 0)
                        }
                    }
                }
            }
            xx <- xx[!is.na(xx$county),]
            
            xx$party[is.na(xx$party)] <- ""
            if (xvotes){
                # delete provisional if their sum = 0
                iprov <- which(names(xx) == "provisional")
                sumprov <- sum(xx$provisional, na.rm = TRUE)
                if (sumprov == 0){
                    xx <- xx[-iprov]
                }
                # delete absentee if their sum = 0
                iabsent <- which(names(xx) == "absentee")
                sumabsent <- sum(xx$absentee, na.rm = TRUE)
                if (sumabsent == 0){
                    xx <- xx[-iabsent]
                }
            }
            # fix missing precincts if surrounded by same precinct - Austin County
            ipna <- which(is.na(xx$precinct))
            lpna <- length(ipna)
            if (lpna > 0){
                for (i in 1:lpna){
                    if (ipna[i] > 1 & ipna[i] < NROW(xx)){
                        if (xx$precinct[ipna[i]-1] == xx$precinct[ipna[i]+1]){
                            xx$precinct[ipna[i]] <- xx$precinct[ipna[i]-1]
                        }
                    }
                }
            }
            zxx <<- xx #DEBUG
            # tests to replicate prior files
            test_replicates <- FALSE
            if (test_replicates){
                if (toupper(county) == "AUSTIN"){
                    xx$office <- gsub("State House","State Representative",xx$office)
                    nmsxx <- c("county","precinct","office","district","candidate","party",
                               "early_voting","election_day","votes")
                    xx <- xx[nmsxx]
                }
                else if (toupper(county) == "CAMERON"){
                    #xx$precinct <- lapply(xx$precinct[], function(x) paste('Precinct ', x))
                    xx$precinct <- gsub("^","Precinct ",xx$precinct)
                    xx$office <- gsub("State House","State Representative",xx$office)
                }
                else if (toupper(county) == "BAILEY"){
                    nmsxx <- c("county","precinct","office","district","candidate","party",
                               "early_voting","election_day","provisional","votes")
                    xx <- xx[nmsxx]
                    xx <- xx[-which(names(xx) == "provisional")] #DEBUG-DUPLICATE
                    xx$office <- toupper(xx$office)
                    xx$office <- gsub("U.S. HOUSE","U.S. House",xx$office)
                    xx$office <- gsub("COMM GENERAL LAND OFFICE","COMM GENERAL LAND OFFICE ",xx$office)
                    xx$candidate <- gsub("KEN PAXTON","KEN PAXTON ",xx$candidate)
                    xx$candidate <- gsub("JAMES WHITE","JAMES WHITE ",xx$candidate)
                    xx$candidate <- gsub("JOY DIAZ","JOY DIAZ ",xx$candidate)
                    xx$office <- gsub("STATE SENATE","State Senate",xx$office)
                    xx$office <- gsub("STATE HOUSE","State Representative",xx$office)
                }
            }
            write_csv(xx, file_csv)
            write_csv(xx, file_std)
            print(paste0(" AFTER write ", file_std))
            # Write DEM.txt to DEM.csv and REP.txt to REP.csv and write both to [file_std].csv.
            # This is required for final step which is currently done manually. If the DEM.csv
            # and REP.csv are identical, then [file_std].csv should contain the final file.
            # If they are different, diff the DEM.csv and REP.csv files and add that part of
            # the DEM.csv not duplicated in the REP.csv to the end of [file_std].csv. This
            # should include only one header (on the first line) and should be the final file.
        }
    }
}
