from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup

import os

app = Flask(__name__)

# Your Line Bot's Channel Access Token and Channel Secret
LINE_CHANNEL_ACCESS_TOKEN = 'W1iFrhuHEPdo8z9ewYqvRKCyFjHWlrlqHkoaJ98nO7diOjgiBPlIrPJqmGJhjj4mOVKNxhSLbW0AYvDc0WsAJZ7IymPR1rvvlP8jyXLwo6aZUyAtnkIhD5t15U5kLVX/qW94ubH5WSyhpPnhLvxzywdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = 'd5cd857c17c8ff9466f3f7817a5980b8'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# WebDriver settings
driver = webdriver.Chrome()

def search(ingredient):
    url = "https://icook.tw/"
    driver.get(url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "search-input")))
    search_box = driver.find_element(By.CLASS_NAME, "search-input")
    search_box.clear()
    search_box.send_keys(ingredient)
    search_box.send_keys(Keys.RETURN)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "browse-recipe-card")))
    original_html = driver.page_source
    return original_html

def progress_bar(percentage, length):
    if percentage < 0:
        percentage = 0
    elif percentage > 100:
        percentage = 100
    filled_length = int(length * percentage // 100)
    bar = "■" * filled_length + "□" * (length - filled_length)
    return f"|{bar}|"

def get_result(original_html, search_ingredient):
    soup = BeautifulSoup(original_html, "html.parser")
    recipe_list = []
    for i in range(2):
        recipe_items = soup.find_all("li", class_="browse-recipe-item")
        for recipe in recipe_items:
            link_tag = recipe.find("a", class_="browse-recipe-link")
            if link_tag and link_tag.has_attr("href"):
                link = link_tag["href"]
                title = recipe.find('h2').get_text(strip=True)
                ingredients = recipe.find('p').get_text(strip=True)
                likes_elem = recipe.select_one('li.browse-recipe-meta-item[data-title*="讚"]')
                time_elem = recipe.select_one('li.browse-recipe-meta-item[data-title*="烹飪時間"]')
                like_count = 0
                cook_time = "未知"
                if likes_elem:
                    likes_text = likes_elem.get_text(strip=True).replace('讚', '').strip()
                    if likes_text.isdigit():
                        like_count = int(likes_text)
                if time_elem:
                    cook_time = time_elem.get_text(strip=True).replace('烹飪時間', '').strip()
                recipe_list.append({
                    "title": title,
                    "ingredients": list(ingredients.split("、")),
                    "likes": like_count,
                    "cook_time": cook_time,
                    "link": f"https://icook.tw{link}"
                })
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, 'li.pagination-tab.page--next a.pagination-tab-link')
            next_button.click()
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "browse-recipe-card")))
            original_html = driver.page_source
            soup = BeautifulSoup(original_html, "html.parser")
        except Exception as e:
            break
    recipe_list.sort(key=lambda x: x["likes"], reverse=True)
    top_recipes = recipe_list[:50]
    search_ingredient = list(search_ingredient.strip().split(" "))
    results = []
    for idx, recipe in enumerate(top_recipes, 1):
        complete_percent = int(
            round(len(search_ingredient) / len(recipe["ingredients"]), 2) * 100
        )
        left = len(recipe["ingredients"]) - len(search_ingredient)
        result = (f"""{idx}. {recipe['title']}
    {recipe['likes']} 次讚 - 烹飪時間: {recipe['cook_time']}
    材料完成度： {complete_percent} % Complete - 差{left}樣 
    {progress_bar(complete_percent, length=10)}
    {'、'.join(recipe["ingredients"])}
""")
        results.append(result)
    return top_recipes, results

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    ingredient = event.message.text
    if ingredient.lower() == "不知道":
        response_text = "請輸入一個食材來搜尋食譜。"
    else:
        original_html = search(ingredient)
        top_recipes, results = get_result(original_html, ingredient)
        response_text = "\n".join(results[:5])  # 只顯示前5個結果
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_text)
    )

if __name__ == "__main__":
    app.run(port=5000)
