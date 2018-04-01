#!/usr/bin/env python
# certbot-he-hook.py
# A hook to be used for manual DNS validation through Hurricate Electric
# Refer to the README for instructions on use
from __future__ import print_function
from requests import Session
from os import environ
from time import sleep
from sys import stderr
from bs4 import BeautifulSoup

def main():
    # Parse the required environment variables, and error out of any are missing
    try:
        he_username = environ["HE_USERNAME"]
        he_password = environ["HE_PASSWORD"]
        he_zone = environ["HE_ZONE"]
        certbot_domain = environ["CERTBOT_DOMAIN"]
        certbot_validation = environ["CERTBOT_VALIDATION"]
    except KeyError as error:
        eprint("ERROR: Required environment variable %s is unset" % error)
        return 1
    
    # Login to HE
    try:
        session = login(he_username, he_password)
    except ValueError as error:
        eprint(error)
        return 1

    # Certbot stores the output of Auth in the CERTBOT_AUTH_OUTPUT variable
    # and then passes it into the cleanup, this is how we differentiate the action
    try:
        certbot_auth_output = environ["CERTBOT_AUTH_OUTPUT"]
    except:
        cleanup = False
    else:
        cleanup = True
    
    # Cleanup routine
    if cleanup:
        # Delete the record id that is passed into CERTBOT_AUTH_OUTPUT, and complete
        try:
            delete_validation(session, he_zone, certbot_auth_output)
        except RuntimeError as error:
            eprint(error)
            return 1
        else:
            return 0
    else:
        # Propogation of the newly created record can take time, which certbot
        # does not account for, the script will sleep for 30 seconds unless overridden
        try:
            he_propagation_seconds = environ["HE_PROPAGATION_SECONDS"]
        except:
            he_propagation_seconds = 30

        # Create the validation record
        try:
            record_id = set_validation(session, he_zone, certbot_domain, certbot_validation)
        except ValueError as error:
            eprint(error)
            return 1
        except RuntimeError as error:
            eprint(error)
            return 1
        else:
            # Print the record ID so certbot passes it into the cleanup
            print(record_id)

            # Sleep for DNS propogation, and complete
            sleep(he_propagation_seconds)
            return 0

def login(username, password):
    """
    Login to Hurricane Electric and return a session that has the cookie

    Args:
        username: Username for HE
        password: Password for HE

    Returns:
        A requests.Session object that is authenticated to HE
    
    Raises:
        ValueError: If the login is not successful
    """

    # Create the session GET the login page to retrieve a session cookie
    session = Session()    
    session.get(
        "https://dns.he.net/"
    )

    # Hit the login page with authentication info to login the session
    login_response = session.post(
       "https://dns.he.net",
        data={
            "email": username,
            "pass": password
        }
    )

    # Parse in the HTML, if the div containing the error message is found, error
    html = BeautifulSoup(login_response.content, "html.parser")
    if html.find("div", {"id": "dns_err"}) is not None:
        raise ValueError("ERROR: HE login failed, check HE_USER and HE_PASS")

    # Return the authenticated session
    return session

def get_zone_id(session, zone):
    """
    Given a zone (domain), retrieve the associated "Zone ID" from HE

    Args:
        session: Authenticated session to HE
        zone: Name of the zone (domain)
    
    Returns:
        The ID of the zone from HE
    
    Raises:
        ValueError: If the zone is not found in the HE account
    """

    # Make an authenticated GET to the DNS management page
    zones_response = session.get(
        "https://dns.he.net"
    )

    # Retrieve the <img> for deleting the zone with the name specified
    # The delete button is used because it includes a name tag with the ID in it
    html = BeautifulSoup(zones_response.content, "html.parser")
    zone_id = html.find("img", {"name": zone, "alt": "delete"})

    # If the tag couldn't be found, error, otherwise, return the value of the tag
    if zone_id is None:
        raise ValueError("ERROR: Domain not found in account, check CERTBOT_DOMAIN")
    else:
        return zone_id["value"]

def delete_validation(session, zone, record_id):
    """
    Delete a validation record from HE

    Args:
        session: Authenticated session to HE
        zone: Name of the zone (domain)
        record_id: ID of the validation record to be deleted
    
    Raises:
        ValueError: If unable to resolve the zone provided
        RuntimeError: If unable to delete the validation record with the ID provided
    """

    # Retrieve the zone ID for the zone
    try:
        zone_id = get_zone_id(session, zone)
    except ValueError as error:
        raise error
    
    # POST to the DNS management UI with form values to delete the record
    delete_response = session.post(
        "https://dns.he.net/index.cgi",
        data={
            "menu": "edit_zone",
            "hosted_dns_zoneid": zone_id,
            "hosted_dns_recordid": record_id,
            "hosted_dns_editzone": "1",
            "hosted_dns_delrecord": "1",
            "hosted_dns_delconfirm": "delete"
        }
    )

    # Parse the HTML response, if the <div> tag indicating success isn't found, error
    html = BeautifulSoup(delete_response.content, "html.parser")
    if html.find("div", {"id": "dns_status"}) is None:
        raise RuntimeError("ERROR: Unable to delete validation record, either it does not exist, or it needs to be manually removed")

def set_validation(session, zone, certbot_domain, certbot_validation):
    """
    Create a TXT validation record in HE

    Args:
        session: Authenticated session to HE
        zone: Name of the zone (domain)
        certbot_domain: Domain that certbot is performing validation on
        certbot_validation: Validation string to be placed in the TXT record
    
    Returns:
        The ID of the created validation record
    
    Raises:
        ValueError: If unable to resolve the zone provided
        RuntimeError: If unable to create the validation record
    """

    # Retrieve the zone ID for the zone
    try:
        zone_id = get_zone_id(session, zone)
    except ValueError as error:
        raise error

    # Form the name of the TXT record
    record_name = "_acme-challenge.%s" % certbot_domain

    # POST to the DNS management page with form values to create the validation record
    # It is a TXT record, _acme-challenge.domain.tld with a random string passed into
    # the hook and a TTL of 300
    create_response = session.post(
        "https://dns.he.net/index.cgi",
        data={
            "account": "",
            "menu": "edit_zone",
            "Type": "TXT",
            "hosted_dns_zoneid": zone_id,
            "hosted_dns_recordid": "",
            "hosted_dns_editzone": "1",
            "Priority": "",
            "Name": record_name,
            "Content": certbot_validation,
            "TTL": "300",
            "hosted_dns_editrecord": "Submit"
        }
    )

    # Parse the HTML response, and list the table rows for DNS records
    html = BeautifulSoup(create_response.content, "html.parser")
    records = html.findAll("tr", {"class": "dns_tr"})

    # Check each table row to see if it is the validation record
    for record in records:
        found = False

        # Retrieve all table data tags for the row
        for value in record.findAll("td", {"class": "dns_view"}):
            # If the proper record is found, indicate and exit the loop
            if value.get_text() == record_name:
                found = True
                break
        
        # If found, return the contents of the "id" attribute on the <tr> tag
        if found:
            return record["id"]
    
    # If none of the rows match the validation record, error
    raise RuntimeError("ERROR: Record not created or not found in HE, check that it was created")

def eprint(*args, **kwargs):
    """
    Print a message to stderr
    """

    print(*args, file=stderr, **kwargs)

# Run the main loop when ran interactively
if __name__ == "__main__":
    exit(main())