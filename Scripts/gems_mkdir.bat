@echo off
REM Makes an empty directory tree in preparation for submission 
REM of GeMS files to NGMDB
REM Arguments are 
REM		1. path to parent folder
REM 	2. name of submission (see 'File structure and naming conventions'
REM 		in GeMS submittal requirements document 
REM 	3. should a basedata folder be created? Use 'y' or 'n'

set argC=0
for %%x in (%*) do Set /A argC+=1
echo %argC%

if not %argC%==3 (
	echo Makes an empty directory tree in preparation for submission of GeMS files to NGMDB
	echo Provide three arguments:
	echo 	1. path to parent folder
	echo 	2. ST_YYYY_AREA_VER name of submission 
	echo 	3. should a BASEDATA folder be created? Use 'y' or 'n'.
	exit /b
	)

set parent=%~1
set fullname=%~2
set basedata=%3
	
REM top-level submittal folder and fullname child folder
mkdir "%parent%/%fullname%-submittal/%fullname%

REM database folder
mkdir "%parent%/%fullname%-submittal/%fullname%/%fullname%-database
mkdir "%parent%/%fullname%-submittal/%fullname%/%fullname%-database/resources

REM Include a basedata folder?
if "%basedata%"=="y" 
	mkdir "%parent%/%fullname%-submittal/%fullname%/%fullname%-database/basedata
	mkdir "%parent%/%fullname%-submittal/%fullname%/%fullname%-database/basedata/resources
	)