#!/bin/bash

set -e

if [ ! "$1" ]; then
	echo "USAGE: $0 version"
	exit 1
fi
VERSION="$1"
DIST="am433-$VERSION"

git clone . "$DIST"

rm -rf "$DIST/.git"
find "$DIST" -type f -name .gitignore -delete
rm "$DIST/am433/tests"/*.ok "$DIST/am433/tests"/*.raw

tar -czf "$DIST".tar.gz "$DIST"
rm -r "$DIST"
