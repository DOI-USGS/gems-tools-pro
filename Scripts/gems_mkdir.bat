REM Makes an empty directory tree in preparation for submission 
REM of GeMS files to NGMDB
REM Arguments are 
REM 	1. name of submission (see 'File structure and naming conventions'
REM 	in GeMS submittal requirements document 
REM 	2. should a basedata folder be created? Can be any value; yes, true, 1, a, etc.
echo off

mkdir "%1\%2"
mkdir "%1\%2\%2-publication"
mkdir "%1\%2\%2-publication\%2-database"
mkdir "%1\%2\%2-publication\%2-database\resources"
mkdir "%1\%2\%2-publication\%2-database\shapefile-version"
mkdir "%1\%2\%2-publication\%2-database\shapefile-version\%2-open"

if not "%3"=="" (
	mkdir "%1\%2\%2-publication\%2-database\%2-basedata"
	mkdir "%1\%2\%2-publication\%2-database\%2-basedata\resources"
	)
