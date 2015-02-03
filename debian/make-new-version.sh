#!/bin/sh
# Author: Jamie Strandboge <jamie@ubuntu.com>
# Copyright (C) 2013-2014 Canonical Ltd.
#
# This script is distributed under the terms and conditions of the GNU General
# Public License, Version 3 or later. See http://www.gnu.org/copyleft/gpl.html
# for details.
set -e

usage() {
    cat <<EOM
Usage: make-new-version.sh <previous> <new>
EOM
}

previous_version="$1"
if [ -z "$previous_version" ]; then
    usage
    exit 1
fi
new_version="$2"
if [ -z "$new_version" ]; then
    usage
    exit 1
fi

for i in policygroups templates ; do
    mkdir data/$i/ubuntu/"$new_version"
    cd data/$i/ubuntu/"$new_version"
    for j in ../"$previous_version"/* ; do
        ln -s $j `basename $j`
    done
    if [ "$i" = "templates" ]; then
        if [ ! -e "ubuntu-sdk" ]; then
            echo "WARN: could not find '$i/ubuntu/$new_version/ubuntu-sdk'"
            echo "      Skipping setting up 'default' symlink."
        else
            rm -f ./default
            ln -s ubuntu-sdk default
        fi
    fi
    cd - >/dev/null
done
