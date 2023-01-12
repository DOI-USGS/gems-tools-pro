@echo off
REM Makes an empty directory tree in preparation for submission 
REM of GeMS files to NGMDB
REM Arguments are 
REM		1. path to parent folder
REM 	2. name of submission (see 'File structure and naming conventions'
REM 		in GeMS Submittal requirements document 
REM		3. abbreviated name 
REM 	4. should a basedata folder be created? Can be any value; yes, true, 1, a, etc.

set argC=0
for %%x in (%*) do Set /A argC+=1
rem echo %argC%

if not %argC%==4 (
	echo Makes an empty directory tree in preparation for submission of GeMS files to NGMDB
	echo Provide four arguments:
	echo 	1. path to parent folder
	echo 	2. ST_YYYY_AREA_VER name of submission 
	echo 	3. abbreviated name for use in the case of long paths
	echo 	4. should a BASEDATA folder be created; yes or no
	goto end
	)
	
set parent=%1
set fullname=%2
set abbname=%3
set basedata=%4
	
REM top-level submittal folder and fullname child folder
mkdir "%parent%/%fullname%-Submittal/%fullname%"

REM check the length of a path using the fullname
REM if too long, use the abbreviated name
set temppath="%parent%/%fullname%-Submittal/%fullname%/%fullname%-Pub"
call :strlen result %temppath%
if %result% LSS 200 (
	set abbname=%fullname%
	)

REM publication folder
mkdir "%parent%/%fullname%-Submittal/%fullname%/%abbname%-Pub"

REM database folder
mkdir "%parent%/%fullname%-Submittal/%fullname%/%abbname%-Pub/%abbname%-DB"
mkdir "%parent%/%fullname%-Submittal/%fullname%/%abbname%-Pub/%abbname%-DB/Resources"

REM Include a basedata folder?
if not "%basedata%"=="" (
	mkdir "%parent%/%fullname%-Submittal/%fullname%/%abbname%-Pub/%abbname%-DB/Basedata"
	mkdir "%parent%/%fullname%-Submittal/%fullname%/%abbname%-Pub/%abbname%-DB/Basedata/Resources"
	
REM shapefile folder
mkdir "%parent%/%fullname%-Submittal/%fullname%/%abbname%-Pub/%abbname%-SHP"

REM ********* function *****************************
:strlen <resultVar> <stringVar>
echo off
(
    setlocal EnableDelayedExpansion
    (set^ tmp=!%~2!)
    if defined tmp (
        set "len=1"
        for %%P in (4096 2048 1024 512 256 128 64 32 16 8 4 2 1) do (
            if "!tmp:~%%P,1!" NEQ "" ( 
                set /a "len+=%%P"
                set "tmp=!tmp:~%%P!"
            )
        )
    ) ELSE (
        set len=0
    )
)
( 
    endlocal
    set "%~1=%len%"
    exit /b
)

:end