"""Monitor conservador de disponibilidade VFS; não efetua reservas."""
import argparse
import json
import os
from pathlib import Path
import smtplib
import ssl
import time
from email.message import EmailMessage
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_URL = "https://visa.vfsglobal.com/ago/en/prt/application-detail"
BLOCKED = ("captcha", "verify you are human", "access denied", "just a moment",
           "waiting room", "virtual queue", "sign in", "log in", "iniciar sessão")


def normalize(text):
    return " ".join(text.casefold().split())


def classify(text, available, unavailable):
    """Ambiguidade nunca é interpretada como vaga."""
    text = normalize(text)
    if any(term in text for term in BLOCKED):
        return "manual"
    yes = any(normalize(term) in text for term in available)
    no = any(normalize(term) in text for term in unavailable)
    if yes and not no:
        return "possible"
    if no and not yes:
        return "unavailable"
    return "unknown"


def send_email(message):
    required = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "ALERT_TO")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ValueError("Faltam variáveis: " + ", ".join(missing))
    email = EmailMessage()
    email["Subject"] = "BootVFS: possível disponibilidade"
    email["From"] = os.environ["SMTP_USER"]
    email["To"] = os.environ["ALERT_TO"]
    email.set_content(message)
    with smtplib.SMTP_SSL(os.environ["SMTP_HOST"],
                          int(os.environ.get("SMTP_PORT", "465")),
                          context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(email)


def send_whatsapp():
    required = ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TO",
                "WHATSAPP_TEMPLATE", "WHATSAPP_TEMPLATE_LANGUAGE", "WHATSAPP_API_VERSION")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ValueError("Faltam variáveis: " + ", ".join(missing))
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    version = os.environ["WHATSAPP_API_VERSION"]
    if not phone_id.isdigit() or not version.startswith("v") or not version[1:].replace(".", "", 1).isdigit():
        raise ValueError("Identificador ou versão da API inválido")
    payload = {
        "messaging_product": "whatsapp",
        "to": os.environ["WHATSAPP_TO"],
        "type": "template",
        "template": {
            "name": os.environ["WHATSAPP_TEMPLATE"],
            "language": {"code": os.environ["WHATSAPP_TEMPLATE_LANGUAGE"]},
        },
    }
    request = Request(f"https://graph.facebook.com/{version}/{phone_id}/messages",
                      data=json.dumps(payload).encode(), method="POST",
                      headers={"Authorization": "Bearer " + os.environ["WHATSAPP_TOKEN"],
                               "Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if not result.get("messages"):
        raise RuntimeError("A API não confirmou a aceitação da mensagem")


def notify(url, channels):
    """Um canal em falha não impede os restantes; terminal sempre ativo."""
    message = f"Possível disponibilidade na VFS. Confirma e agenda manualmente: {url}"
    print(message, flush=True)
    success = True
    for channel in dict.fromkeys(channels):
        try:
            if channel == "email":
                send_email(message)
            elif channel == "whatsapp":
                send_whatsapp()
        except Exception as error:
            print(f"Falha no alerta {channel} ({type(error).__name__}).", flush=True)
            success = False
    return success


def load_config(path):
    config = json.loads(Path(path).read_text())
    url = urlsplit(config.get("url", DEFAULT_URL))
    if url.scheme != "https" or not url.hostname or not (
        url.hostname == "vfsglobal.com" or url.hostname.endswith(".vfsglobal.com")
    ) or url.username or url.password:
        raise ValueError("Usa um URL HTTPS oficial de vfsglobal.com, sem credenciais.")
    config.setdefault("url", DEFAULT_URL)
    config.setdefault("interval_seconds", 900)
    if not isinstance(config["interval_seconds"], (int, float)) or not 300 <= config["interval_seconds"] <= 86400:
        raise ValueError("interval_seconds deve estar entre 300 e 86400.")
    for key in ("available_text", "unavailable_text"):
        values = config.get(key)
        if not isinstance(values, list) or not values or not all(isinstance(x, str) and x.strip() for x in values):
            raise ValueError(f"Configura {key} com textos reais observados no calendário.")
    config.setdefault("selector", "body")
    if not isinstance(config["selector"], str) or not config["selector"].strip():
        raise ValueError("selector deve ser um seletor CSS não vazio.")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--headed", action="store_true", help="Mostrar navegador (requer ambiente gráfico)")
    parser.add_argument("--login", action="store_true", help="Entrar manualmente e guardar sessão local")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--channel", choices=("terminal", "email", "whatsapp"), action="append",
                        help="Pode repetir para ativar vários canais; terminal sempre ativo")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.login and not args.headed:
        parser.error("--login requer --headed e um ambiente gráfico local")
    from playwright.sync_api import sync_playwright
    private = Path(".bootvfs")
    private.mkdir(mode=0o700, exist_ok=True)
    private.chmod(0o700)
    with sync_playwright() as playwright:
        options = {"headless": not args.headed}
        if os.environ.get("BOOTVFS_CHROMIUM"):
            options["executable_path"] = os.environ["BOOTVFS_CHROMIUM"]
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy_url:
            proxy = urlsplit(proxy_url)
            options["proxy"] = {"server": f"{proxy.scheme}://{proxy.hostname}:{proxy.port or 8080}"}
            if proxy.username:
                options["proxy"]["username"] = proxy.username
            if proxy.password:
                options["proxy"]["password"] = proxy.password
        with playwright.chromium.launch_persistent_context(str(private / "browser"), **options) as browser:
            page = browser.pages[0] if browser.pages else browser.new_page()
            if args.login:
                page.goto(config["url"], wait_until="domcontentloaded", timeout=60000)
                input("Entra manualmente e abre o calendário. Depois prime Enter aqui para guardar e sair. ")
                return
            previous = None
            failures = 0
            while True:
                try:
                    response = page.goto(config["url"], wait_until="domcontentloaded", timeout=60000)
                    if response is None or response.status >= 400:
                        status = "http_error"
                    else:
                        content = page.locator(config["selector"]).inner_text(timeout=30000)
                        status = classify(content, config["available_text"], config["unavailable_text"])
                    print(time.strftime("%Y-%m-%d %H:%M:%S"), status, flush=True)
                    delivery_failed = False
                    if status == "possible" and previous != "possible":
                        delivery_failed = not notify(config["url"], args.channel or ["terminal"])
                    # Erros ou páginas ambíguas não rearmam um alerta já enviado.
                    if status in ("possible", "unavailable"):
                        previous = status
                    if status == "manual":
                        print("É necessária intervenção manual. Monitor parado.", flush=True)
                        return 2
                    if delivery_failed:
                        status = "notification_error"
                    if status in ("unknown", "http_error", "notification_error"):
                        failures += 1
                    else:
                        failures = 0
                except Exception as error:
                    # Não imprimir mensagens que possam conter dados da sessão.
                    print(f"Falha na verificação ({type(error).__name__}); sem alerta.", flush=True)
                    status = "error"
                    failures += 1
                if args.once:
                    return 0 if status in ("possible", "unavailable") else 2
                if failures >= 3:
                    print("Três verificações inconclusivas. Confirma a sessão e a configuração manualmente.")
                    return 2
                time.sleep(min(86400, config["interval_seconds"] * (2 ** min(failures, 4))))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"Erro de configuração ou ambiente: {type(error).__name__}. Consulta o README.")
        raise SystemExit(2)
