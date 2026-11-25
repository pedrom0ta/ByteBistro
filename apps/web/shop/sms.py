import hashlib
import logging
import re
import secrets
import time
from django.conf import settings
from django.core.cache import cache
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.module_loading import import_string

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ModuleNotFoundError:
    class BotoCoreError(Exception):
        pass

    class ClientError(Exception):
        pass


def _sns_client():
    import boto3
    return boto3.client("sns")


class _OtpProvider:
    def _create_challenge(self):
        code = f"{secrets.randbelow(1000000):06d}"
        nonce = secrets.token_hex(16)
        return code, nonce + "." + salted_hmac(nonce, code).hexdigest()

    def verify(self, challenge, code):
        if not isinstance(challenge, str) or not isinstance(code, str):
            return False
        nonce, sep, digest = challenge.partition(".")
        if not nonce or not sep or not digest or "." in digest:
            return False
        return constant_time_compare(digest, salted_hmac(nonce, code).hexdigest())


class ConsoleProvider(_OtpProvider):
    """Local challenge provider. Replace both issue and verify for a real SMS service."""
    def issue(self, phone):
        if not settings.DEBUG:
            raise ValueError("O provedor de SMS precisa ser configurado.")
        code, challenge = self._create_challenge()
        logging.getLogger("bytebistro.sms").info("SMS local • final %s • código %s", phone[-4:], code)
        return challenge


class SnsSmsProvider(_OtpProvider):
    """Production SMS provider backed by AWS SNS."""

    def __init__(self, client=None, country_code=None):
        self.client = client
        self.country_code = country_code

    def _client(self):
        return self.client if self.client is not None else _sns_client()

    def _normalize_phone(self, phone):
        if not isinstance(phone, str):
            raise ValueError("Número de telefone inválido.")
        cleaned = re.sub(r"[\s()-]", "", phone.strip())
        if cleaned.startswith("+"):
            if not re.fullmatch(r"\+[1-9][0-9]{7,14}", cleaned):
                raise ValueError("Número de telefone inválido.")
            return cleaned
        if not re.fullmatch(r"[0-9]{10,12}", cleaned):
            raise ValueError("Número de telefone inválido.")
        raw_cc = getattr(settings, "SMS_COUNTRY_CODE", "+55") if self.country_code is None else self.country_code
        if not isinstance(raw_cc, str):
            raise ValueError("Número de telefone inválido.")
        country_code = raw_cc.strip()
        if country_code and not country_code.startswith("+"):
            country_code = "+" + country_code
        if not re.fullmatch(r"\+[1-9][0-9]{0,3}", country_code):
            raise ValueError("Número de telefone inválido.")
        target = f"{country_code}{cleaned}"
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", target):
            raise ValueError("Número de telefone inválido.")
        return target

    def issue(self, phone):
        target = self._normalize_phone(phone)
        code, challenge = self._create_challenge()
        logger = logging.getLogger("bytebistro.sms")
        try:
            client = self._client()
            client.publish(
                PhoneNumber=target,
                Message=f"ByteBistro: seu código de verificação é {code}. Válido por 5 minutos.",
                MessageAttributes={
                    "AWS.SNS.SMS.SMSType": {
                        "DataType": "String",
                        "StringValue": "Transactional",
                    }
                },
            )
        except (BotoCoreError, ClientError) as error:
            logger.warning(
                "Falha ao enviar SMS SNS • final %s • erro %s",
                target[-4:],
                type(error).__name__,
            )
            raise ValueError("Não foi possível enviar o SMS. Tente novamente.") from error
        logger.info("SMS SNS enviado • final %s", target[-4:])
        return challenge

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def limit(key, maximum, seconds):
    cache.add(key, 0, seconds)
    if cache.incr(key) > maximum:
        raise ValueError("Limite atingido. Tente novamente mais tarde.")

def issue(request, phone):
    key = digest(phone)
    limit("ip:"+digest(request.META.get("REMOTE_ADDR", "")), 24, 3600)
    if not cache.add("cool:"+key, True, 60):
        raise ValueError("Aguarde um minuto para solicitar outro código.")
    limit("send:"+key, 4, 3600)
    challenge = import_string(settings.SMS_PROVIDER)().issue(phone)
    request.session["otp"] = dict(phone=phone, challenge=challenge, issued=int(time.time()))
    cache.set("current:"+key, challenge, 300)
    request.session.pop("verified", None)

def verify(session, code):
    otp = session.get("otp", {})
    key = digest(otp.get("phone", ""))
    challenge = otp.get("challenge")
    if not challenge or time.time()-otp["issued"] >= 300 or cache.get("current:"+key) != challenge:
        raise ValueError("Código expirado. Solicite um novo SMS.")
    limit("attempt:"+digest(challenge), 5, 300)
    if not import_string(settings.SMS_PROVIDER)().verify(challenge, code):
        raise ValueError("Código incorreto. Confira os seis dígitos.")
    if not cache.add("used:"+digest(challenge), True, 300):
        raise ValueError("Código já utilizado.")
    session.cycle_key()
    session.pop("otp")
    return otp["phone"]
