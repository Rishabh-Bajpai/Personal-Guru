# scripts/generate_cert.py

from OpenSSL import crypto
from pathlib import Path

def generate_self_signed_cert(cert_dir="certs", cert_name="cert.pem", key_name="key.pem"):
    """
    Generates a self-signed certificate and a private key and saves them to the specified directory.
    """
    # Create the certificate directory if it doesn't exist
    Path(cert_dir).mkdir(parents=True, exist_ok=True)

    cert_path = Path(cert_dir) / cert_name
    key_path = Path(cert_dir) / key_name

    if cert_path.exists() and key_path.exists():
        print(f"Certificate '{cert_path}' and key '{key_path}' already exist. Skipping generation.")
        return

    # Generate a new private key
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    # Create a new self-signed certificate
    cert = crypto.X509()
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)  # 10 years
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, 'sha256')

    # Save the certificate and key to files
    try:
        with open(cert_path, "wt") as cert_file:
            cert_file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode('utf-8'))
        with open(key_path, "wt") as key_file:
            key_file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key).decode('utf-8'))
        print(f"Successfully generated certificate to '{cert_path}' and key to '{key_path}'")
    except IOError as e:
        print(f"Error writing certificate or key files: {e}")

if __name__ == "__main__":
    generate_self_signed_cert()