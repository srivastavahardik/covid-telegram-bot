#!/bin/bash
while IFS= read -r line; do
	city=$(echo $line | cut -d'=' -f 1)
	echo "Launching tmux for $city"
	tmux new-session -d -s $city python covid.py $line
done < $1
