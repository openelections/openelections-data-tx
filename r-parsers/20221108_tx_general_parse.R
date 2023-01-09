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

duplicated_precinct <- c("BANDERA","DENTON","FANNIN","GRAY","LUBBOCK")
duplicated_all <- c("COOKE","CORYELL","EASTLAND","GAINES","GREGG","LLANO","UVALDE")
duplicated_other <- c("BEE")
duplicated_any <- c(duplicated_precinct,duplicated_all,duplicated_other)

valid_provisionals <- function(county){
    if (toupper(county) %in% duplicated_any){
        print(paste0("########## WARNING: IGNORING INVALID PROVISIONALS IN ",county)) #DEBUG
        return(FALSE)
    }
    return(TRUE)
}

# Source files expected to be at following location relative to directory r-parsers.
# The working directory should be set to r-parsers. It can be set via the setwd command.
# If you get the message "nfiles=0", the value of dir below is incorrect. Modify it to match the directory.
# Add an out subdirectory to this directory to contain the output files.
# NOTE: Had to use just the subdirectory 2022- 1 March Primary PctxPct due to file paths becoming too long for Windows.
#dir <- "..\\2022- 1 March Primary PctxPct\\"
dir <- "..\\2022- 8 November GE Pctxpct\\"
print(paste0("STARTTIME=",Sys.time()))
###############################################################################
# set to county in upper case (like "EL PASO") to limit search;
# set to "" to search all counties
###############################################################################
match_county <- "" # set to county in upper case (like "EL PASO") to limit search; set to "" to search all counties

