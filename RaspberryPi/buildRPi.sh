#!/bin/bash

patch ../lwaTV3.py -o lwaTV3.rpi.py <convert3toRPi.patch
perms=`stat -c '%a' ../lwaTV3.py `
chmod ${perms} lwaTV3.rpi.py

