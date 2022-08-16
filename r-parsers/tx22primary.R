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

# Source files expected to be at following location relative to directory r-parsers.
# The working directory should be set to r-parsers. It can be set via the setwd command.
# If you get the message "len=0", the value of dir below is incorrect. Modify it to match the directory.
# Add an out subdirectory to this directory to contain the output files.
# NOTE: Had to use just the subdirectory 2022- 1 March Primary PctxPct due to file paths becoming too long for Windows.
#dir <- "..\\2022- 1 March Primary PctxPct-20220808T225503Z-001\\2022- 1 March Primary PctxPct\\"
dir <- "..\\2022- 1 March Primary PctxPct\\"
# start <- c(1,5, 8,12,18,24,30,36, 42,102,105,112,168,206,236,261)
# end   <- c(4,7,11,17,23,29,35,41,101,104,111,167,205,235,260,263)
# nms   <- c("irace","icandidate","iprecinct","votes","absentee","early_voting","election_day","provisional",
#            "unused","party","party2","office","candidate","precinct","precinct2","racetype")
start <- c(1,5, 8,12,18,21,28, 84,122,152,177)
end   <- c(4,7,11,17,20,27,83,121,151,176,179)
nms   <- c("irace","icandidate","iprecinct","votes",
           "party","party2","office","candidate","precinct","precinct2","racetype")

# Use PopulationEstimates.csv to get county names
filename <- "PopulationEstimates.csv"
us <- read_csv(filename, skip = 4)
names(us) <- c("FIPS","State","Area","Rucode","Pop90","Pop00","Pop10","Pop20","Pop21")
tx <- us[us$State == "TX" & us$Area != "Texas",]
counties <- tx$Area
counties <- gsub(" County","",counties)

