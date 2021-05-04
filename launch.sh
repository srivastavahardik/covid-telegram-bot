#!/bin/bash
echo "Killing existing sessions..."
screen -ls | grep Detached | cut -d. -f1 | awk '{print $1}' | xargs kill
killall -p firefox
while IFS= read -r line; do
	city=$(echo $line | cut -d'=' -f 1)
	echo "Launching for $city"
	screen -S $city -d -m python3 covid.py $line
done < $1
