library(tidyverse)

state2s = c("AK","AL","AR","AZ","CA","CO","CT","DC","DE","FL",
            "GA","HI","IA","ID","IL","IN","KS","KY","LA","MA",
            "MD","ME","MI","MN","MO","MS","MT","NC","ND","NE",
            "NH","NJ","NM","NV","NY","OH","OK","OR","PA","RI",
            "SC","SD","TN","TX","UT","VA","VT","WA","WI","WV","WY")
state2f <- c("Alaska","Alabama","Arkansas","Arizona","California",
            "Colorado","Connecticut","District of Columbia","Delaware","Florida",
            "Georgia","Hawaii","Iowa","Idaho","Illinois",
            "Indiana","Kansas","Kentucky","Louisiana","Massachusetts",
            "Maryland","Maine","Michigan","Minnesota","Missouri",
            "Mississippi","Montana","North Carolina","North Dakota","Nebraska",
            "New Hampshire","New Jersey","New Mexico","Nevada","New York",
            "Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island",
            "South Carolina","South Dakota","Tennessee","Texas","Utah",
            "Virginia","Vermont","Washington","Wisconsin","West Virginia",
            "Wyoming")
states <- ""
election_date <- "20201103"
election_year <- substring(election_date,1,4)
election_type <- "general"
fileout <- "check_states"
status <- "OK"

catfile <- function(ff,msg){
    line <- paste0(msg,"\n")
    cat(file = ff, append = TRUE, line)
    cat(file = stderr(), line)
}
check_state <- function(state2){
    ff <- paste0(fileout,"_",election_date,"_",election_type,".txt")
    if (toupper(state2) == "WI"){
        areaname <- "ward"
    }
    else{
        areaname <- "precinct"
    }
    filename   <- paste0(election_date,"__",tolower(state2),"__",election_type,"__",areaname,".csv")
    xelection2 <- paste0(election_date,"__",tolower(state2),"__",election_type)
    filepath <- paste0("https://raw.githubusercontent.com/openelections/openelections-data-",
                       tolower(state2),"/master/",election_year,"/",filename)
    catfile(ff,paste0("########## START check_state(",state2,"), filename=",filename))
    if (exists("xx")) rm(xx)
    status <<- "OK"
    result = tryCatch({
        xx <- read_csv(filepath)
    }, warning = function(w) {
        status <<- "WARNING"
        catfile(ff,paste0("WARNING in check_state(",state2,"): ",w))
    }, error = function(e) {
        status <<- "ERROR"
        catfile(ff,paste0("ERROR in check_state(",state2,"): ",e))
    }, finally = {
        #cleanup-code
    })
    if (status == "WARNING"){ #try again but ignore warnings
        result = tryCatch({
            xx <- read_csv(filepath)
        }, error = function(e) {
            status <- "ERROR"
            catfile(ff,paste0("ERROR in check_state(",state2,"): ",e))
        }, finally = {
            #cleanup-code
        })
    }
    if (exists("xx")){
        if (toupper(state2) == "WI"){
            names(xx)[names(xx) == "ward"] <- "precinct"
        }
        reqcols <- c("county","precinct","office","district","party","candidate","votes")
        for (col in reqcols){
            if (!(col %in% names(xx))){
                catfile(ff,paste0("ERROR: MISSING COLUMN ",col," in ",filename))
            }
        }
        ucounties <- unique(xx$county)
        vcounties <- toupper(get_counties(state2))
        zvcounties <<- vcounties
        for (cc in ucounties){
            if (!(toupper(cc) %in% vcounties)){
                catfile(ff,paste0("ERROR: INVALID COUNTY=|",cc,"|"))
            }
            yy <- xx[xx$county == cc,]
            nna <- sum(is.na(yy$precinct))
            if (nna > 0){
                catfile(ff,paste0("  ",nna," of ",NROW(yy)," precints are NA in ",xelection2,", county ",cc))
            }
        }
    }
    else{
        #catfile(ff,paste0("=========> Unable to parse ",filename))
    }
}
check_all_states <- function(){
    for (ss in state2s){
        check_state(ss)
    }
}
get_counties <- function(state2){
    # Use PopulationEstimates.csv to get county names
    filename <- "PopulationEstimates.csv"
    us <- read_csv(filename, skip = 4)
    names(us) <- c("FIPS","State","Area","Rucode","Pop90","Pop00","Pop10","Pop20","Pop21")
    statei <- which(state2s == state2)
    tx <- us[us$State == state2 & us$Area != state2f[statei],]
    counties <- tx$Area
    counties <- gsub(" County","",counties)
    return(counties)
}
for (ss in states){
    if (ss == ""){
        check_all_states()
    }
    else{
        check_state(ss)
    }
}

