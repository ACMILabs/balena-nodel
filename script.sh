# Copy recipe to directory based on device name
mkdir -p /opt/nodel/nodes/$BALENA_DEVICE_NAME_AT_INIT
cp -f /opt/nodel/scripts/script.py /opt/nodel/nodes/$BALENA_DEVICE_NAME_AT_INIT/
# Start Nodel
java -jar /opt/nodel/nodel.jar --interface $NODEL_INTERFACE