import os
import time
from dataclasses import dataclass

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, ElementClickInterceptedException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


SEARCH_SELECTORS = [
    (By.XPATH, "//div[@contenteditable='true' and @role='textbox' and @data-tab='3']"),
    (By.XPATH, "//div[@contenteditable='true' and @role='textbox' and @data-tab='4']"),
    (By.XPATH, "//div[@contenteditable='true' and @role='textbox' and contains(@aria-label,'Pesquisar')]"),
    (By.XPATH, "//div[@contenteditable='true' and @role='textbox' and contains(@aria-label,'Search')]"),
]

NEW_CHAT_SELECTORS = [
    (By.XPATH, "//span[@data-icon='new-chat-outline']"),
    (By.XPATH, "//span[@data-icon='chat']"),
    (By.XPATH, "//button[@aria-label='Nova conversa']"),
    (By.XPATH, "//button[@aria-label='New chat']"),
    (By.XPATH, "//*[@title='Nova conversa']"),
    (By.XPATH, "//*[@title='New chat']"),
]

MESSAGE_SELECTORS = [
    (By.XPATH, "//div[@contenteditable='true' and @role='textbox' and @data-tab='10']"),
    (By.XPATH, "//div[@contenteditable='true' and @role='textbox' and @data-tab='9']"),
]

ATTACH_BUTTON_SELECTORS = [
    (By.XPATH, "//div[@title='Anexar']"),
    (By.XPATH, "//div[@title='Attach']"),
    (By.XPATH, "//span[@data-icon='attach-menu-plus']"),
    (By.XPATH, "//span[@data-icon='clip']"),
    (By.XPATH, "//button[contains(@aria-label,'Anexar')]"),
    (By.XPATH, "//button[contains(@aria-label,'Attach')]"),
    (By.XPATH, "//button[contains(@aria-label,'Adicionar')]"),
    (By.XPATH, "//button[contains(@aria-label,'Mais')]"),
]

DOCUMENT_INPUT_XPATH = (
    "//input[@type='file' and @accept "
    "and (contains(@accept,'image') or contains(@accept,'video') or contains(@accept,'*'))]"
)

IMAGE_INPUT_XPATH = "//input[@type='file' and @accept and contains(@accept,'image')]"

NO_RESULTS_XPATH = (
    "//*[contains(text(),'Nenhum chat') "
    "or contains(text(),'Nenhum contato') "
    "or contains(text(),'Nenhuma conversa') "
    "or contains(text(),'No chats, contacts or messages found')]"
)


@dataclass
class SendResult:
    number: str
    sent: bool
    error: str = ""


def wait_for_any(driver, selectors, timeout=30):
    end = time.time() + timeout
    last_error = None
    while time.time() < end:
        for by, sel in selectors:
            try:
                el = driver.find_element(by, sel)
                if el.is_displayed():
                    return el
            except Exception as exc:
                last_error = exc
        time.sleep(0.5)
    raise TimeoutException("Timeout waiting for element") from last_error


def has_no_results(driver):
    candidates = driver.find_elements(By.XPATH, NO_RESULTS_XPATH)
    return any(el.is_displayed() for el in candidates)


def normalize_number(raw):
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits


def click_new_chat(driver):
    try:
        button = wait_for_any(driver, NEW_CHAT_SELECTORS, timeout=10)
        try:
            button.click()
        except ElementClickInterceptedException:
            # Fechar qualquer overlay (menus) que possam bloquear o clique.
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
            try:
                button.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", button)
        time.sleep(1)
    except TimeoutException:
        return False
    return True


def type_slowly(element, text, delay=0.05):
    for ch in text:
        element.send_keys(ch)
        time.sleep(delay)


def collect_numbers():
    print("Cole os numeros (um por linha). Linha vazia para terminar:")
    numbers = []
    while True:
        line = input().strip()
        if not line:
            break
        parts = [p.strip() for p in line.split(",") if p.strip()]
        for part in parts:
            digits = normalize_number(part)
            if digits:
                numbers.append(digits)
    return numbers


def build_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    # Use a persistent profile folder to keep WhatsApp Web logged in.
    profile_dir = os.path.join(os.getcwd(), "chrome_profile")
    options.add_argument(f"--user-data-dir={profile_dir}")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def send_message(driver, number, message):
    for _ in range(2):
        try:
            click_new_chat(driver)
            search_box = wait_for_any(driver, SEARCH_SELECTORS, timeout=60)
            search_box.click()
            search_box.send_keys(Keys.CONTROL, "a")
            search_box.send_keys(Keys.BACKSPACE)
            type_slowly(search_box, number, delay=0.05)
            time.sleep(2)
            break
        except StaleElementReferenceException:
            time.sleep(1)
            continue

    if has_no_results(driver):
        return False

    search_box.send_keys(Keys.ENTER)
    message_box = wait_for_any(driver, MESSAGE_SELECTORS, timeout=30)
    message_box.click()
    lines = message.splitlines() or [""]
    for index, line in enumerate(lines):
        if line:
            message_box.send_keys(line)
        if index < len(lines) - 1:
            message_box.send_keys(Keys.SHIFT, Keys.ENTER)
    message_box.send_keys(Keys.ENTER)
    return True


