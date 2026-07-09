FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:13e428067eac23eafc5ccf570ff2fb19beab981036b00b5d90902c20da1cc236

COPY . $SRC/amqtt
WORKDIR $SRC/amqtt

COPY .clusterfuzzlite/build.sh $SRC/
