class OTPException(Exception):
    pass


class OTPCooldownException(OTPException):
    pass


class OTPInvalidException(OTPException):
    pass


class OTPLockedException(OTPException):
    pass
