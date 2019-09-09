# base-image for python on any machine using a template variable,
# see more about dockerfile templates here: https://www.balena.io/docs/learn/develop/dockerfile/
FROM balenalib/intel-nuc-alpine-openjdk:latest-run
# TODO: Get the RPi image working
# FROM balenalib/raspberrypi3-alpine-openjdk:latest-run

# use `install_packages` if you need to install dependencies,
# for instance if you need git, just uncomment the line below.
RUN install_packages wget jq iproute2

# Latest Nodel release
ENV NODEL_JAR https://github.com/museumsvictoria/nodel/releases/download/v2.1.1-release389/nodelhost-release-2.1.1-rev389.jar

# Install Nodel
RUN mkdir /opt/nodel && wget -O /opt/nodel/nodel.jar $NODEL_JAR

# Copy scripts
COPY ./scripts/ /code/
RUN chmod +x /code/shutdown.sh
RUN chmod +x /code/reboot.sh

# Copy recipes
COPY recipes/script.py /opt/nodel/scripts/script.py

COPY ./script.sh /opt/nodel/script.sh
WORKDIR /opt/nodel/

# script.sh will run when container starts up on the device
CMD ["bash","script.sh"]