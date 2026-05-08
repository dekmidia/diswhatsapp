import os
import time
from dataclasses import dataclass

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, ElementClickInterceptedException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


ACTIVE_DRIVER = None


def stop_automation():
    global ACTIVE_DRIVER
    if ACTIVE_DRIVER:
        try:
            ACTIVE_DRIVER.quit()
        except Exception:
            pass
        ACTIVE_DRIVER = None



SEARCH_SELECTORS = [
    (By.XPATH, "//input[@aria-label='Pesquisar nome ou número']"),
    (By.XPATH, "//input[@aria-label='Pesquisar ou começar uma nova conversa']"),
    (By.XPATH, "//input[@title='Pesquisar ou começar uma nova conversa']"),
    (By.XPATH, "//input[contains(@aria-label,'Pesquisar')]"),
    (By.XPATH, "//div[@id='side']//div[@contenteditable='true' and @role='textbox']"),
    (By.XPATH, "//div[@contenteditable='true' and @role='textbox' and contains(@aria-label,'Pesquisar')]"),
    (By.XPATH, "//div[@contenteditable='true' and contains(@aria-placeholder,'Pesquisar')]"),
    (By.XPATH, "//div[@contenteditable='true' and @role='textbox']"),
    (By.XPATH, "//div[@contenteditable='true']"),
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
    (By.XPATH, "//div[@contenteditable='true' and @role='textbox' and contains(@aria-label,'mensagem')]"),
    (By.XPATH, "//div[@contenteditable='true' and @role='textbox' and contains(@aria-label,'message')]"),
    (By.XPATH, "//footer//div[@contenteditable='true' and @role='textbox']"),
    (By.CSS_SELECTOR, "footer .copyable-text.selectable-text[contenteditable='true']"),
]

