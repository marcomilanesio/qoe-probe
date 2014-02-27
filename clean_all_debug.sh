#!/bin/bash

psql netw < ./temp_files/drop_tables.sql
#psql netw < ./drop_server_tables.sql
rm -rf ./session_bkp/
find . -name *.pyc | xargs rm 
