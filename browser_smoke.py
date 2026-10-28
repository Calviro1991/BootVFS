"""Valida Chromium localmente, sem contactar a VFS."""
import os
from playwright.sync_api import sync_playwright
from bootvfs import classify


def main():
    with sync_playwright() as playwright:
        options = {"headless": True}
        if os.environ.get("BOOTVFS_CHROMIUM"):
            options["executable_path"] = os.environ["BOOTVFS_CHROMIUM"]
        with playwright.chromium.launch(**options) as browser:
            page = browser.new_page()
            for text, expected in (("Appointment available", "possible"), ("No slots", "unavailable")):
                page.set_content(f'<main id="calendar">{text}</main>')
                actual = classify(page.locator("#calendar").inner_text(), ["Appointment available"], ["No slots"])
                if actual != expected:
                    raise RuntimeError(f"Esperado {expected}, obtido {actual}")
            print("Chromium: leitura de dois estados locais validada.")


if __name__ == "__main__":
    main()
