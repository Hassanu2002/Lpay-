from abc import ABC, abstractmethod


class NotificationProvider(ABC):
    @abstractmethod
    async def send_phone_otp(self, phone_number: str, code: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_email_verification(self, email: str, token: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_password_reset(self, email: str, token: str) -> None:
        raise NotImplementedError


class NullNotificationProvider(NotificationProvider):
    """
    Development adapter. It deliberately does not log or expose OTPs/tokens.
    A real SMS/email adapter will be added through the provider interface later.
    """

    async def send_phone_otp(self, phone_number: str, code: str) -> None:
        return None

    async def send_email_verification(self, email: str, token: str) -> None:
        return None

    async def send_password_reset(self, email: str, token: str) -> None:
        return None


notification_provider = NullNotificationProvider()
