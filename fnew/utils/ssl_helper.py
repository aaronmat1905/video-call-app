import socket
from OpenSSL import crypto
import os
from datetime import datetime, timedelta

def get_local_ip():
    """Get the local IP address of the machine."""
    try:
        # Create a socket to get the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Connect to Google's DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"  # Fallback to localhost

def generate_self_signed_cert(
    emailAddress="videochat@example.com",
    commonName="localhost",
    countryName="US",
    localityName="Locality",
    stateOrProvinceName="State",
    organizationName="Organization",
    organizationUnitName="Org Unit",
    serialNumber=0,
    validityStartInSeconds=0,
    validityEndInSeconds=10*365*24*60*60,
    KEY_FILE="key.pem",
    CERT_FILE="cert.pem"):
    """Generate self-signed certificates for SSL."""
    
    # Get the local IP for SAN
    local_ip = get_local_ip()
    
    # Create key
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)
    
    # Create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = countryName
    cert.get_subject().ST = stateOrProvinceName
    cert.get_subject().L = localityName
    cert.get_subject().O = organizationName
    cert.get_subject().OU = organizationUnitName
    cert.get_subject().CN = commonName
    cert.get_subject().emailAddress = emailAddress
    
    # Set certificate validity
    cert.set_serial_number(serialNumber)
    cert.set_notBefore(datetime.now().strftime("%Y%m%d%H%M%SZ").encode())
    cert.set_notAfter((datetime.now() + timedelta(days=365)).strftime("%Y%m%d%H%M%SZ").encode())
    
    # Set issuer to subject (self-signed)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    
    # Add Subject Alternative Names
    san_list = [
        b"DNS:localhost",
        b"DNS:127.0.0.1",
        f"DNS:{local_ip}".encode(),
        f"IP:{local_ip}".encode(),
        b"IP:127.0.0.1"
    ]
    
    san_extension = crypto.X509Extension(
        b"subjectAltName",
        False,
        b", ".join(san_list)
    )
    
    # Add extensions
    cert.add_extensions([
        crypto.X509Extension(b"basicConstraints", True, b"CA:FALSE"),
        crypto.X509Extension(b"keyUsage", True, b"digitalSignature, keyEncipherment"),
        crypto.X509Extension(b"extendedKeyUsage", False, b"serverAuth"),
        san_extension
    ])
    
    # Sign the certificate
    cert.sign(k, 'sha256')
    
    # Create the cert directory if it doesn't exist
    cert_dir = os.path.dirname(CERT_FILE)
    if cert_dir:
        os.makedirs(cert_dir, exist_ok=True)
    
    # Save the key and certificate
    with open(CERT_FILE, "wt") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
    
    with open(KEY_FILE, "wt") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))
        
    print(f"🔒 Generated SSL certificate for: localhost, 127.0.0.1, {local_ip}")
    return local_ip