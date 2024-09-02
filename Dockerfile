FROM ubuntu:latest
LABEL authors="dev"

ENTRYPOINT ["top", "-b"]