SEND_BUTTON_SELECTORS = [
    (By.XPATH, "//span[@data-icon='send']"),
    (By.XPATH, "//button/span[@data-icon='send']"),
    (By.XPATH, "//button[@aria-label='Enviar']"),
    (By.XPATH, "//button[@aria-label='Send']"),
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


def wait_for_any(driver, selectors, timeout=30, log_callback=None):
    if log_callback is None:
        log_callback = lambda x: None

    end = time.time() + timeout
    last_error = None
    log_callback(f"Aguardando elementos ({timeout}s)...")
    
    while time.time() < end:
        # Tentar obter informacoes basicas da pagina para log
        try:
            title = driver.title
            log_callback(f"Status da pagina: '{title}'")
            
            # Debug extra: contar qualquer elemento editavel ou input
            editables = driver.find_elements(By.XPATH, "//*[@contenteditable='true'] | //input | //div[@role='textbox']")
            if editables:
                log_callback(f"Debug: {len(editables)} campos interativos detectados na pagina.")
                # Logar detalhes do primeiro para entender o que ele é
                try:
                    el = editables[0]
                    log_callback(f"Amostra: Tag={el.tag_name}, Role={el.get_attribute('role')}, Label={el.get_attribute('aria-label')}")
                except: pass
            else:
                log_callback("Debug: Nenhum campo interativo detectado ainda.")
                # Tentar ver se o app principal está carregado
                apps = driver.find_elements(By.ID, "app")
                if apps:
                    log_callback("Debug: Container '#app' encontrado, mas sem campos de texto.")
        except Exception as e:
            log_callback(f"Erro ao ler status: {e}")
            pass

        for by, sel in selectors:
            try:
                elements = driver.find_elements(by, sel)
                if elements:
                    log_callback(f"Tentando {sel}: {len(elements)} elementos encontrados.")
                for el in elements:
                    if el.is_displayed():
                        log_callback(f"Elemento visivel encontrado: {sel}")
                        return el
                    else:
                        log_callback(f"Elemento encontrado mas NÃO está visível: {sel}")
            except Exception as exc:
                last_error = exc
        time.sleep(2)
    raise TimeoutException("Timeout waiting for element") from last_error


def has_no_results(driver):
    candidates = driver.find_elements(By.XPATH, NO_RESULTS_XPATH)
    return any(el.is_displayed() for el in candidates)


def normalize_number(raw):
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits


def click_new_chat(driver, log_callback=None):
    try:
        button = wait_for_any(driver, NEW_CHAT_SELECTORS, timeout=10, log_callback=log_callback)
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


def send_message(driver, number, message, log_callback=None):
    for _ in range(2):
        try:
            click_new_chat(driver, log_callback=log_callback)
            search_box = wait_for_any(driver, SEARCH_SELECTORS, timeout=60, log_callback=log_callback)
            try:
                search_box.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", search_box)
            
            search_box.send_keys(Keys.CONTROL, "a")
            search_box.send_keys(Keys.BACKSPACE)
            type_slowly(search_box, number, delay=0.05)
            time.sleep(3) # Aguardar resultados da busca
            
            # Tentar clicar no primeiro contato que aparecer
            try:
                contact_xpath = "//div[@id='side']//div[contains(@style, 'z-index')]//div[@role='listitem']"
                contacts = driver.find_elements(By.XPATH, contact_xpath)
                if contacts:
                    if log_callback: log_callback("Contato encontrado na lista, clicando...")
                    contacts[0].click()
                else:
                    if log_callback: log_callback("Pressionando Enter como fallback para abrir chat.")
                    search_box.send_keys(Keys.ENTER)
            except Exception:
                search_box.send_keys(Keys.ENTER)
            
            time.sleep(2)
            break
        except StaleElementReferenceException:
            time.sleep(1)
            continue

    if has_no_results(driver):
        if log_callback: log_callback(f"Resultado não encontrado para {number}")
        return False

    message_box = wait_for_any(driver, MESSAGE_SELECTORS, timeout=30, log_callback=log_callback)
    message_box.click()
    time.sleep(1)
    
    lines = message.splitlines() or [""]
    for index, line in enumerate(lines):
        if line:
            message_box.send_keys(line)
        if index < len(lines) - 1:
            message_box.send_keys(Keys.SHIFT, Keys.ENTER)
    
    time.sleep(1)
    message_box.send_keys(Keys.ENTER)
    
    # Fallback: verificar se a caixa ainda tem texto (o Enter falhou em enviar)
    # IMPORTANTE: só clicar no botão de enviar se a caixa ainda contiver texto
    # pois clicar quando já enviado causa reaction na mensagem
    try:
        time.sleep(1.5)
        remaining_text = message_box.text or message_box.get_attribute("textContent") or ""
        if remaining_text.strip():
            if log_callback: log_callback("Texto ainda na caixa após Enter. Clicando no botão de enviar...")
            send_btn = driver.find_elements(By.XPATH, "//footer//span[@data-icon='send'] | //footer//button[@aria-label='Enviar']")
            if send_btn and send_btn[0].is_displayed():
                send_btn[0].click()
        else:
            if log_callback: log_callback("Mensagem de texto enviada com sucesso.")
    except:
        pass
        
    return True
def send_image_attachment(driver, image_path, log_callback=None):
    if log_callback: log_callback(f"Preparando envio de imagem: {image_path}")
    try:
        abs_path = os.path.abspath(image_path)
        # ---- PASSO 1: Copiar imagem para o clipboard (Windows) ----
        # Abordagem: colar imagem diretamente no campo de mensagem via Ctrl+V.
        # O WhatsApp Web trata imagens coladas como fotos normais (não figurinha).
        if log_callback: log_callback("Copiando imagem para o clipboard...")
        try:
            import subprocess
            safe_path = abs_path.replace("\\", "\\\\")
            ps_clip = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "Add-Type -AssemblyName System.Drawing; "
                f"$img = [System.Drawing.Image]::FromFile('{safe_path}'); "
                "[System.Windows.Forms.Clipboard]::SetImage($img); "
                "$img.Dispose();"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_clip],
                timeout=10, check=False, capture_output=True, text=True
            )
            if result.returncode != 0:
                raise Exception(f"PS erro: {result.stderr}")
            if log_callback: log_callback("Imagem copiada para o clipboard com sucesso.")
        except Exception as e:
            if log_callback: log_callback(f"Erro ao copiar para clipboard: {e}")
            raise

        # ---- PASSO 2: Colar no campo de mensagem ----
        if log_callback: log_callback("Colando imagem no campo de mensagem via Ctrl+V...")
        msg_box = wait_for_any(driver, [
            (By.XPATH, "//div[@contenteditable='true' and @role='textbox' and contains(@aria-label,'mensagem')]"),
            (By.XPATH, "//div[@contenteditable='true' and @role='textbox']"),
        ], timeout=10, log_callback=log_callback)
        msg_box.click()
        time.sleep(0.5)
        msg_box.send_keys(Keys.CONTROL, 'v')
        if log_callback: log_callback("Ctrl+V executado.")

        # ---- PASSO 4: Aguardar a tela de prévia aparecer ----
        if log_callback: log_callback("Aguardando tela de prévia da imagem...")
        time.sleep(5)

        # ---- PASSO 5: Enviar pela prévia ----
        sent = False

        # Estratégia A: Selenium nativo — botão com aria-label "Enviar" diretamente
        if log_callback: log_callback("Estratégia A: buscando botão Enviar via Selenium...")
        send_selectors = [
            (By.XPATH, "//*[@aria-label='Enviar']"),
            (By.XPATH, "//*[@aria-label='Send']"),
            (By.XPATH, "//button[@aria-label='Enviar']"),
            (By.XPATH, "//div[@role='button' and @aria-label='Enviar']"),
            (By.XPATH, "//span[@role='button' and @aria-label='Enviar']"),
        ]
        for by, sel in send_selectors:
            try:
                els = driver.find_elements(by, sel)
                for el in els:
                    try:
                        driver.execute_script("arguments[0].click();", el)
                        if log_callback: log_callback(f"Botão Enviar clicado (Selenium JS): {sel}")
                        sent = True
                        break
                    except: continue
                if sent: break
            except: continue

        # Estratégia B: JS que encontra o elemento mais à direita e embaixo (o botão ">")
        if not sent:
            if log_callback: log_callback("Estratégia B: JS por posição (canto inferior direito)...")
            js_click_bottomright = """
                var allElems = document.querySelectorAll('div[role="button"], span[role="button"], button');
                var bestEl = null;
                var maxScore = 0;
                var debug = [];
                for (var i = 0; i < allElems.length; i++) {
                    var el = allElems[i];
                    var rect = el.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) continue;
                    var label = (el.getAttribute('aria-label') || '').toLowerCase();
                    if (label.includes('emoji') || label.includes('figurinha') || 
                        label.includes('sticker') || label.includes('fechar') || 
                        label.includes('cancel') || label.includes('close')) continue;
                    var score = rect.right + rect.bottom;
                    debug.push(label + '@' + Math.round(rect.right) + ',' + Math.round(rect.bottom));
                    if (score > maxScore) { maxScore = score; bestEl = el; }
                }
                if (bestEl) {
                    bestEl.click();
                    var r = bestEl.getBoundingClientRect();
                    return 'OK:' + (bestEl.getAttribute('aria-label') || 'no-label') + '@right=' + Math.round(r.right) + ',bottom=' + Math.round(r.bottom) + '|debug:' + debug.slice(-5).join(';');
                }
                return 'FAIL:' + debug.join(';');
            """
            start_time = time.time()
            while time.time() - start_time < 12:
                try:
                    result = driver.execute_script(js_click_bottomright)
                    if log_callback: log_callback(f"JS B resultado: {result}")
                    if result and result.startswith("OK:"):
                        sent = True
                        break
                except Exception as e:
                    if log_callback: log_callback(f"Erro JS B: {e}")
                time.sleep(2)

        # Estratégia C: Enter no body com verificação CORRETA (checa se o botão Enviar sumiu)
        if not sent:
            try:
                if log_callback: log_callback("Estratégia C: Enter no documento...")
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ENTER)
                time.sleep(2)
                # Verificação correta: o botão de Enviar ainda está visível?
                still_has_send = driver.find_elements(By.XPATH, "//*[@aria-label='Enviar'] | //*[@aria-label='Send']")
                if not still_has_send:
                    if log_callback: log_callback("Prévia fechou após Enter. Enviado.")
                    sent = True
                else:
                    if log_callback: log_callback("Enter pressionado mas a prévia ainda está aberta.")
            except Exception as e:
                if log_callback: log_callback(f"Estratégia C falhou: {e}")

        if not sent:
            if log_callback: log_callback("AVISO: Todas as estratégias falharam. Imagem pode não ter sido enviada.")

        time.sleep(2)
        return sent

    except Exception as e:
        if log_callback: log_callback(f"Erro crítico no envio de imagem: {e}")
        return False


