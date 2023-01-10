REM Makes an empty directory tree in preparation for submission 
REM of GeMS files to NGMDB
REM Arguments are 
REM 	1. name of submission (see 'File structure and naming conventions'
REM 	in GeMS submittal requirements document 
REM 	2. should a basedata folder be created? Can be any value; yes, true, 1, a, etc.
echo off
mkdir %1%
mkdir "%1/%1-publication"
mkdir "%1/%1-publication/%1-database"
mkdir "%1/%1-publication/%1-database/resources"
mkdir "%1/%1-publication/%1-database/shapefile-version"
mkdir "%1/%1-publication/%1-database/shapefile-version/%1-open"

if not "%2"=="" (
	mkdir "%1/%1-publication/%1-database/%1-basedata"
	mkdir "%1/%1-publication/%1-database/%1-basedata/resources"
	)
