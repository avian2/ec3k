#!/bin/bash

VERDICT=0

for TEST in *.raw; do
	BASE=`basename "$TEST" .raw`
	../capture -f "$TEST" > "$BASE.out"
	if [ -e "$BASE.ok" ]; then
		if ! diff -u "$BASE.ok" "$BASE.out"; then
			VERDICT=1
		else
			rm "$BASE.out"
		fi
	else
		echo "Creating new test case $BASE.ok"
		cp -a "$BASE.out" "$BASE.ok"
	fi
done

exit "$VERDICT"
