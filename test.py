import PySimpleGUI as sg
from dotenv import load_dotenv
config = load_dotenv()
import google.generativeai as genai
import re
import os

import google.generativeai as genai

HEALTH = 10
FOOD = 10

RESPONSE_MEMORY = []

PROMPT="You are the dungeon master of a game about taking care of a Rudolf. The player is Santa. The player will be given tasks to perform that will affect the health and food of the reindeer. The aim is to protect the reindeer. The player will have two stats about the reindeer's life and the food. Say [health - or +] or [food - or +] based on the events and actions of the player each turn. The number of -'s and +'s are indicative of how many units of health or food it loses. You will pose a challenging scenario if you think the player hasn't done anything eventful.\n" 

genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel("gemini-1.5-flash")

def parse_response(response):
    try:
        health_change = 0
        food_change = 0
        response_text = response.text.lower()

        health_match = re.search(r"\[health ([+-]+)\]", response_text)
        if health_match:
            health_change = health_match.group(1).count('+') - health_match.group(1).count('-')

        food_match = re.search(r"\[food ([+-]+)\]", response_text)
        if food_match:
            food_change = food_match.group(1).count('+') - food_match.group(1).count('-')

    except Exception as e:
        print("Error parsing response:", e)
        health_change = 0
        food_change = 0

    return health_change, food_change



def update_response_memory(new_memory):
    global RESPONSE_MEMORY
    RESPONSE_MEMORY.append(new_memory)
    if len(RESPONSE_MEMORY) > 3:
        RESPONSE_MEMORY.pop(0)

def talk_to_gemini(player_response):
    global HEALTH
    global FOOD
    global RESPONSE_MEMORY

    CRAFTED_PROMPT = f"PROMPT: {PROMPT}\n" + f'Past 3 moves: {" ".join(RESPONSE_MEMORY)}' + f"\n Player's New Move: {player_response}\n"

    response = model.generate_content(CRAFTED_PROMPT)

    print(response)

    health_change, food_change = parse_response(response)
    HEALTH += health_change
    FOOD += food_change

    update_response_memory(response.text)

    return response.text

sg.theme('DarkRed')

layout = [
        [sg.Push(), sg.Text("Santa & Rudolph:\nThe Simulator", font=("Calibri", 28), justification="center"), sg.Push()],
        [sg.Image(filename="reindeer.png", size=(80,80), subsample=4), sg.Text("Rudolf", font=("Calibri", 18)), sg.Text(f"Health: {HEALTH} | Food: {FOOD}", key="Rudolf", font=("Calibri", 14)), sg.Push()],
        [sg.Push()],
        [sg.Push(), sg.Text("The Dungeon Master Says..."), sg.Push()],
        [sg.Push(), sg.Text("You are Santa. Your goal is to keep your reindeer happy and fed while you distribute gifts to the children of the world.",key='-GEMINI_RESPONSE-', font=("Calibri", 13), size=(100,20), justification="center"), sg.Push()],
        [sg.Push()],
        [sg.Push(), sg.Text("Your Response", font=("Calibri", 16)), sg.Push()],
        [sg.Push(), sg.Input(key='-PLAYER_RESPONSE-', size=(100,100)), sg.Push(), sg.Button('Submit', key="submit_answer")],
        [sg.Push()],
        #[sg.Push(), sg.Text("Game Results: You're doing fine. Keep going.", key="-GAME_RESULTS-"), sg.Push()],
]

window = sg.Window('Santa\'s Reindeer Predicament', layout, icon="christmashat.ico")

while True:

    event, values = window.read()

    if event == sg.WIN_CLOSED or event == 'Cancel':
        break

    elif event == "submit_answer":

        response = talk_to_gemini(values["-PLAYER_RESPONSE-"])

        window["-GEMINI_RESPONSE-"].update(response)
        window["-PLAYER_RESPONSE-"].update("")
        window["Rudolf"].update(f"Health: {HEALTH} | Food: {FOOD}")

window.close()

layout = [[sg.Image(sg.desktop.test.reindeer.png)]]