$ORIGIN rhesis.internal.
$TTL 300
@   IN  SOA ns.rhesis.internal. admin.rhesis.internal. (
            1       ; serial (BIND auto-increments on dynamic update)
            3600    ; refresh
            900     ; retry
            604800  ; expire
            300     ; minimum TTL
        )
    IN  NS  ns.rhesis.internal.
ns  IN  A   127.0.0.1
