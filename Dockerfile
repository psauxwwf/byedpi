FROM docker.io/alpine AS build
RUN apk add --no-cache build-base linux-headers
WORKDIR /usr/local/src/byedpi
COPY . .
RUN LDFLAGS=-static make

FROM docker.io/alpine AS runtime
COPY --from=build /usr/local/src/byedpi/ciadpi /bin/ciadpi
COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