def find_file_input(driver, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        inputs = driver.find_elements(By.XPATH, DOCUMENT_INPUT_XPATH)
        if inputs:
            return inputs[0]
        time.sleep(0.5)
    raise TimeoutException("Timeout waiting for file input")


def click_attach_menu(driver, log_callback, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        for by, sel in ATTACH_BUTTON_SELECTORS:
            try:
                el = driver.find_element(by, sel)
                if el.is_displayed():
                    el.click()
                    log_callback("Menu de anexo aberto.")
                    return True
            except Exception:
                continue
        time.sleep(0.5)
    log_callback("Nao foi possivel abrir o menu de anexo.")
    return False


def send_image_attachment(driver, file_path, log_callback):
    if not os.path.exists(file_path):
        log_callback("Imagem nao encontrada no disco.")
        return False
    if not click_attach_menu(driver, log_callback, timeout=30):
        return False
    file_input = None
    try:
        file_input = wait_for_any(driver, [(By.XPATH, IMAGE_INPUT_XPATH)], timeout=5)
        log_callback("Input de imagem encontrado.")
    except TimeoutException:
        log_callback("Input de imagem nao encontrado, tentando input generico.")
        file_input = find_file_input(driver, timeout=30)
    file_input.send_keys(file_path)
    time.sleep(2)
    send_button = wait_for_any(
        driver,
        [
            (By.XPATH, "//div[@role='button' and @aria-label='Enviar']"),
            (By.XPATH, "//div[@role='button' and @aria-label='Send']"),
            (By.XPATH, "//button[@aria-label='Enviar']"),
            (By.XPATH, "//button[@aria-label='Send']"),
            (By.XPATH, "//span[@data-icon='send']"),
            (By.XPATH, "//span[@data-icon='checkmark']"),
            (By.XPATH, "//button//*[contains(@data-icon,'send')]"),
            (By.XPATH, "//div[contains(@aria-label,'Enviar')]"),
            (By.XPATH, "//div[contains(@aria-label,'Send')]"),
        ],
        timeout=30,
    )
    send_button.click()
    time.sleep(2)
    return True


def run_automation(numbers, message, log_callback=None, image_path=None):
    if log_callback is None:
        log_callback = print

    log_callback("Iniciando navegador...")
    try:
        driver = build_driver()
    except Exception as exc:
        log_callback(f"Falha ao iniciar o navegador: {exc}")
        return []

    driver.get("https://web.whatsapp.com")
    log_callback("Escaneie o QR Code no WhatsApp Web e aguarde a tela carregar.")

    try:
        wait_for_any(driver, SEARCH_SELECTORS, timeout=180)
    except TimeoutException:
        log_callback("Nao foi possivel encontrar a caixa de pesquisa. Verifique o login.")
        driver.quit()
        return []

    results = []
    for number in numbers:
        try:
            sent = send_message(driver, number, message)
            if sent:
                if image_path:
                    sent_image = send_image_attachment(driver, image_path, log_callback)
                    if sent_image:
                        log_callback("Imagem enviada.")
                    else:
                        log_callback("Falha ao enviar imagem.")
                log_callback(f"Mensagem enviada para {number}. Aguardando 30s...")
                time.sleep(30)
                results.append(SendResult(number=number, sent=True))
            else:
                log_callback(f"Numero nao encontrado: {number}")
                results.append(
                    SendResult(number=number, sent=False, error="Numero nao encontrado")
                )
        except Exception as exc:
            log_callback(f"Falha ao processar {number}: {exc}")
            results.append(SendResult(number=number, sent=False, error=str(exc)))

    driver.quit()
    return results


def main():
    numbers = collect_numbers()
    if not numbers:
        print("Nenhum numero informado. Encerrando.")
        return

    message = input("Digite a mensagem a enviar: ").strip()
    if not message:
        print("Mensagem vazia. Encerrando.")
        return

    results = run_automation(numbers, message)
    invalid = [r.number for r in results if not r.sent]
    if invalid:
        print("Numeros nao encontrados:")
        for num in invalid:
            print(num)


if __name__ == "__main__":
    main()
