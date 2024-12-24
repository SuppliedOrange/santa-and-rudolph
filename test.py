import PySimpleGUI as sg
import json
import os
from dotenv import load_dotenv
import google.generativeai as genai
import re

INITIAL_STATS = {
    'health': 10,
    'food': 10,
    'energy': 10,
    'morale': 10,
    'training': 5
}
MAX_STATS = 15
MIN_STATS = 0
ACTIONS_TO_WIN = 20

PROMPT = """You are the dungeon master of a challenging game about preparing Rudolf for Christmas delivery. Track these stats, showing changes based on player actions:
- Health: Physical condition
- Food: Nourishment level
- Energy: Stamina for activities
- Morale: Mental state
- Training: Flight skills

For example [health ++] means health increased by 2 units, [food ---] means food decreased by 3 units.

Include weather after each action:
[weather: blizzard/rain/clear/windy]

Create consequences where actions affect multiple stats. Examples:
- Training flight: [training ++] [energy --] [food -]
- Feeding treats: [food ++] [morale +] [training -]
- Rest in stable: [energy ++] [morale -] [training -]

Add [progress] when player makes meaningful choices.

Frequently award achievements [achievement: name] for:
- Bad Weather? No Problem: Handle blizzard well
- Cracked at this game: Have all stats above 10
- Pokemon trainers bow to me: Get training above 13
- Crushed skull? No problem: Recover from 1 health
- Please.. give me rest: Have rudolph be very tired and hungry
- Spoilt Reindeer: Have training low, but comforting stats high
- I make excellent choices: Make good choices consequetively
- Euphoria, and it's not cocaine!: Boost morale significantly in one turn
- I'm built like the terminator, baby: Have training and energy above 11

You may come up with your own achievements on the fly. Come up with wity names for them like mentioned above.

Each response should include:
Description of action results, Stat changes, Weather status and Achievement check
Do not use \*\* to bold text.

If any stat falls to 0, it's game over.

Consider the context of previous actions when responding."""

class GameState:
    def __init__(self):
        self.stats = INITIAL_STATS.copy()
        self.actions_taken = 0
        self.history = []
        self.game_over = False
        self.achievements = self.load_achievements()
        self.weather = 'normal'

    def load_achievements(self):
        try:
            with open('achievements.json', 'r') as f:
                return set(json.load(f)['achievements'])
        except:
            return set()

    def save_achievements(self):
        with open('achievements.json', 'w') as f:
            json.dump({'achievements': list(self.achievements)}, f)

    def add_achievement(self, achievement):
        self.achievements.add(achievement)
        self.save_achievements()

def parse_response(response):
    response_text = response.text.lower()
    changes = {stat: 0 for stat in INITIAL_STATS.keys()}
    achievements = set()
    weather = 'normal'
    progress = '[progress]' in response_text
    
    for stat in INITIAL_STATS.keys():
        match = re.search(fr"\[{stat} ([+-]+)\]", response_text)
        if match:
            changes[stat] = match.group(1).count('+') - match.group(1).count('-')
    
    weather_match = re.search(r"\[weather: (\w+)\]", response_text)
    if weather_match:
        weather = weather_match.group(1)
    
    achievement_matches = re.finditer(r"\[achievement: (.+?)\]", response_text)
    achievements = {match.group(1) for match in achievement_matches}
    
    return changes, weather, achievements, progress

def update_stats(game_state, changes, weather, progress):
    weather_effects = {
        'blizzard': {'health': -1, 'energy': -1},
        'rain': {'morale': -1, 'training': -1},
        'windy': {'training': -1}
    }
    
    if weather in weather_effects:
        for stat, change in weather_effects[weather].items():
            changes[stat] = changes.get(stat, 0) + change
    
    for stat, change in changes.items():
        game_state.stats[stat] = min(max(game_state.stats[stat] + change, MIN_STATS), MAX_STATS)
    
    game_state.weather = weather
    if progress:
        game_state.actions_taken += 1
    
    if any(value <= 0 for value in game_state.stats.values()):
        game_state.game_over = True
        return "Game Over: Rudolf isn't ready for Christmas delivery!"
    elif game_state.actions_taken >= ACTIONS_TO_WIN:
        if game_state.stats['training'] >= 10:
            game_state.game_over = True
            return "Victory! Rudolf is prepared for Christmas Eve!"
        else:
            game_state.game_over = True
            return "Game Over: Rudolf's training wasn't sufficient!"
    return None

