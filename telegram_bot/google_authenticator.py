import pyotp
from qrcode import QRCode, constants

class GoogleAuthenticatorClient:
    def __init__(self) -> None:
       self.secret_key = self.generate_secret_key()
       
    def generate_secret_key(self):
        """ Generate a secret key for the user """
        return pyotp.random_base32(64)
    
    def create_qr_code(self, name=None, issuer_name=None):
        """ Create a QR code for the user """
        url = pyotp.totp.TOTP(self.secret_key).provisioning_uri(name=name, issuer_name=issuer_name)
        qr = QRCode(version=1, error_correction=constants.ERROR_CORRECT_L, box_size=10, border=4)
        
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image()
        return img
    
    def verify_code(self, code):
        """ Verify the code """
        return pyotp.totp.TOTP(self.secret_key).verify(code)
     