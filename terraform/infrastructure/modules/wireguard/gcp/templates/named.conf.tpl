// BIND9 configuration — split-horizon DNS for rhesis.ai
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

// rhesis.ai zone — split-horizon: dev-*/stg-* → internal LB IPs (BIND9 only, VPN),
// prod internal records (argocd, grafana) → rhesis.ai apex (written by prd internal-dns);
// prd public hosts are static-stub zones below and resolve publicly.
//
// update-policy: each key restricted to its own hostname subtrees via subdomain grants.
// A subdomain grant on "dev-api.rhesis.ai." covers the A/AAAA record AND its sub-names
// (_external-dns.dev-api.rhesis.ai., _acme-challenge.dev-api.rhesis.ai., etc.).
// A compromised dev or stg key cannot overwrite api.rhesis.ai or app.rhesis.ai.
//
// Adding a new service requires updating bind9_allowed_names in terraform/infrastructure/main.tf
// and re-applying before ExternalDNS can create records for the new hostname.
zone "rhesis.ai" {
    type master;
    file "/var/lib/bind/rhesis.ai.zone";
    update-policy {
%{ for env, key in tsig_keys ~}
%{ for hostname in lookup(allowed_names, env, []) ~}
        grant "${key.keyname}" subdomain "${hostname}." ANY;
%{ endfor ~}
%{ for txt_name in lookup(txt_ownership_names, env, []) ~}
        grant "${key.keyname}" name "${txt_name}." TXT;
%{ endfor ~}
%{ endfor ~}
    };
};
%{ if length(public_names) > 0 ~}

// Public hostnames that must resolve as the internet sees them (proxied through
// Cloudflare), not from the rhesis.ai zone above. A static-stub zone is the deepest
// match for these names, so named recurses to the public name servers instead of
// answering from its own data. A forward zone would not work here: named forwards
// only what it cannot answer locally, and it answers anything under rhesis.ai
// itself (NXDOMAIN if the record is missing).
%{ for hostname in public_names ~}
zone "${hostname}" {
    type static-stub;
    server-names {
%{ for ns in public_name_servers ~}
        "${ns}";
%{ endfor ~}
    };
};
%{ endfor ~}
%{ endif ~}
