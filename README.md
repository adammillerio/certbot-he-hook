# certbot-he-hook

This script provides the ability to perform automatic DNS validation using the Let's Encrypt [certbot](https://github.com/certbot/certbot) client and [Hurricane Electric Dynamic DNS](https://dns.he.net/).

# Installation

This script is compatible with Python 2 and 3. The only external dependency that is required is BeautifulSoup. The following command can be used to install it:

Python 2: `pip install beautifulsoup4`

Python 3: `pip3 install beautifulsoup4`

# Configuration

In order to use this hook, the following values must be provided:
| Name  | Description  |
|---|---|
| HE_USERNAME | Username used to authenticate with HE |
| HE_PASSWORD | Password used to authenticate with HE |
| HE_ZONE | "Hosted zone" for the record to be created under, e.g. adammiller.io for example.adammiller.io |
| HE_PROPAGATION_SECONDS | (Optional) Time to wait before ending execution of the auth hook, defaults to 30 seconds |

# Usage

The following is an example execution of certbot using the hook in order to validate example.adammiller.io, this assumes that the script is located at `/opt/certbot-he-hook.py` and is executable:

```
HE_USERNAME=adammillerio HE_PASSWORD=admin123 HE_ZONE=adammiller.io \
	certbot certonly \
	--domain example.adammiller.io \
	--email admin@adammiller.io \
	--preferred-challenges dns \
	--manual \
	--manual-auth-hook "/opt/certbot-he-hook.py"  \
	--manual-cleanup-hook "/opt/certbot-he-hook.py"  \
	--manual-public-ip-logging-ok
```

In addition, here is an example of certificate renewal:

```
HE_USERNAME=adammillerio HE_PASSWORD=admin123 HE_ZONE=adammiller.io \
	certbot renew \
	--preferred-challenges dns \
	--manual-auth-hook "/opt/certbot-he-hook.py"  \
	--manual-cleanup-hook "/opt/certbot-he-hook.py"  \
	--manual-public-ip-logging-ok
```

# Overview

When performing validations, Certbot provides several different standard plugins to use for validation with popular services. However, for less popular services, it offers what is referred to as "manual" mode. When running in manual mode, there are two additional configuration options, which specify "hooks" (arbitrary commands) to be ran for the creation and deletion of a DNS validation record.

This script aims to be a fully functiona hook script for both authentication and cleanup. Because HE does not provide an API for DNS updates, this script makes use of both the Python Requests library for automating an HTTP session, and the BeautifulSoup library for parsing the DNS management page.

This script utilizes environment variables to determine Hurricane Electric configuration information (described in the Configuration section). In adition, it utilizes the following environment variables provided by the certbot application at runtime:

| Name  | Description  |
|---|---|
| CERTBOT_DOMAIN | Domain or subdomain which the validation is being performed form |
| CERTBOT_VALIDATION | Random string of characters provided by the certbot application |
| CERTBOT_AUTH_OUTPUT | Any content printed to stdout during the authentication hook |

The script automatically determines which routine to run based on the presence of CERTBOT_AUTH_OUTPUT, as this variable is only provided to the cleanup hook.

## Authentication

The authentication routine performs the following steps:

* Login to HE
* Retrieve the "Hosted Zone ID" provided in the HE_ZONE variable
* Create the TXT record used for DNS validation by certbot
* Sleep for the time provided in HE_PROPAGATION_SECONDS, or 30 seconds if undefined, in order to ensure the record creation has propagated
* Retrieve the "Hosted Record ID" of the newly created record
* Print the record ID to stdout so it can be passed back into the cleanup hook

## Cleanup

The cleanup routine performs the following steps:

* Parse the record ID printed to stdout and provided to the cleanup hook as CERTBOT_AUTH_OUTPUT
* Login to HE
* Retrieve the "Hosted Zone ID" provided in the HE_ZONE variable
* Delete the DNS record with the associated record ID

# Limitations

Currently, due to the way it is implemented, this will only work with `certbot renew` if all certificates are for the same zone (domain). In order to work around this, multiple `certbot renew` invocations can be made with different values for HE_ZONE.

# Disclaimer

Because HE provides no API whatsoever, this script is ultimately at the mercy of their development team. This hook relies on directly manipulating the DOM, so if it changes, existing functionality may be broken. If this happens, let me know, and I will try my best to fix it.