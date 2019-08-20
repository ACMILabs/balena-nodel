# Start Nodel
mkdir -p /opt/nodel/nodes/$BALENA_DEVICE_NAME_AT_INIT
cp -f /opt/nodel/scripts/script.py /opt/nodel/nodes/$BALENA_DEVICE_NAME_AT_INIT/
java -jar /opt/nodel/nodel.jar