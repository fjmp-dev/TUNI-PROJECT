# Publishes the suite's mDNS name (mir-suite.local -> 192.168.1.75) so browsers on
# the LAN can reach it by name instead of by IP, and the TLS cert's CN matches.
#
# It does NOT run its own mDNS stack: it talks to the Jetson's avahi-daemon over
# the host D-Bus socket (mounted in compose). Publishing an alias natively would
# mean editing /etc/avahi as root; this keeps the whole thing inside the stack.
FROM debian:12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends avahi-utils \
 && rm -rf /var/lib/apt/lists/*

ENV MDNS_NAME=mir-suite.local \
    MDNS_IP=192.168.1.75

# -R (no reverse entry) is required: the Jetson's avahi already owns the PTR for
# 192.168.1.75 (it publishes lab.local), so claiming it again is a name collision
# and avahi-publish dies. We only want the forward name -> address record.
#
# avahi-publish stays in the foreground for as long as the name is claimed; if it
# exits (daemon restart), compose's restart policy re-claims it.
ENTRYPOINT ["/bin/sh", "-c", "exec avahi-publish -a -R \"$MDNS_NAME\" \"$MDNS_IP\""]
