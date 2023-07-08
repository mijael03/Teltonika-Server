GPS_Teltonika_Server
====================

Server for GPS trackers Teltonika FMB920

Actually this script writes logs in a file called logs.txt (in case this file dont exist the script will create the file automatically)

There is two parts.
Snifr.py - script that receive connections from trackers, parse data, and write it to redis-db
gps.py - script that handles and decode the packet received
