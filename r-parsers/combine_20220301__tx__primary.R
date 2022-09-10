library(tidyverse)

getElectionfile <- function(enames, outfile){
    #efiles <- cfiles[as.character(cfiles$elections) == input$xelection,]
    reqcols <- c("county","precinct","office","district","party","candidate","votes")
    curcols <- reqcols
    optcols <- NULL
    #enames <- efiles$filenames
    yy <- NULL
    for (ename in enames){
        print(paste0("BEFORE read_csv(",ename,")")) #DEBUG-RM
        filepath <- paste0(indir,ename)
        xx0 <- read_csv(filepath)
        cols0 <- names(xx0)
        xx <- xx0[,reqcols]
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
election <- "20220301__tx__primary"
epattern <- paste0(election,"__[A-Za-z_]+__precinct.csv")
indir <- "2022\\counties\\"
outfile <- paste0("2022\\",election,"__precinct.csv")
list <- list.files(indir, pattern = epattern, full.names = FALSE)
len <- length(list)
print(epattern)
print(paste0("len=",len))
print(list)
getElectionfile(unlist(list), outfile)