def run_automation(numbers, message, log_callback=None, image_path=None):
    global ACTIVE_DRIVER
    if log_callback is None:
        log_callback = print

    log_callback("Iniciando navegador...")
    try:
        driver = build_driver()
        ACTIVE_DRIVER = driver
    except Exception as exc:
        log_callback(f"Falha ao iniciar o navegador: {exc}")
        return []

    try:
        driver.get("https://web.whatsapp.com")
        log_callback("Escaneie o QR Code no WhatsApp Web e aguarde a tela carregar.")

        try:
            wait_for_any(driver, SEARCH_SELECTORS, timeout=180, log_callback=log_callback)
            log_callback("WhatsApp carregado com sucesso! Iniciando envios...")
        except TimeoutException:
            log_callback("Nao foi possivel encontrar a caixa de pesquisa. Verifique se voce esta logado.")
            return []

        results = []
        for number in numbers:
            try:
                sent = send_message(driver, number, message, log_callback=log_callback)
                if sent:
                    if image_path:
                        time.sleep(2) # Pequena pausa entre texto e imagem
                        sent_image = send_image_attachment(driver, image_path, log_callback)
                        if sent_image:
                            log_callback(f"Imagem enviada para {number}.")
                        else:
                            log_callback(f"Aviso: Falha ao enviar imagem para {number}, mas texto foi enviado.")
                    
                    log_callback(f"Fluxo concluído para {number}. Aguardando intervalo de segurança (30s)...")
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
        return results
    finally:
        stop_automation()


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