if (!file.exists("20221108_tx_general_defs.csv")){
    setwd("./r-parsers")
}
def <- read_csv("20221108_tx_general_defs.csv")

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
    if (match_county == ""){
        print(paste0("f=",f)) #DEBUG
    }
    mm <- str_match(f, "^([A-Z_]+)_COUNTY")
    if(!is.na(mm[1,1])){
        county0 <- mm[1,2]
        county <- gsub("_"," ",county0)
        if (match_county != ""){
            if (county != match_county) next
        }
        nn <- str_match(f, "\\.([A-Za-z]+)$")
        ext <- ""
        if (!is.na(nn[1,1])){
            ext <- nn[1,1]
        }
        gotxx <- FALSE
        xvotes <- FALSE
        party <- "" #CHANGE-UNCOMMENT
        #######################################################################
        # Check for known fixed-width formats 
        #######################################################################
        if (toupper(ext) %in% c(".TXT",".ASC")){
            file_txt <- paste0(dir,f)
            rr <- readLines(file_txt)
            nc <- nchar(rr[1])
            print(paste0(nc,"  ",county0))
            gotxx <- TRUE
            # if (nc == 161){ # Donley County (in progress)
            #     #desc      r c ip vo pa p2 of  ca  pr  p2  rt
            #     start <- c(1,5, 8,12,19,21,28, 84,122,152,177)
            #     end   <- c(4,7,11,18,20,27,83,121,151,176,179)
            #     nms   <- c("irace","icandidate","iprecinct","votes",
            #                "party","party2","office","candidate","precinct","precinct2","racetype")
            #     nmsxx <- c("county","precinct","office","district","party","candidate","votes")
            #     xx <- read_fwf(file_txt, fwf_positions(start, end, nms), col_types = "ccccccccccc")
            #     xx$county <- str_to_title(county) # match standard
            #     xx$district <- ""
            #     xx <- xx[nmsxx]
            #     xvotes <- FALSE
            # }
            if (nc == 179){
                #desc      r c ip vo pa p2 of  ca  pr  p2  rt
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
                nms   <- c("irace","icandidate","iprecinct","votes","election_day","early_voting","absentee","provisional",
                           "unused","party","party2","office","candidate","precinct","precinct2","racetype")
                nmsxx <- c("county","precinct","office","district","party","candidate","votes",
                           "absentee","early_voting","election_day","mail","provisional","limited")
                xx <- read_fwf(file_txt, fwf_positions(start, end, nms), col_types = "cccccccccccccccc")
                xx$county <- str_to_title(county) # match standard
                xx$district <- ""
                xx$mail <- 0
                xx$limited <- 0
                xx <- xx[nmsxx]
                xvotes <- TRUE
            }
            else{
                gotxx <- FALSE
            }
        }
        #######################################################################
        # Check for all known csv, xlsx and xls formats
        #######################################################################
        else if (toupper(ext) %in% c(".CSV",".XLSX",".XLS")){
            dd <- def[toupper(def$counties) == toupper(county),]
            # if (toupper(county) == "BANDERA"){ # DEM and REP don't match
            #     if (party == "REP"){
            #         dd$early_voting[1] <- "Early Voting Votes"
            #         dd$election_day[1] <- "Election Day Voting Votes"
            #     }
            # }
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
                        vv <- read_excel(filename, sheet = nsheet, col_types = "text", skip = nskip)
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
                    #           "absentee","early_voting","election_day","mail","provisional","limited")
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
                    if (!is.na(dd$mail[1])){
                        xx$mail <- as.numeric(vv[[dd$mail[1]]])
                        xx$mail[is.na(xx$mail)] <- 0
                        xx$votes <- xx$votes + xx$mail
                        got_mail <- TRUE
                        xvotes <- TRUE
                    }
                    else{
                        xx$mail <- 0
                        got_mail <- FALSE
                    }
                    if (!is.na(dd$provisional_counted[1]) & valid_provisionals(county)){
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
                    if (!is.na(dd$limited[1])){
                        xx$limited <- as.numeric(vv[[dd$limited[1]]])
                        xx$limited[is.na(xx$limited)] <- 0
                        xx$votes <- xx$votes + xx$limited
                        got_limited <- TRUE
                        xvotes <- TRUE
                    }
                    else{
                        xx$limited <- 0
                        got_limited <- FALSE
                    }
                    if (!is.na(dd$votes[1])){
                        xx$votes <- vv[[dd$votes[1]]]
                        got_votes <- TRUE
                    }
                    gotxx <- TRUE
                }
                else if (!is.na(dd$desc2[1]) & dd$desc2[1] == "mtab_oc"){
                    col0 <- 3 #start column of 1st candidate
                    ncol <- 5 #columns per candidate
                    skip0 <- 2 #number of rows to skip to read candidates
                    tt <- read_excel(filename, sheet = nsheet, col_types = "text", skip = nskip)
                    yy <- NULL
                    if (toupper(county) == "DALLAS"){ #add limited?
                        vv <- read_excel(filename, sheet = "Registered Voters", col_types = "text",
                                         skip = 0)
                        xx <- data.frame(vv$Precinct)
                        names(xx)[1] <- "precinct"
                        xx$county <- str_to_title(county)
                        xx$office <- "Registered Voters"
                        xx$district <- ""
                        xx$party <- party
                        xx$candidate <- ""
                        xx$votes <- vv$`Registered Voters`
                        xx$absentee <- ""
                        xx$early_voting <- ""
                        xx$election_day <- ""
                        xx$mail <- ""
                        xx$provisional <- ""
                        nmsxx <- c("county","precinct","office","district","party","candidate","votes",
                                  "absentee","early_voting","election_day","mail","provisional")
                        yy <- xx[nmsxx]
                        
                        xx$office <- "Ballots Cast"
                        xx$district <- ""
                        xx$party <- party
                        xx$candidate <- ""
                        xx$votes <- vv$`Ballots Cast`
                        xx$absentee <- vv$`EV Mail`
                        xx$early_voting <- vv$`EV In-person`
                        xx$election_day <- vv$`Election Day`
                        xx$mail <- 0
                        xx$provisional <- vv$`PROV/EV/ED`
                        yy <- rbind(yy, xx)
                    }
                    for (i in 1:NROW(tt)){
                        if (tt$Contest[i] == "Registered Voters"){
                            next #do separately for both parties
                        }
                        roff <- read_excel(filename, sheet = tt$Page[i], col_types = "text",
                                           skip = (as.numeric(dd$office[1])-1), n_max = 1)
                        rcan <- read_excel(filename, sheet = tt$Page[i], col_types = "text",
                                           skip = (as.numeric(dd$candidate[1])-1), n_max = 1)
                        vv <- read_excel(filename, sheet = tt$Page[i], col_types = "text",
                                         skip = skip0)
                        zvv <<- vv #DEBUG-RM
                        precinct <- vv[,as.numeric(dd$precinct[1])]
                        j <- 3
                        while(names(vv)[j] != "Total"){ #no more candidates
                            xx <- data.frame(precinct)
                            names(xx)[1] <- "precinct"
                            xx$county <- str_to_title(county)
                            office1 <- names(roff)[1]
                            office1 <- gsub(" \\(Vote For \\d+\\)","",office1,ignore.case = TRUE)
                            xx$office <- office1
                            xx$district <- ""
                            xx$candidate <- names(rcan)[j]
                            xx$party[grepl("^DEM ",xx$candidate)] <- "DEM"
                            xx$party[grepl("^REP ",xx$candidate)] <- "REP"
                            xx$party[grepl("^LIB ",xx$candidate)] <- "LIB"
                            xx$party[grepl("^GRN ",xx$candidate)] <- "GRN"
                            if (toupper(county) == "TRAVIS" | toupper(county) == "TARRANT"){
                                file_party <- paste0(dir,"out/20221108__tx__general__dallas__precinct_party.csv")
                                pp <- read_csv(file_party)
                                k <- which(pp$candidate == names(rcan)[j])
                                if (length(k) == 1){
                                    print(paste0("=== FOUND ",names(rcan)[j]," is |",pp$party[k],"|"))
                                    xx$party <- pp$party[k]
                                }
                                else{
                                    print(paste0("*** COULD NOT FIND ",names(rcan)[j]))
                                }
                            }
                            #print(paste0("Candidate=",names(rcan)[j])) #DEBUG-RM
                            nmsxx <- c("county","precinct","office","district","party","candidate")
                            xx <- xx[nmsxx]
                            xvotes <- FALSE
                            ivotes        <- as.numeric(dd$votes[1])+j-1
                            iabsentee     <- as.numeric(dd$absentee[1])+j-1
                            iearly_voting <- as.numeric(dd$early_voting[1])+j-1
                            ielection_day <- as.numeric(dd$election_day[1])+j-1
                            imail         <- as.numeric(dd$mail[1])+j-1
                            iprovisional  <- as.numeric(dd$provisional_counted[1])+j-1
                            ilimited      <- as.numeric(dd$limited[1])+j-1
                            imax <- 0
                            xx$votes <- as.numeric(vv[[ivotes]])
                            if (!is.na(iabsentee)){
                                xx$absentee <- as.numeric(vv[[iabsentee]])
                                xx$absentee[is.na(xx$absentee)] <- 0
                                xx$votes <- xx$votes + xx$absentee
                                got_absentee <- TRUE
                                xvotes <- TRUE
                                if (imax < iabsentee) imax <- iabsentee
                            }
                            else{
                                xx$absentee <- 0
                                got_absentee <- FALSE
                            }
                            if (!is.na(iearly_voting)){
                                xx$early_voting <- as.numeric(vv[[iearly_voting]])
                                xx$early_voting[is.na(xx$early_voting)] <- 0
                                xx$votes <- xx$votes + xx$early_voting
                                got_early_voting <- TRUE
                                xvotes <- TRUE
                                if (imax < iearly_voting) imax <- iearly_voting
                            }
                            else{
                                xx$early_voting <- 0
                                got_early_voting <- FALSE
                            }
                            if (!is.na(ielection_day)){
                                xx$election_day <- as.numeric(vv[[ielection_day]])
                                xx$election_day[is.na(xx$election_day)] <- 0
                                xx$votes <- xx$votes + xx$election_day
                                got_election_day <- TRUE
                                xvotes <- TRUE
                                if (imax < ielection_day) imax <- ielection_day
                            }
                            else{
                                xx$election_day <- 0
                                got_election_day <- FALSE
                            }
                            if (!is.na(imail)){
                                xx$mail <- as.numeric(vv[[imail]])
                                xx$mail[is.na(xx$mail)] <- 0
                                xx$votes <- xx$votes + xx$mail
                                got_mail <- TRUE
                                xvotes <- TRUE
                                if (imax < imail) imax <- imail
                            }
                            else{
                                xx$mail <- 0
                                got_mail <- FALSE
                            }
                            if (!is.na(iprovisional) & valid_provisionals(county)){
                                xx$provisional <- as.numeric(vv[[iprovisional]])
                                xx$provisional[is.na(xx$provisional)] <- 0
                                xx$votes <- xx$votes + xx$provisional
                                got_provisional <- TRUE
                                xvotes <- TRUE
                                if (imax < iprovisional) imax <- iprovisional
                            }
                            else{
                                xx$provisional <- 0
                                got_provisional <- FALSE
                            }
                            if (!is.na(ilimited)){
                                xx$limited <- as.numeric(vv[[ilimited]])
                                xx$limited[is.na(xx$limited)] <- 0
                                xx$votes <- xx$votes + xx$limited
                                got_limited <- TRUE
                                xvotes <- TRUE
                                if (imax < ilimited) imax <- ilimited
                            }
                            else{
                                xx$limited <- 0
                                got_limited <- FALSE
                            }
                            if (!is.na(ivotes)){
                                xx$votes <- vv[[ivotes]]
                                got_votes <- TRUE
                                if (imax < ivotes) imax <- ivotes
                            }
                            gotxx <- TRUE
                            zdal <<- xx #DEBUG-RM
                            xx <- xx[xx$precinct != "Total:",]
                            if (is.null(yy)){
                                yy <- xx
                            }
                            else{
                                yy <- rbind(yy, xx)
                            }
                            j <- imax+1 #fix error with Tarrant County
                        }
                    }
                    zyy <- yy #DEBUG-RM
                    ztt <<- tt #DEBUG-RM
                    xx <- yy
                    gotxx <- TRUE
                }
                else if (!is.na(dd$desc2[1]) & dd$desc2[1] == "opc_hdr"){
                    if (toupper(ext) %in% c(".CSV",".XLSX",".XLS")){ # added XLSX for Dallas County
                        #xxparty <- read_delim(filenamex, ' ', col_names = FALSE, n_max = 1)
                        #hdr usually ordered by office, party, candidate
                        oskip <- as.numeric(dd$office[1]) + nskip - 1
                        pskip <- as.numeric(dd$party[1]) + nskip - 1
                        cskip <- as.numeric(dd$candidate[1]) + nskip - 1
                        if (toupper(ext) == ".CSV"){
                            ohdr <- read_csv(filename, col_names = FALSE, skip = oskip, n_max = 1)
                            phdr <- read_csv(filename, col_names = FALSE, skip = pskip, n_max = 1)
                            chdr <- read_csv(filename, col_names = FALSE, skip = cskip, n_max = 1)
                            vv <- read_csv(filename, col_types = "c", skip = (nskip+2))
                        }
                        else{
                            ohdr <- read_excel(filename, sheet = nsheet, col_names = FALSE, col_types = "text", skip = oskip)
                            phdr <- read_excel(filename, sheet = nsheet, col_names = FALSE, col_types = "text", skip = pskip)
                            chdr <- read_excel(filename, sheet = nsheet, col_names = FALSE, col_types = "text", skip = cskip)
                            vv <-   read_excel(filename, sheet = nsheet, col_names = TRUE,  col_types = "text", skip = (nskip+2))
                        }
                        col1 <- as.numeric(dd$votes[1])
                        office    <- as.character(ohdr[1,col1:NCOL(ohdr)])
                        party     <- as.character(phdr[1,col1:NCOL(phdr)])
                        candidate <- as.character(chdr[1,col1:NCOL(chdr)])
                        #candidate <- candidate[!is.na(candidate)]
                        xx <- data.frame(office,party,candidate,stringsAsFactors = FALSE)
                        xx$county <- county
                        xx$precinct <- NA
                        xx$district <- NA
                        xx$votes <- 0
                        xx <- xx[,c("county","precinct","office","district","party","candidate","votes")]
                        colname <- NULL
                        colindx <- NULL
                        xvotes <- FALSE
                        if (!is.na(dd$absentee[1])){
                            iabsentee <- as.numeric(dd$absentee[1])
                            xx$absentee <- 0
                            colname <- c(colname, "absentee")
                            colindx <- c(colindx, iabsentee)
                            xvotes <- TRUE
                        }
                        if (!is.na(dd$early_voting[1])){
                            iearly_voting <- as.numeric(dd$early_voting[1])
                            xx$early_voting <- 0
                            colname <- c(colname, "early_voting")
                            colindx <- c(colindx, iearly_voting)
                            xvotes <- TRUE
                        }
                        if (!is.na(dd$election_day[1])){
                            ielection_day <- as.numeric(dd$election_day[1])
                            xx$election_day <- 0
                            colname <- c(colname, "election_day")
                            colindx <- c(colindx, ielection_day)
                            xvotes <- TRUE
                        }
                        if (!is.na(dd$mail[1])){
                            imail <- as.numeric(dd$mail[1])
                            xx$mail <- 0
                            colname <- c(colname, "mail")
                            colindx <- c(colindx, imail)
                            xvotes <- TRUE
                        }
                        if (!is.na(dd$provisional_counted[1]) & valid_provisionals(county)){
                            iprovisional <- as.numeric(dd$provisional_counted[1])
                            xx$provisional <- 0
                            colname <- c(colname, "provisional")
                            colindx <- c(colindx, iprovisional)
                            xvotes <- TRUE
                        }
                        if (!is.na(dd$limited[1])){
                            ilimited <- as.numeric(dd$limited[1])
                            xx$limited <- 0
                            colname <- c(colname, "limited")
                            colindx <- c(colindx, ilimited)
                            xvotes <- TRUE
                        }
                        j <- 1
                        last_precinct <- ""
                        iprecinct <- dd$precinct[1]
                        yy <- NULL
                        vv <- vv[vv[,as.numeric(iprecinct)] != "COUNTY TOTALS",]
                        vv <- vv[!is.na(vv[,as.numeric(iprecinct)]),] # delete trailing empty lines for Cooke County
                        #print(paste0("NROW(vv)=",NROW(vv))) #DEBUG-RM
                        for (i in 1:NROW(vv)){
                            precinct <- vv[i, as.numeric(iprecinct)]
                            #print(paste0("i|precinct=",i,"|",precinct,"|")) #DEBUG-RM
                            if (last_precinct != precinct){
                                j <- 1
                                if (i > 1){
                                    xx$precinct <- as.character(last_precinct)
                                    if (is.null(yy)){
                                        yy <- xx
                                    }
                                    else{
                                        yy <- rbind(yy,xx)
                                    }
                                    xx$votes <- 0
                                }
                                last_precinct <- precinct
                            }
                            #xx$precinct <- precinct
                            voteinfo <- as.character(vv[i,col1:NCOL(vv)])
                            xx[[colname[which(colindx == j)]]] <- voteinfo
                            xx$votes <- xx$votes + as.numeric(voteinfo)
                            j <- j+1
                        }
                        xx$precinct <- as.character(last_precinct)
                        yy <- rbind(yy,xx)
                    }
                    print(paste0("PROCESSED ",NROW(vv)," ROWS")) #DEBUG
                    print(paste0("PROC TIME=",Sys.time()))
                    # else{
                    #     vv <- read_excel(filename, sheet = nsheet, skip = nskip)
                    # }
                    # Additional logic here
                    yy <- yy[!is.na(yy$votes),]
                    if (toupper(county) == "DALLAS"){ # do this for all opc_hdr counties?
                        yy <- yy[yy$votes != 0,]
                    }
                    zyy <<- yy #DEBUG-RM
                    xx <- yy
                    gotxx <- TRUE
                } 
                else{
                    print("Cannot parse unknown format") #DEBUG-RM
                    gotxx <- FALSE
                }
                if (gotxx){
                    xx <- xx[!is.na(xx$office),] # remove blank lines for Austin County
                    zdd <<- dd #DEBUG-RM
                    zxx <<- xx #DEBUG-RM
                }
            }
            else{
                gotxx <- FALSE
            }
        }
        else{
            #print(paste0("SKIP ",f))
            gotxx <- FALSE
        }
        if (gotxx){
            gxx1 <<- xx #DEBUG-RM
            file_csv <- paste0(dir,"out/",f)
            file_csv <- gsub(ext,".csv",file_csv)
            f_std <- paste0("20221108__tx__general__",tolower(county0),"__precinct.csv")
            file_std <- paste0(dir,"out/",f_std)
            # Changes to match standard
            xx$precinct <- gsub("^Precinct [0]*","",xx$precinct, ignore.case = TRUE)
            if (toupper(county) == "COLLIN"){
                xx$precinct <- gsub("^PCT [0]*","",xx$precinct, ignore.case = TRUE)
            }
            #xx$precinct <- gsub("^PCT ","",xx$precinct, ignore.case = TRUE) # Wharton County
            xx$party[xx$party == "(D)"] <- "DEM" # El Paso County
            xx$party[xx$party == "(R)"] <- "REP" # El Paso County
            xx$party[xx$party == "(G)"] <- "GRN" # El Paso County
            xx$party[xx$party == "(I)"] <- "IND" # El Paso County
            xx$party[xx$party == "(L)"] <- "LIB" # El Paso County
            xx$party[grepl("^Democratic",xx$party, ignore.case = TRUE)] <- "DEM" #Brazos County
            xx$party[grepl("^Republican",xx$party, ignore.case = TRUE)] <- "REP" #Brazos County
            xx$candidate <- str_squish(xx$candidate) # change all multiple spaces to a single space - Ellis County
            xx$office <- str_squish(xx$office) # change all multiple spaces to a single space
            xx$office <- str_to_title(xx$office)
            xx$office[xx$office == "Registered Voters - Total"] <- "Registered Voters"
            xx$candidate[grepl("^REGISTERED VOTERS",xx$candidate,ignore.case = TRUE)] <- ""
            xx$county <- str_to_title(xx$county) #Cooke County
            
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
            xx$party[grepl("^Lib ",xx$office, ignore.case = TRUE)] <- "LIB" # Cooke County
            xx$party[grepl("^Grn ",xx$office, ignore.case = TRUE)] <- "GRN" # Cooke County
            xx$party[grepl("^DEM ",xx$candidate, ignore.case = TRUE)] <- "DEM" # Dallas County
            xx$party[grepl("^REP ",xx$candidate, ignore.case = TRUE)] <- "REP" # Dallas County
            xx$party[grepl("^GRN ",xx$candidate, ignore.case = TRUE)] <- "GRN" # Dallas County
            xx$party[grepl("^IND ",xx$candidate, ignore.case = TRUE)] <- "IND" # Dallas County
            xx$party[grepl("^LIB ",xx$candidate, ignore.case = TRUE)] <- "LIB" # Dallas County
            xx$office <- gsub(" \\(R\\)$","",xx$office, ignore.case = TRUE) # Hays County
            xx$office <- gsub(" \\(D\\)$","",xx$office, ignore.case = TRUE) # Hays County
            xx$office <- gsub("^\\(R\\) ","",xx$office, ignore.case = TRUE) # El Paso County
            xx$office <- gsub("^\\(D\\) ","",xx$office, ignore.case = TRUE) # El Paso County
            xx$office <- gsub("^Rep\\.? ","",xx$office, ignore.case = TRUE)
            xx$office <- gsub("^Dem\\.? ","",xx$office, ignore.case = TRUE)
            xx$office <- gsub("^Lib\\.? ","",xx$office, ignore.case = TRUE) # Cooke County
            xx$office <- gsub("^Grn\\.? ","",xx$office, ignore.case = TRUE) # Cooke County
            xx$office <- gsub("^Rep ","",xx$office, ignore.case = TRUE) # delete double Rep
            xx$office <- gsub("^Dem ","",xx$office, ignore.case = TRUE) # delete double Dem
            xx$office <- gsub(" Of "," of ",xx$office)
            xx$office <- gsub(" At "," at ",xx$office)
            xx$office <- gsub("-At-","-at-",xx$office) # Austin County
            xx$office <- gsub(" The "," the ",xx$office) # Clay County
            xx$office <- gsub(" And "," and ",xx$office) # Goliad County
            xx$office <- gsub("^Jop ","JOP ",xx$office) # Donley County
            xx$office <- gsub("State Boe","State BoE",xx$office)
            xx$office <- gsub("President / Vice-President","President",xx$office) # Rusk County
            xx$office <- gsub("State Senator","State Senate",xx$office) # Clay County
            xx$office <- gsub("State Representative","State House",xx$office) # Callahan County
            xx$office <- gsub("State Rep\\.?","State House",xx$office) # Dallas County
            xx$office <- gsub("^U\\.? ?s\\.? Senator","U.S. Senate",xx$office, ignore.case = TRUE) # Rusk County
            xx$office <- gsub("^U\\.? ?s\\.? Representative","U.S. House",xx$office, ignore.case = TRUE) # Brazos County
            xx$office <- gsub("^U\\.? ?s\\.? Rep,","U.S. House,",xx$office, ignore.case = TRUE) # Goliad County
            xx$office <- gsub("^United States Representative","U.S. House",xx$office, ignore.case = TRUE) # Guadalupe County
            xx$office <- gsub("^U\\.s\\. Congressional","U.S. House",xx$office, ignore.case = TRUE) # Dallas County
            xx$candidate <- gsub("^DEM ","",xx$candidate, ignore.case = TRUE) # Rusk County
            xx$candidate <- gsub("^REP ","",xx$candidate, ignore.case = TRUE) # Rusk County
            xx$candidate <- gsub("^LIB ","",xx$candidate, ignore.case = TRUE) # Rusk County
            xx$candidate <- gsub("^GRN ","",xx$candidate, ignore.case = TRUE) # Rusk County
            xx$candidate <- gsub("^\\(D\\)","",xx$candidate, ignore.case = TRUE) # El Paso County
            xx$candidate <- gsub("^\\(R\\)","",xx$candidate, ignore.case = TRUE) # El Paso County
            xx$candidate <- gsub("^\\(G\\)","",xx$candidate, ignore.case = TRUE) # El Paso County
            xx$candidate <- gsub("^\\(I\\)","",xx$candidate, ignore.case = TRUE) # El Paso County
            xx$candidate <- gsub("^\\(L\\)","",xx$candidate, ignore.case = TRUE) # El Paso County
            
            for (i in 1:NROW(xx)){
                mm <- str_match(xx$office[i], "U.S. House\\,? Dist\\.?(?:rict)?(?: No.)? (\\d+)")
                if(!is.na(mm[1,1])){
                    xx$district[i] <- mm[1,2]
                    xx$office[i] <- "U.S. House"
                    next
                }
                mm <- str_match(xx$office[i],"Us Rep(?: \\d+ Us)\\,? Dist\\.?(?:rict)?(?: No.)? (\\d+)")
                if(!is.na(mm[1,1])){
                    xx$district[i] <- mm[1,2]
                    xx$office[i] <- "U.S. House"
                    next
                }
                mm <- str_match(xx$office[i], "State Senate\\,? Dist\\.?(?:rict)?(?: No.)? (\\d+)")
                if(!is.na(mm[1,1])){
                    xx$district[i] <- mm[1,2]
                    xx$office[i] <- "State Senate"
                    next
                }
                #mm <- str_match(xx$office[i], "State Representative\\,? Dist\\.?(?:rict)?(?: No.)? (\\d+)")
                mm <- str_match(xx$office[i], "State House\\,? Dist\\.?(?:rict)?(?: No.)? (\\d+)") # Callahan County dbl-space
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
                xx$mail         <- as.numeric(xx$mail)
                xx$provisional  <- as.numeric(xx$provisional)
                xx$limited      <- as.numeric(xx$limited)
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
                        nonzero <- (xx$votes[i] != 0 | xx$absentee[i] != 0 | xx$early_voting[i] != 0 | xx$election_day[i] != 0 | xx$mail[i] != 0 | xx$provisional[i] != 0 | xx$limited[i] != 0)
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
                            nonzero <- (xx$votes[i] != 0 | xx$absentee[i] != 0 | xx$early_voting[i] != 0 | xx$election_day[i] != 0 | xx$mail[i] != 0 | xx$provisional[i] != 0 | xx$limited[i] != 0)
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
                if (sumprov == 0 | valid_provisionals(county) == FALSE){
                    xx <- xx[-iprov]
                }
                # delete absentee if their sum = 0
                iabsent <- which(names(xx) == "absentee")
                sumabsent <- sum(xx$absentee, na.rm = TRUE)
                if (sumabsent == 0){
                    xx <- xx[-iabsent]
                }
                # delete mail if their sum = 0
                imail <- which(names(xx) == "mail")
                summail <- sum(xx$mail, na.rm = TRUE)
                if (summail == 0){
                    xx <- xx[-imail]
                }
                # delete limited if their sum = 0
                ilimited <- which(names(xx) == "limited")
                sumlimited <- sum(xx$limited, na.rm = TRUE)
                if (sumlimited == 0){
                    xx <- xx[-ilimited]
                }
                if (toupper(county) == "CRANE"){
                    ielection_day <- which(names(xx) == "election_day")
                    sumelection_day <- sum(xx$election_day, na.rm = TRUE)
                    if (sumelection_day == 0){
                        xx <- xx[-ielection_day]
                        iearly_voting <- which(names(xx) == "early_voting") # Crane County
                        xx <- xx[-iearly_voting]
                    }
                }
            }
            # fix missing precincts if surrounded by same precinct - Austin County
            ipna <- which(is.na(xx$precinct))
            lpna <- length(ipna)
            if (lpna > 0){
                zipna <<- ipna #DEBUG
                zlpna <<- lpna #DEBUG
                for (i in 1:lpna){
                    if (ipna[i] > 1 & ipna[i] < NROW(xx)){
                        if (xx$precinct[ipna[i]-1] == xx$precinct[ipna[i]+1]){
                            xx$precinct[ipna[i]] <- xx$precinct[ipna[i]-1]
                        }
                    }
                }
            }
            if (toupper(county) == "CAMERON"){ # fixes to match current file
                xx$party[grepl("^Ballots Cast - Blank$",xx$office)] <- party
                xx <- xx[xx$office != "Ballots Cast" | xx$party != "",] # exclude if no party
                xx <- xx[xx$office != "Registered Voters" | party != "DEM",] # include only in REP file
            }
            else if (toupper(county) == "COLEMAN"){ # fixes to match current file
                xx <- xx[xx$office != "Ballots Cast - Blank",]
                xx <- xx[xx$office != "Registered Voters" | party != "REP",] # include only in DEM file
            }
            else if (toupper(county) == "ELLIS"){ # fixes to match current file
                xx <- xx[xx$office != "Registered Voters - Democratic Party",] # exclude DEM registered voters
                xx$party[xx$office == "Registered Voters - Republican Party"] <- "" 
                xx$office[xx$office == "Registered Voters - Republican Party"] <- "Registered Voters" 
            }
            else if (toupper(county) == "RUSK"){ # fixes to match current file
                #exclude local races
                xx <- xx[!grepl("^Constable ", xx$office),] #exclude local Constable races
                xx <- xx[!grepl("^City Council, ", xx$office),]
                xx <- xx[!grepl("^Local Option City of ", xx$office),]
                xx <- xx[!grepl("^Mayor ", xx$office),]
                xx <- xx[!grepl("^Alderman, ", xx$office),]
                xx <- xx[!grepl("^Trustee\\,? ", xx$office),]
                xx <- xx[!grepl("^School Board, ", xx$office),]
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
                else if (toupper(county) == "BANDERA"){
                    cols <- c("county","party","precinct","office","district","candidate",
                              "early_voting","election_day","votes")
                    xx <- xx[,cols]
                    xx$office <- gsub("State House","State Representative",xx$office)
                }
                else if (toupper(county) == "CALHOUN"){
                    #xx$precinct <- lapply(xx$precinct[], function(x) paste('Precinct ', x))
                    xx$precinct <- gsub("^","Precinct ",xx$precinct)
                    xx$office <- gsub("State House","State Representative",xx$office)
                    xx$office <- gsub("State Senate","State Senator",xx$office)
                    xx$office <- gsub("Crim Dist Attorney, Calhoun County","REP Crim Dist Attorney, Calhoun County",xx$office) # add REP
                }
                else if (toupper(county) == "CAMERON"){
                    #xx$precinct <- lapply(xx$precinct[], function(x) paste('Precinct ', x))
                    xx$precinct <- gsub("^","Precinct ",xx$precinct)
                    xx$office <- gsub("State House","State Representative",xx$office)
                    xx$office <- gsub("Ballots Cast - Blank","BALLOTS CAST - BLANK",xx$office)
                    
                }
                else if (toupper(county) == "CARSON"){
                    xx$precinct <- gsub("^","Precinct ",xx$precinct)
                    xx$office <- gsub("State House","State Representative",xx$office)
                }
                else if (toupper(county) == "CLAY"){
                    xx$precinct <- gsub("^","Precinct ",xx$precinct)
                    xx$office <- gsub("State House","State Representative",xx$office)
                    xx$office <- gsub("Ballots Cast - Blank","BALLOTS CAST - BLANK",xx$office)
                }
                else if (toupper(county) == "COLEMAN"){
                    xx$precinct <- gsub("^","Precinct ",xx$precinct)
                    xx$office <- gsub("State House","State Representative",xx$office)
                    #xx$office <- gsub("Ballots Cast - Blank","BALLOTS CAST - BLANK",xx$office)
                }
                else if (toupper(county) == "ELLIS"){
                    xx$office <- gsub("State House","State Representative",xx$office)
                }
                else if (toupper(county) == "RUSK"){
                    xx <- xx[c("county","precinct","office","district","party","candidate",
                               "votes","election_day","early_voting","absentee")]
                    xx$office <- gsub("Ballots Cast - Blank","BALLOTS CAST - BLANK",xx$office)
                    xx$office <- gsub("State House","State Representative",xx$office)
                    xx$candidate <- gsub("Michael R. Pence","Michael R. Penc",xx$candidate)
                    xx$candidate <- gsub("Kamala D. Harris","Kamala D. Harri",xx$candidate)
                    xx$candidate <- gsub(" Cohe"," Coh",xx$candidate)
                    xx$candidate <- gsub("Mary \"MJ\" Hegar","DEM Mary \"MJ\" Hegar",xx$candidate)
                }
            }
            #write_csv(xx, file_csv)
            write_csv(xx, file_std)
            print(paste0(" AFTER write ", file_std))
            # Write DEM.txt to DEM.csv and REP.txt to REP.csv and write both to [file_std].csv.
            # This is required for final step which is currently done manually. If the DEM.csv
            # and REP.csv are identical, then [file_std].csv should contain the final file.
            # If they are different, diff the DEM.csv and REP.csv files and add that part of
            # the DEM.csv not duplicated in the REP.csv to the end of [file_std].csv. This
            # should include only one header (on the first line) and should be the final file.
            if (toupper(county0) == "DALLAS"){
                tt <- table(xx$candidate,xx$part)
                dd <- as.data.frame(tt)
                dd <- dd[dd$Freq > 0,]
                names(dd) <- c("candidate","party","count")
                unique_candidates <- length(unique(dd$candidate))
                nrows_candidates <- NROW(dd)
                if (unique_candidates == nrows_candidates){
                    print(paste0("===== unique_candidates == nrows_candidates: ",unique_candidates," == ",nrows_candidates))
                }
                else{
                    print(paste0("***** unique_candidates <> nrows_candidates: ",unique_candidates," <> ",nrows_candidates))
                }
                file_party <- gsub(".csv","_party.csv",file_std)
                write_csv(dd, file_party)
            }
        }
        print(paste0("STOP TIME=",Sys.time()))
    }
}
