#!/bin/bash

curl -X POST --header "Content-Type:application/json" "$BALENA_SUPERVISOR_ADDRESS/v1/reboot?apikey=$BALENA_SUPERVISOR_API_KEY"