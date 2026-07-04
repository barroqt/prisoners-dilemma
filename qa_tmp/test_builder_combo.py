"""QA: builder 'Start from' combobox — open, search, keyboard select, seed load."""
from playwright.sync_api import sync_playwright

OUT = "qa_tmp"
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto("http://127.0.0.1:8765/")
    page.click('button[data-view="builder"]')

    page.click("#builder-start-input")
    page.wait_for_selector(".combo-item")
    print("items when open:", page.locator(".combo-item").count())
    page.screenshot(path=f"{OUT}/combo-open.png")

    page.fill("#builder-start-input", "pav")
    page.wait_for_timeout(150)
    page.screenshot(path=f"{OUT}/combo-search.png")
    page.keyboard.press("Enter")
    page.wait_for_timeout(700)  # compile round-trip
    page.screenshot(path=f"{OUT}/combo-loaded.png")
    print("name field:", page.input_value("#builder-name"))
    print("rule cards:", page.locator("#builder-rules .rule-card").count())

    # approximate strategy via keyboard
    page.fill("#builder-start-input", "yama")
    page.wait_for_timeout(150)
    page.keyboard.press("Enter")
    page.wait_for_timeout(700)
    print("name after yamachi:", page.input_value("#builder-name"))
    print("desc after yamachi:", page.input_value("#builder-desc"))

    # escape closes; arrow navigation moves highlight
    page.fill("#builder-start-input", "t")
    page.wait_for_timeout(150)
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    active = page.locator(".combo-item.active .combo-name").inner_text()
    print("active after 2x ArrowDown:", active)
    page.keyboard.press("Escape")
    print("list hidden after Escape:", page.locator("#builder-start-list").is_hidden())
    b.close()

print("console errors:", errors or "none")
