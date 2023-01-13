library(tidyverse)

catfile <- function(ff,msg){
    line <- paste0(msg,"\n")
    cat(file = ff, append = TRUE, line)
    cat(file = stderr(), line)
}
getElectionfile <- function(enames, outfile, ff){
    #efiles <- cfiles[as.character(cfiles$elections) == input$xelection,]
    reqcols <- c("county","precinct","office","district","party","candidate","votes")
    curcols <- reqcols
    optcols <- NULL
    #enames <- efiles$filenames
    yy <- NULL
    for (ename in enames){
        catfile(ff, paste0("BEFORE read_csv(",ename,")")) #DEBUG
        filepath <- paste0(indir,ename)
        xx0 <- NULL
        xx  <- NULL
        cols0 <- NULL
        result = tryCatch({
            xx0 <- read_csv(filepath)
            cols0 <- names(xx0)
            xx <- xx0[,reqcols]
        }, warning = function(w) {
            status <<- "WARNING"
            catfile(ff,paste0("WARNING in getElectionfile(",outfile,"): ",w))
        }, error = function(e) {
            status <<- "ERROR"
            catfile(ff,paste0("ERROR in getElectionfile(",outfile,"): ",e))
        }, finally = {
            #cleanup-code
        })
        if (is.null(xx)){
            catfile(ff,paste0("SKIP ",ename))
            next
        }
        for (col in reqcols){
            if (!(col %in% names(xx))){
                catfile(ff,paste0("MISSING ",col,", SKIP ",ename))
                next
            }
        }
        for (col in optcols){
            xx[[col]] <- ""
        }
        for (col in cols0){
            if (col %in% curcols){
                if (!(col %in% reqcols)){ # in optcols
                    xx[[col]] <- xx0[[col]]
                }
            }
            else{
                curcols <- c(curcols,col)
                optcols <- c(optcols,col)
                xx[[col]] <- xx0[[col]]
                if (!is.null(yy)){
                    yy[[col]] <- ""
                }
            }
        }
        if (is.null(yy)){
            yy <- xx
        }
        else{
            yy <- rbind(yy, xx)
        }
    }
    zcurcols <<- curcols #DEBUG-RM
    zzall <<- yy #DEBUG-RM
    write_csv(yy, outfile)
}
#BEGIN MODIFY
election_year  <- "2022"
election_date  <- "20221108"
election_state <- "tx"
election_type  <- "general"
election_area  <- "precinct"
#END MODIFY
election <- paste0(election_date,"__",election_state,"__",election_type)
epattern <- paste0(election,"__[A-Za-z_]+__",election_area,".csv")
indir   <- paste0(election_year,"\\counties\\")
outfile <- paste0(election_year,"\\",election,"__",election_area,".csv")
ff      <- paste0(election_year,"\\",election,"__",election_area,".txt")
list <- list.files(indir, pattern = epattern, full.names = FALSE)
len <- length(list)
catfile(ff,epattern)
catfile(ff,paste0("len=",len))
# list <- c("20201103__tx__general__andrews__precinct.csv",
#           "20201103__tx__general__brown__precinct.csv") #create test file
# list <- c("20201103__tx__general__andrews__precinct.csv",
#           "20201103__tx__general__maverick__precinct.csv") #create test file
catfile(ff,list)
getElectionfile(unlist(list), outfile, ff)
catfile(ff,paste0("len=",len))