def create_tabs_layout(game_state):
    main_tab = [
        [sg.Text(f"Actions Remaining: {ACTIONS_TO_WIN - game_state.actions_taken}", key="Actions")],
        [sg.Text("Stats:", font=("Calibri", 14))],
        [sg.Text("", key="Stats", size=(60, 5))],
        [sg.Text("Current Weather:", font=("Calibri", 12)), sg.Text("", key="Weather")],
        [sg.Text("The Dungeon Master Says...", font=("Calibri", 14))],
        [sg.Multiline("", key='-GEMINI_RESPONSE-', size=(60, 10), disabled=True)],
        [sg.Text("Your Action:", font=("Calibri", 12))],
        [sg.Input(key='-PLAYER_RESPONSE-', size=(60, 1))],
        [sg.Button('Take Action', key="submit_answer")]
    ]
    
    history_tab = [
        [sg.Multiline("", key='-HISTORY-', size=(60, 20), disabled=True)]
    ]
    
    achievements_tab = [
        [sg.Text("Achievements Earned:", font=("Calibri", 14))],
        [sg.Listbox(values=sorted(list(game_state.achievements)), 
                   size=(60, 20), 
                   key='-ACHIEVEMENTS-')]
    ]
    
    return [[sg.TabGroup([[
        sg.Tab('Game', main_tab),
        sg.Tab('History', history_tab),
        sg.Tab('Achievements', achievements_tab)
    ]])]]

def update_display(window, game_state, response=""):
    stats_text = "\n".join([f"{stat.title()}: {value}/{MAX_STATS}" 
                           for stat, value in game_state.stats.items()])
    window["Stats"].update(stats_text)
    window["Weather"].update(game_state.weather)
    window["Actions"].update(f"Actions Remaining: {ACTIONS_TO_WIN - game_state.actions_taken}")
    
    if response:
        window["-GEMINI_RESPONSE-"].update(response)
        game_state.history.append(f"\n--- Action {game_state.actions_taken} ---\n"
                                f"Player: {window['-PLAYER_RESPONSE-'].get()}\n"
                                f"Response: {response}")
        window["-HISTORY-"].update("\n".join(game_state.history))
        window["-PLAYER_RESPONSE-"].update("")

def talk_to_gemini(player_response, game_state):
    # Build context from history
    if game_state.history:
        history_entries = []
        for idx, entry in enumerate(game_state.history[-3:]):
            try:
                player_part = entry.split('Player: ')[1].split('\n')[0]
                response_part = entry.split('Response: ')[1]
                history_entries.append(f"Turn {idx+1}:\nPlayer: {player_part}\nResult: {response_part}")
            except IndexError:
                continue
        context = "\n".join(history_entries)
    else:
        context = "Game Start"
    
    prompt = f"""{PROMPT}

Recent History:
{context}

Current Stats: {game_state.stats}
Weather: {game_state.weather}
Player's Action: {player_response}
"""
    return model.generate_content(prompt)

def main():
    sg.theme('DarkRed')
    game_state = GameState()
    
    while True:
        window = sg.Window('Santa\'s Reindeer Predicament', 
                        [
                            [sg.Push(), sg.Text("Santa & Rudolf: The Simulator", font=("Calibri", 28)), sg.Push()],
                            [sg.Image(filename="reindeer.png", size=(80, 80), subsample=4)],
                            *create_tabs_layout(game_state),
                            [sg.Button('Restart Game', key="restart_game"), sg.Button('Quit', key="quit_game")],
                            [sg.Text("", key="-GAME_STATUS-", text_color='yellow')]
                        ], 
                        icon="christmashat.ico",
                        finalize=True)
        
        update_display(window, game_state)
        
        while True:
            event, values = window.read()
            
            if event in (sg.WIN_CLOSED, 'quit_game'):
                window.close()
                return
                
            elif event == "restart_game":
                window.close()
                game_state = GameState()
                break
                
            elif event == "submit_answer" and not game_state.game_over:
                response = talk_to_gemini(values['-PLAYER_RESPONSE-'], game_state)
                changes, weather, new_achievements, progress = parse_response(response)
                
                for achievement in new_achievements:
                    game_state.add_achievement(achievement)
                
                game_over_message = update_stats(game_state, changes, weather, progress)
                update_display(window, game_state, response.text)
                window['-ACHIEVEMENTS-'].update(sorted(list(game_state.achievements)))
                
                if game_over_message:
                    window["-GAME_STATUS-"].update(game_over_message)

if __name__ == "__main__":
    load_dotenv()
    genai.configure(api_key=os.environ['GEMINI_API_KEY'])
    model = genai.GenerativeModel("gemini-1.5-flash")
    main()
