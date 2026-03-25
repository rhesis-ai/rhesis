// BIND9 configuration for rhesis.internal dynamic DNS
// Managed by Terraform — do not edit manually

options {
    directory "/var/cache/bind";
    listen-on { any; };
    listen-on-v6 { none; };

    allow-query {
        127.0.0.0/8;
%{ for cidr in allow_query_cidrs ~}
        ${cidr};
%{ endfor ~}
    };

    // Forward non-authoritative queries (replaces dnsmasq forwarding)
    forwarders {
        8.8.8.8;
        8.8.4.4;
    };
    forward only;

    dnssec-validation no;
    recursion yes;
};

logging {
    channel default_log {
        syslog daemon;
        severity info;
        print-time yes;
        print-category yes;
    };
    category default { default_log; };
};

// TSIG key definitions (one per environment)
%{ for env, key in tsig_keys ~}
key "${key.keyname}" {
    algorithm hmac-sha256;
    secret "${key.secret}";
};

%{ endfor ~}

// rhesis.internal zone — accepts dynamic updates from all env TSIG keys
zone "rhesis.internal" {
    type master;
    file "/var/lib/bind/rhesis.internal.zone";
    allow-update {
%{ for env, key in tsig_keys ~}
        key "${key.keyname}";
%{ endfor ~}
    };
};
