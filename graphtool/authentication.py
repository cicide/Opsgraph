"""
Class to handle subscriber authentication
"""
import hashlib, random, string, os
import zlib
import struct
from Crypto.Cipher import AES
import base64
import utils

log = utils.get_logger("AuthenticateService")

class ScrambledPassword:
    """The scrambled password. """

    MIN_PASS_LEN = 6
    SALT_CHARS = string.ascii_letters + string.digits + "./"
    SALT_LEN   = 4

    def __init__( self, raw_password, salt = None):

        if len(raw_password) < ScrambledPassword.MIN_PASS_LEN:
            raise TooShortException

        if not any( [ i in raw_password for i in string.ascii_letters ] ):
            raise LetterMissingException

        #if not any( [ i in raw_password for i in string.digits ] ):
            #raise NumberMissingException

        if not salt:
            salt = ''.join( [ random.choice( ScrambledPassword.SALT_CHARS ) for i in xrange( ScrambledPassword.SALT_LEN ) ] )

        if len( salt ) != ScrambledPassword.SALT_LEN:
            raise WrongSaltLenException

        for i in salt:
            if i not in ScrambledPassword.SALT_CHARS:
                raise BadSaltCharsException

        self.__salt = salt
        self.__scrambled = hashlib.md5( raw_password + salt ).hexdigest( )

    def getSalt( self ):
        return self.__salt

    def getHashed( self ):
        return self.__scrambled

    def __str__( self ):
        return self.__scrambled

    def __len__( self ):
        return len( self.__scrambled )

    def __eq__( self, rhs ):
        return str( self ) == str( rhs )

    def __ne__(self, other):
        return str(self) != str(other)


class RawPassword:
    """ 
    The raw password.
    """

    MIN_PASS_LEN = 6
    MAX_PASS_LEN = 30

    def __init__( self, password ):
        """ Raw password """
        if not password or len(password) < RawPassword.MIN_PASS_LEN or len(password) > MAX_PASS_LEN:
            raise PasswordException("Invalid password value or length")

        if not self.isdigit( ):
            raise PasswordNotNumeric( password, self.MIN_PASS_LEN, self.MAX_PASS_LEN )

class PasswordException(Exception):
    pass

class PasswordNotNumeric(PasswordException):
    def __init__( self, password, minLength, maxLength ):
        PasswordException.__init__( self, 101, 'Passwords must be %s-%s numeric characters. Value: "%s"' % ( minLength, maxLength, password ) )

class ScrambledPasswordException(PasswordException):
    pass

class WrongSaltLenException(ScrambledPasswordException ):
    def __init__( self, salt ):
        ScrambledPasswordException.__init__( self, 102,
                                          'Salts for hashed passwords must be %s characters long. salt: %s, length: %s' % ( ScrambledPassword.SALT_LEN, salt, len( salt ) ) )

class BadSaltCharsException(ScrambledPasswordException):
    def __init__( self, salt ):
        ScrambledPasswordException.__init__( self, 103, 'The salt "%s" contains invalid characters' % salt )

class TooShortException(ScrambledPasswordException):
    def __init__( self ):
        ScrambledPasswordException.__init__( self, 104, 'Passwords must be at least %s characters long.' % ScrambledPassword.MIN_PASS_LEN )

class NumberMissingException( ScrambledPasswordException ):
    def __init__( self ):
        ScrambledPasswordException.__init__( self, 105, 'Passwords must contain at least one digit.' )

class LetterMissingException(ScrambledPasswordException):
    def __init__( self ):
        ScrambledPasswordException.__init__( self, 106, 'Passwords must contain at least one letter.' )


################################## Symmetric Crypting ###################################


class CheckSumError(Exception):
    pass

class Crypter(object):
    ''' Handle symmetric crypting/ decrypting '''

    def _lazysecret(self, secret, blocksize=32, padding='}'):
        """pads secret if not legal AES block size (16, 24, 32)"""
        if not len(secret) in (16, 24, 32):
            return secret + (blocksize - len(secret)) * padding
        return secret
    
    def encrypt(self, plaintext, secret, lazy=True):
        """encrypt plaintext with secret
        plaintext   - content to encrypt
        secret      - secret to encrypt plaintext
        lazy        - pad secret if less than legal blocksize (default: True)
        returns ciphertext
        """
    
        if type(plaintext) is unicode:
            plaintext = plaintext.encode('utf-8')
        if type(secret) is unicode:
            secret = secret.encode('utf-8')

        secret = self._lazysecret(secret) if lazy else secret
        iv_bytes = os.urandom(16)
        encobj = AES.new(secret, AES.MODE_CFB, iv_bytes)
    
        data = iv_bytes + encobj.encrypt(plaintext) 

        return base64.urlsafe_b64encode(str(data))
    
    def decrypt(self, ciphertext, secret, lazy=True):
        """decrypt ciphertext with secret
        ciphertext  - encrypted content to decrypt
        secret      - secret to decrypt ciphertext
        lazy        - pad secret if less than legal blocksize (default: True)
        returns plaintext
        """

        #log.debug("authentication:decrypt: ciphertext=%s, secret=%s"%(ciphertext, secret))

        if type(ciphertext) is unicode:
            ciphertext = ciphertext.encode('utf-8')
        if type(secret) is unicode:
            secret = secret.encode('utf-8')
        b64_ciphertext = base64.urlsafe_b64decode(ciphertext) 
        iv_bytes = b64_ciphertext[:16]
        b64_ciphertext = b64_ciphertext[16:]

        #log.debug("authentication:decrypt: b64_ciphertext=%s"%(b64_ciphertext))

        secret = self._lazysecret(secret) if lazy else secret
        encobj = AES.new(secret, AES.MODE_CFB, iv_bytes)
        plaintext = encobj.decrypt(b64_ciphertext)
    
        return plaintext

class ForcePasswordChange(Exception):
    pass

class AlreadyLoggedIn(Exception):
    pass
