import hashlib
import logging
import secrets
import time
from django.conf import settings
from django.core.cache import cache
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.module_loading import import_string

class ConsoleProvider:
    """Local challenge provider. Replace both issue and verify for a real SMS service."""
    def issue(self, phone):
        if not settings.DEBUG:
            raise ValueError("O provedor de SMS precisa ser configurado.")
        code = f"{secrets.randbelow(1000000):06d}"
        nonce = secrets.token_hex(16)
        logging.getLogger("bytebistro.sms").info("SMS local • final %s • código %s", phone[-4:], code)
        return nonce + "." + salted_hmac(nonce, code).hexdigest()

    def verify(self, challenge, code):
        nonce, digest = challenge.split(".")
        return constant_time_compare(digest, salted_hmac(nonce, code).hexdigest())

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
