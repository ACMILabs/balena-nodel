# Configure virtual network interface for Nodel
IP_ADDRESS=$(curl -X GET --header "Content-Type:application/json" "$BALENA_SUPERVISOR_ADDRESS/v1/device?apikey=$BALENA_SUPERVISOR_API_KEY" | jq -r .ip_address)
ip link add nodel0 type dummy
ifconfig nodel0 $IP_ADDRESS
mkdir -p /opt/nodel/nodes/$BALENA_DEVICE_NAME_AT_INIT
cp -f /opt/nodel/scripts/script.py /opt/nodel/nodes/$BALENA_DEVICE_NAME_AT_INIT/
# Start Nodel
java -jar /opt/nodel/nodel.jar --interface nodel0 &
ifconfig nodel0 0.0.0.0