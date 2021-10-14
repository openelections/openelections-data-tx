[![Build Status](https://github.com/openelections/openelections-data-tx/actions/workflows/data_tests.yml/badge.svg?branch=master)](https://github.com/openelections/openelections-data-tx/actions/workflows/data_tests.yml?query=branch%3Amaster)
[![Build Status](https://github.com/openelections/openelections-data-tx/actions/workflows/format_tests.yml/badge.svg?branch=master)](https://github.com/openelections/openelections-data-tx/actions/workflows/format_tests.yml?query=branch%3Amaster)

OpenElections Data TX
=====================

Pre-processed election results for Texas. These CSV files are converted from [original source files](https://github.com/openelections/openelections-sources-tx) from individual counties. You can refer to the below table for overall progress. Elections marked as `done` have all counties completed for that level. Those marked as `working` mean that at least one volunteer is working on this election, and this could be a good place to start if you're new. `Not started` means that this election is wide open and could use a volunteer.

## Precinct Results

| year  | general  | primary  |
|---|---|---|
| 2020  | [done](https://github.com/openelections/openelections-data-tx/blob/master/2020/20201103__tx__general__precinct.csv)  | [done](https://github.com/openelections/openelections-data-tx/blob/master/2020/20200303__tx__primary__precinct.csv) |
| 2018  | [done](https://github.com/openelections/openelections-data-tx/blob/master/2018/20181106__tx__general__precinct.csv) | [working](https://github.com/openelections/openelections-data-tx/issues/123)
| 2016  | [done](https://github.com/openelections/openelections-data-tx/blob/master/2016/20161108__tx__general__precinct.csv) |  [working](https://github.com/openelections/openelections-data-tx/issues/12) |
| 2014 |  [working](https://github.com/openelections/openelections-data-tx/issues/11) | [working](https://github.com/openelections/openelections-data-tx/issues/111)  |
| 2012  |   [working](https://github.com/openelections/openelections-data-tx/issues/285) | not started |
| 2010  |  not started | not started |
| 2008  |  not started | not started |

## County Results

Complete for elections from 2000 through 2018 general.

To contribute, email openelections@gmail.com or [find us on Twitter](https://twitter.com/openelex) and let us know what counties/elections you'd like to work on. You also can leave a comment on one of the [issues](https://github.com/openelections/openelections-data-tx/issues) in this repository. Volunteers can do as much or as little as they like - one county or all 254.

## Results Notes

* Sherman County 2018 primary results include three early voting columns: `early_voting`, `early_voting_os` and `early_voting_ts`. The last two refer to specific models of voting machines.
