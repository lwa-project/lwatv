#!/bin/bash

patch lwaTV3.py -o lwaTV2.py <convert3to2.patch
perms=`stat -c '%a' lwaTV3.py `
chmod ${perms} lwaTV2.py