list <- list.files(dir, pattern = "*", full.names = FALSE)
len <- length(list)
print(paste0("len=",len))
for (f in list){
    mm <- str_match(f, "^([A-Z_]+)_COUNTY")
    if(!is.na(mm[1,1])){
        county0 <- mm[1,2]
        county <- gsub("_"," ",county0)
        if (grepl("DEMOCRATIC",f)){
            party <- "DEM"
            #print(paste0("DEM ",county))
        }
        else if (grepl("REPUBLICAN",f)){
            party <- "REP"
            #print(paste0("REP ",county))
        }
        else{
            party <- ""
            #print(paste0("########## NO PARTY FOUND IN ",f))
        }
        if (party != "" & grepl(".txt$",f)){
            file_txt <- paste0(dir,f)
            rr <- readLines(file_txt)
            nc <- nchar(rr[1])
            print(paste0(nc,"  ",county0))
            if (nc == 179){
                file_csv <- paste0(dir,"out/",f)
                file_csv <- gsub(".txt",".csv",file_csv)
                f_std <- paste0("20220301__tx__primary__",tolower(county0),"__precinct.csv")
                file_std <- paste0(dir,"out/",f_std)
                #print(paste0("BEFORE read ", file_txt))
                xx <- read_fwf(file_txt, fwf_positions(start, end, nms), col_types = "ccccccc")
                #print(paste0(" AFTER read ", file_txt))
                xx$county <- str_to_title(county) # match standard
                xx$district <- ""
                # nms   <- c("irace","icandidate","iprecinct","votes",
                #            "party","party2","office","candidate","precinct","racetype")
                nmsxx   <- c("county","precinct","office","district","party","candidate","votes")
                xx <- xx[nmsxx]
                # Changes to match standard
                xx$precinct <- gsub("^Precinct [0]*","",xx$precinct, ignore.case = TRUE)
                #xx$precinct <- gsub("^PCT ","",xx$precinct, ignore.case = TRUE) # Wharton County
                xx$party[xx$party == "(D)"] <- "DEM" # El Paso County
                xx$party[xx$party == "(R)"] <- "REP" # El Paso County
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
                xx$party[grepl("^Rep ",xx$office, ignore.case = TRUE)] <- "REP"
                xx$party[grepl("^Dem ",xx$office, ignore.case = TRUE)] <- "DEM"
                xx$office <- gsub("^Rep ","",xx$office, ignore.case = TRUE)
                xx$office <- gsub("^Dem ","",xx$office, ignore.case = TRUE)
                xx$office <- gsub("^Rep ","",xx$office, ignore.case = TRUE) # delete double Rep
                xx$office <- gsub("^Dem ","",xx$office, ignore.case = TRUE) # delete double Dem
                xx$office <- gsub(" Of "," of ",xx$office)
                xx$office <- gsub(" At "," at ",xx$office)
                xx$office <- gsub(" The "," the ",xx$office) # Clay County
                xx$office <- gsub(" And "," and ",xx$office) # Goliad County
                xx$office <- gsub("^Jop ","JOP ",xx$office) # Donley County
                xx$office <- gsub("State Boe","State BoE",xx$office)
                xx$office <- gsub("State Senator","State Senate",xx$office) # Clay County
                xx$office <- gsub("^Us Representative","U.S. House",xx$office, ignore.case = TRUE)
                xx$office <- gsub("^Us Rep,","U.S. House,",xx$office, ignore.case = TRUE) # Goliad County
                xx$office <- gsub("^United States Representative","U.S. House",xx$office, ignore.case = TRUE) # Guadalupe County
                
                for (i in 1:NROW(xx)){
                    mm <- str_match(xx$office[i], "U.S. House, District (\\d+)")
                    if(!is.na(mm[1,1])){
                        xx$district[i] <- mm[1,2]
                        xx$office[i] <- "U.S. House"
                        next
                    }
                    mm <- str_match(xx$office[i],"^(DEM|REP) US Rep, District (\\d+)")
                    if (!is.na(mm[1,1])){
                        xx$office[i] <- paste0(mm[1,2]," US Rep")
                        xx$district[i] <- mm[1,3]
                        xx$office[i] <- "U.S. House"
                        next
                    }
                    mm <- str_match(xx$office[i], "State Senate, Dist (\\d+)")
                    if(!is.na(mm[1,1])){
                        xx$district[i] <- mm[1,2]
                        xx$office[i] <- "State Senate"
                        next
                    }
                    mm <- str_match(xx$office[i], "State Representative, Dist (\\d+)")
                    if(!is.na(mm[1,1])){
                        xx$district[i] <- mm[1,2]
                        xx$office[i] <- "State House"
                        next
                    }
                }

                xx$votes        <- as.numeric(xx$votes)
                # xx$absentee     <- as.numeric(xx$absentee)
                # xx$early_voting <- as.numeric(xx$early_voting)
                # xx$election_day <- as.numeric(xx$election_day)
                # xx$provisional  <- as.numeric(xx$provisional)
                
                # Only delete if all votes for all lines in an office group are zero
                #xx <- xx[xx$office != "Registered Voters - Nonpartisan",] # Robertson County
                lastoffice <- ""
                nonzero <- TRUE
                for (i in 1:NROW(xx)){
                    if (xx$office[i] != lastoffice){
                        if (nonzero == FALSE){
                            if (grepl("Registered Voter",xx$office[i]) | grepl("Ballots Cast",xx$office[i])){
                                for (j in firsti:(i-1)){ #mark for removal
                                    xx$county[j] <- NA
                                }
                            }
                        }
                        nonzero <- (xx$votes[i] != 0)
                        lastoffice <- xx$office[i]
                        firsti <- i
                    }
                    else{
                        if (!nonzero){
                            if (xx$votes[i] != 0){
                                nonzero <- TRUE
                            }
                        }
                    }
                }
                xx <- xx[!is.na(xx$county),]
                
                xx$party[is.na(xx$party)] <- ""
                # sumprov <- sum(xx$provisional)
                # if (sumprov == 0){
                #     xx <- xx[-NCOL(xx)]
                # }
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
}
