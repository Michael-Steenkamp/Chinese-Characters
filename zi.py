import json
import os
import random
import sys
import time
from typing import Any, Dict, List, Tuple

# ==========================================
# -------- Penalties and Rewards -----------
# ==========================================
# (Adapted from hsk-vocab.py)
# Controls how quickly the weight for a character changes.
PENALTY_HINT = 1.5
PENALTY_SKIP = 3.0
PENALTY_INCORRECT = 4.0
REWARD_STREAK = 0.25  # Bonus per item in streak
REWARD_TIME = 0.5   # Bonus for beating avg time
REWARD_CORRECT = 1.0  # Base reward for correct
MAX_WEIGHT = 10.0     # Weight for new/unseen characters
MIN_WEIGHT = 0.01     # Weight for "mastered" characters

# ==========================================
# ------------ File Paths ------------------
# ==========================================
JSON_DIR = "json"
PROGRESS_DIR = "progress"
DATA_FILE_PATH = os.path.join(JSON_DIR, "zi.json")
PROGRESS_FILE_PATH = os.path.join(PROGRESS_DIR, "zi-progress.json")

# ==========================================
# ------------ Global Flags ----------------
# ==========================================
# These will be set by user input in the main menu
g_random_mode = True
g_show_examples = True # This is your "meta data" option

# ==========================================
# ------------ Global Variables ------------
# ==========================================
g_in_order_index = 0  # Used only if g_random_mode is False

# ==========================================
# ----------------- Icons ------------------
# ==========================================
# (Adapted from hsk-vocab.py)
icon_proficiency = "🧠"
icon_time = "  "
icon_streak = "  "
icon_accuracy = "  "
icon_seen = "  "
icon_mastery = "⭐"
icon_warning = "⚠"
icon_correct = "✔ "
icon_incorrect = "✖ "

# --- ANSI Colors for better terminal output ---
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# ==========================================
# ----------- Helper Functions -------------
# ==========================================
def press_enter_continue():
    input("Press Enter To Continue...")
    clear_terminal()

def clear_terminal():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def load_data(file_path: str, is_progress_file: bool = False) -> List[Dict[str, Any]]:
    """
    Loads data from the specified JSON file.
    Creates the file and directory if they don't exist.
    """
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError as e:
            print(f"{bcolors.FAIL}Error creating directory {directory}: {e}{bcolors.ENDC}")
            return []

    if not os.path.isfile(file_path):
        if is_progress_file:
            print(f"{bcolors.WARNING}Progress file not found. Will create new: {file_path}{bcolors.ENDC}")
        else:
            print(f"{bcolors.WARNING}Data file not found. Creating new: {file_path}{bcolors.ENDC}")
        save_data([], file_path)  # Create an empty file
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # --- FIX ---
            # Ensure the loaded data is a list.
            if not isinstance(data, list):
                print(f"{bcolors.FAIL}Error: Data in {file_path} is not a list.{bcolors.ENDC}")
                print(f"{bcolors.WARNING}Resetting file to an empty list. Old data might be lost.{bcolors.ENDC}")
                save_data([], file_path)
                return []
            # --- END FIX ---
                
            return data
    except json.JSONDecodeError:
        print(f"{bcolors.FAIL}Error: Could not decode JSON from {file_path}.{bcolors.ENDC}")
        return []
    except Exception as e:
        print(f"{bcolors.FAIL}An error occurred loading data: {e}{bcolors.ENDC}")
        return []

def save_data(data: List[Dict[str, Any]], file_path: str):
    """
    Saves the provided data list to the specified JSON file.
    """
    try:
        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"{bcolors.FAIL}Error saving data to {file_path}: {e}{bcolors.ENDC}")

# ==========================================
# -------- Progress Functions --------------
# ==========================================

def get_default_progress_item(character: str) -> Dict[str, Any]:
    """Creates a new progress item with default max weight."""
    return {
        "character": character,
        "weight": MAX_WEIGHT,
        "streak": 0,
        "avg_time": 0.0,
        "total_time": 0.0,
        "attempts": 0,
        "correct": 0
    }

def load_and_sync_progress(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Loads progress from file.
    Syncs progress with the main data list to add new items
    or remove old ones.
    """
    progress_data = load_data(PROGRESS_FILE_PATH, is_progress_file=True)
    
    # Create a lookup map for existing progress
    progress_map = {p['character']: p for p in progress_data}
    
    # Get all characters that *should* exist
    data_chars = {item['character'] for item in data}
    
    synced_progress = []
    has_changed = False

    # 1. Add/update items from the main data file
    for item in data:
        char = item['character']
        if char in progress_map:
            synced_progress.append(progress_map[char])
        else:
            # New character was added to zi.json, add to progress
            print(f"{bcolors.OKCYAN}New character '{char}' found. Adding to progress...{bcolors.ENDC}")
            synced_progress.append(get_default_progress_item(char))
            has_changed = True

    # 2. Check for items to remove
    final_progress = []
    for prog_item in synced_progress:
        if prog_item['character'] in data_chars:
            final_progress.append(prog_item)
        else:
            # Character was removed from zi.json, remove from progress
            print(f"{bcolors.WARNING}Character '{prog_item['character']}' not in zi.json. Removing from progress...{bcolors.ENDC}")
            has_changed = True

    if has_changed:
        save_data(final_progress, PROGRESS_FILE_PATH)
        print(f"{bcolors.OKGREEN}Progress file synced.{bcolors.ENDC}")

    return final_progress

# ==========================================
# -------- Add Entry Function --------------
# ==========================================

def add_new_entry(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Guides the user to add a new character entry.
    (Adapted from original zi.py)
    """
    print(f"\n{bcolors.HEADER}--- Add New Character Entry ---{bcolors.ENDC}")
    print(f"{bcolors.OKCYAN}Enter 'q' at any time to cancel and return to menu.{bcolors.ENDC}")

    try:
        # Get main character info
        character = input(f"{bcolors.OKBLUE}Enter Character (e.g., 你): {bcolors.ENDC}").strip()
        if character == 'q': return data
        if not character:
             print(f"{bcolors.FAIL}Character cannot be empty.{bcolors.ENDC}")
             return data
        
        # Check for duplicates
        if any(item['character'] == character for item in data):
            print(f"{bcolors.FAIL}Error: Character '{character}' already exists in the database.{bcolors.ENDC}")
            return data

        description = input(f"{bcolors.OKBLUE}Enter Definition (e.g., you): {bcolors.ENDC}").strip()
        if description == 'q': return data

        pinyin_marks = input(f"{bcolors.OKBLUE}Enter Pinyin (tone marks) (e.g., nǐ): {bcolors.ENDC}").strip()
        if pinyin_marks == 'q': return data

        pinyin_numbers = input(f"{bcolors.OKBLUE}Enter Pinyin (tone numbers) (e.g., ni3): {bcolors.ENDC}").strip()
        if pinyin_numbers == 'q': return data

        examples = []
        
        # Loop to add example combinations
        while True:
            add_example = input(f"\n{bcolors.OKBLUE}Add an example combination? (y/n): {bcolors.ENDC}").strip().lower()
            if add_example == 'q': return data
            if add_example != 'y':
                break
                
            print(f"{bcolors.HEADER}--- Adding Example ---{bcolors.ENDC}")
            ex_word = input(f"{bcolors.OKBLUE}  Example Word (e.g., 你好): {bcolors.ENDC}").strip()
            if ex_word == 'q': return data

            ex_desc = input(f"{bcolors.OKBLUE}  Word Definition (e.g., hello): {bcolors.ENDC}").strip()
            if ex_desc == 'q': return data

            ex_pinyin_marks = input(f"{bcolors.OKBLUE}  Word Pinyin (marks) (e.g., nǐ hǎo): {bcolors.ENDC}").strip()
            if ex_pinyin_marks == 'q': return data

            ex_pinyin_numbers = input(f"{bcolors.OKBLUE}  Word Pinyin (numbers) (e.g., ni3 hao3): {bcolors.ENDC}").strip()
            if ex_pinyin_numbers == 'q': return data

            examples.append({
                "word": ex_word,
                "description": ex_desc,
                "pinyin_marks": ex_pinyin_marks,
                "pinyin_numbers": ex_pinyin_numbers
            })
            print(f"{bcolors.OKGREEN}Example added!{bcolors.ENDC}")

        new_entry = {
            "character": character,
            "description": description,
            "pinyin_marks": pinyin_marks,
            "pinyin_numbers": pinyin_numbers,
            "examples": examples
        }

        data.append(new_entry)
        save_data(data, DATA_FILE_PATH)
        
        print(f"\n{bcolors.OKGREEN}{bcolors.BOLD}Successfully added '{character}' to the database!{bcolors.ENDC}")
        print(f"{bcolors.OKCYAN}Progress file will be updated on next quiz start or main menu reload.{bcolors.ENDC}")
        return data

    except Exception as e:
        print(f"{bcolors.FAIL}An error occurred while adding entry: {e}{bcolors.ENDC}")
        return data

# ==========================================
# ----------- Quiz Logic -------------------
# ==========================================

def get_next_index(data_len: int, progress: List[Dict[str, Any]]) -> int:
    """
    Gets the index for the next quiz item.
    Either randomly (based on weights) or sequentially.
    (Adapted from hsk-vocab.py)
    """
    global g_in_order_index
    if g_random_mode:
        weights = [item["weight"] for item in progress]
        indices = list(range(data_len))
        selected_index = random.choices(indices, weights=weights, k=1)[0]
    else:
        selected_index = g_in_order_index
        g_in_order_index = (g_in_order_index + 1) % data_len
    return selected_index

def get_quiz_item_data(item: Dict[str, Any]) -> Tuple[List[str], List[str], str]:
    """Extracts the prompt, answer, and hint from a data item."""
    prompt = f"字: {bcolors.OKBLUE}{bcolors.BOLD}{item['character']}{bcolors.ENDC}"
    
    answer = [
        item.get("pinyin_marks", "").lower(),
        item.get("pinyin_numbers", "").lower()
    ]
    
    # Hint is the description
    hint = [item.get('description', 'No description available.')]

    return answer, hint, prompt


def reveal_answer_details(item: Dict[str, Any], show_examples: bool):
    """Prints the full details for a character."""
    print(f"  {bcolors.BOLD}Pinyin: {bcolors.OKGREEN}{item['pinyin_marks']}{bcolors.ENDC} ({bcolors.OKGREEN}{item['pinyin_numbers']}{bcolors.ENDC})")
    print(f"  {bcolors.BOLD}Definition: {bcolors.OKGREEN}{item['description']}{bcolors.ENDC}")

    if show_examples and item.get("examples"):
        print(f"{bcolors.WARNING}--- Example Combinations ---{bcolors.ENDC}")
        for ex in item["examples"]:
            print(f"  Word: {bcolors.OKCYAN}{ex['word']}{bcolors.ENDC}")
            print(f"    Pinyin: {ex['pinyin_marks']} ({ex['pinyin_numbers']})")
            print(f"    Definition: {ex['description']}")
            print("    " + "-" * 10)

def check_answer(user_input: str, answer_list: List[str]) -> bool:
    """Checks if the user's input matches any valid answer."""
    return user_input.lower() in answer_list

def display_item_metadata(prog_item: Dict[str, Any], orig_weight: float):
    """
    Shows the stats for the item that was just quizzed.
    (Adapted from hsk-vocab.py)
    """
    # Calculate "proficiency" for this single item (0-100%)
    weight_range = MAX_WEIGHT - MIN_WEIGHT
    new_proficiency = ((MAX_WEIGHT - prog_item['weight']) / weight_range) * 100.0
    old_proficiency = ((MAX_WEIGHT - orig_weight) / weight_range) * 100.0
    proficiency_change = new_proficiency - old_proficiency
    
    accuracy = (prog_item['correct'] / prog_item['attempts']) * 100.0 if prog_item['attempts'] > 0 else 0.0

    print("╔")
    print(f"║ {icon_accuracy} {accuracy:.2f}% ({prog_item['correct']} / {prog_item['attempts']})")
    print(f"║ {icon_proficiency} {new_proficiency:.2f}% ({'+' if proficiency_change > 0.0 else ''}{proficiency_change:.2f}%)")
    print(f"║ {icon_streak} {prog_item['streak']}")
    print(f"║ {icon_time} {prog_item['avg_time']:.2f}s avg")
    print("╚")


def run_quiz_for_item(item: Dict[str, Any], prog_item: Dict[str, Any], show_examples: bool, current_index: int, total_items: int) -> str:
    """
    Runs the full quiz logic for a single item.
    Handles input, checking, and weight updates.
    Returns a status string: "correct", "incorrect", "skipped", "quit".
    (Adapted from hsk-vocab.py)
    """
    if not g_random_mode:
        # Use current_index (which is 0-based) + 1 for display
        print(f"Item {current_index + 1}/{total_items} (Sequential Mode)")
        
    answer, hint, prompt = get_quiz_item_data(item)
    print(prompt)

    start_time = time.time()
    inpt = input(" Enter Pinyin: ").strip()
    end_time = time.time()

    elapsed_time = end_time - start_time
    orig_weight = prog_item['weight']

    # --- Handle special commands ---
    if inpt.lower() == "-q":
        print("Quitting session...")
        return "quit"
    if inpt.lower() == "-s":
        print(f"{bcolors.WARNING}Skipped.{bcolors.ENDC}")
        reveal_answer_details(item, show_examples)
        prog_item['weight'] = min(MAX_WEIGHT, prog_item['weight'] + PENALTY_SKIP)
        prog_item['streak'] = 0
        prog_item['attempts'] += 1 # Skipping counts as an attempt
        display_item_metadata(prog_item, orig_weight)
        return "skipped"
    if inpt.lower() == "-h":
        print(f"{bcolors.WARNING}Hint: {hint[0]}{bcolors.ENDC}")
        prog_item['weight'] = min(MAX_WEIGHT, prog_item['weight'] + PENALTY_HINT)
        # Re-prompt for answer after hint
        start_time_after_hint = time.time()
        inpt = input(f" [ {icon_warning} ] ").strip()
        end_time_after_hint = time.time()
        elapsed_time += (end_time_after_hint - start_time_after_hint)

    # --- Update time stats (always) ---
    prog_item['attempts'] += 1
    prog_item['total_time'] += elapsed_time

    # --- Check the answer ---
    if check_answer(inpt, answer):
        print(f"{icon_correct} {bcolors.OKGREEN}Correct!{bcolors.ENDC} (⏱ {elapsed_time:.2f}s)")
        prog_item['correct'] += 1
        prog_item['streak'] += 1
        
        # Apply rewards
        reward = (REWARD_CORRECT + (REWARD_STREAK * prog_item['streak']))
        if prog_item['avg_time'] > 0 and elapsed_time < prog_item['avg_time']:
            reward += REWARD_TIME

        prog_item['weight'] = max(MIN_WEIGHT, prog_item['weight'] - reward)
        result = "correct"
        
        # Show details on correct, per user request
        reveal_answer_details(item, show_examples)

    else:
        print(f"{icon_incorrect} {bcolors.FAIL}Incorrect.{bcolors.ENDC} (⏱ {elapsed_time:.2f}s)")
        reveal_answer_details(item, show_examples) # Show full answer on incorrect
        prog_item['streak'] = 0
        prog_item['weight'] = min(MAX_WEIGHT, prog_item['weight'] + PENALTY_INCORRECT)
        result = "incorrect"

    # Update avg_time *after* processing
    prog_item['avg_time'] = prog_item['total_time'] / prog_item['attempts']
    
    # Display the metadata for this specific item
    display_item_metadata(prog_item, orig_weight)
    press_enter_continue()

    return result

# ==========================================
# --------- Statistics Functions -----------
# ==========================================

def get_session_metadata(progress: List[Dict[str, Any]]) -> Tuple[float, float]:
    """
    Calculates the total (overall) proficiency and total time spent.
    (Adapted from hsk-vocab.py)
    """
    if not progress:
        return 0.0, 0.0
        
    total_weight = sum(p['weight'] for p in progress)
    total_time = sum(p['total_time'] for p in progress)

    avg_weight = total_weight / len(progress)
    weight_range = MAX_WEIGHT - MIN_WEIGHT

    normalized_avg_difficulty = (avg_weight - MIN_WEIGHT) / weight_range
    proficiency_percent = (1.0 - normalized_avg_difficulty) * 100.0
    proficiency_percent = max(0.0, min(100.0, proficiency_percent))
    
    return proficiency_percent, total_time

def display_session_summary(
    progress: List[Dict[str, Any]],
    session_correct: int,
    session_attempts: int,
    time_change_minutes: float,
    start_proficiency: float):
    """
    Displays a final summary of the session and overall progress.
    (Adapted from hsk-vocab.py)
    """
    
    session_accuracy = (session_correct / session_attempts * 100) if session_attempts > 0 else 0
    end_proficiency, end_total_time = get_session_metadata(progress)
    proficiency_change = end_proficiency - start_proficiency
    
    total_words = len(progress)
    words_seen = sum(1 for p in progress if p['attempts'] > 0)
    
    overall_total_correct = sum(p['correct'] for p in progress)
    overall_total_attempts = sum(p['attempts'] for p in progress)
    overall_accuracy = (overall_total_correct / overall_total_attempts * 100) if overall_total_attempts > 0 else 0
    
    mastery_threshold = MIN_WEIGHT + (MAX_WEIGHT - MIN_WEIGHT) * 0.05
    words_mastered = sum(1 for p in progress if p['weight'] <= mastery_threshold)
    
    clear_terminal()
    print()
    print(f"╔══ {bcolors.BOLD}Session Summary{bcolors.ENDC} ════════════════════")
    print(f"║ {icon_time} Time:        +{time_change_minutes:.2f} minutes")
    print(f"║ {icon_accuracy} Accuracy:     {session_accuracy:.1f}% ({session_correct} / {session_attempts})")
    print(f"║ {icon_proficiency} Change:      {'+' if proficiency_change > 0 else ''}{proficiency_change:.2f}%")
    print("╚" + "═" * 41)
    
    print()
    
    print(f"╔══ {bcolors.BOLD}Overall Progress (zi.json){bcolors.ENDC} ═══════════")
    print(f"║ {icon_proficiency} Proficiency:  {end_proficiency:.1f}%")
    print(f"║ {icon_accuracy} Accuracy:     {overall_accuracy:.1f}% ({overall_total_correct}/{overall_total_attempts})")
    print(f"║ {icon_seen} Seen:         {words_seen} / {total_words} words")
    print(f"║ {icon_mastery} Mastered:     {words_mastered} / {total_words} words")
    print(f"║ {icon_time} Total Time:   {end_total_time / 3600:.2f} hours")
    print("╚" + "═" * 41)
    print()
    input(f"{bcolors.OKCYAN}Press Enter To Return to Menu...{bcolors.ENDC}")

# ==========================================
# --------- Quiz Session Runner ------------
# ==========================================

def run_quiz_session(data: List[Dict[str, Any]], progress: List[Dict[str, Any]]):
    """
    The main loop for a single quiz session.
    (This is the logic from hsk-vocab.py's main())
    """
    global g_in_order_index
    g_in_order_index = 0 # Reset for sequential mode
    
    if not data or not progress:
        print(f"{bcolors.FAIL}No data or progress found. Cannot start quiz.{bcolors.ENDC}")
        print(f"{bcolors.WARNING}Please add entries first.{bcolors.ENDC}")
        time.sleep(2)
        return

    clear_terminal()
    
    session_correct = 0
    session_attempts = 0

    start_proficiency, start_total_time = get_session_metadata(progress)

    try:
        while True:
            print(f"{bcolors.HEADER}--- Starting Quiz ---{bcolors.ENDC}")
            print(f"{bcolors.OKCYAN}Type '-s' to skip, '-h' for hint, '-q' to quit.{bcolors.ENDC}")
            # Find the data index (0 to len-1)
            index = get_next_index(len(data), progress)
            
            # Get the corresponding items
            item_data = data[index]
            # Note: progress is already synced and in the same order as data
            item_progress = progress[index] 

            print("\n" + "-" * 30)
            result = run_quiz_for_item(item_data, item_progress, g_show_examples, index, len(data))

            if result == "correct":
                session_correct += 1
                session_attempts += 1
            elif result == "incorrect" or result == "skipped":
                session_attempts += 1
            elif result == "quit":
                break  # User quit

    except KeyboardInterrupt:
        print(f"\n{bcolors.WARNING}Session interrupted. Saving progress...{bcolors.ENDC}")
    finally:
        # Always save progress on exit
        save_data(progress, PROGRESS_FILE_PATH)
        
        end_proficiency, end_total_time = get_session_metadata(progress)
        time_change_minutes = (end_total_time - start_total_time) / 60.0

        display_session_summary(
            progress=progress,
            session_correct=session_correct,
            session_attempts=session_attempts,
            time_change_minutes=time_change_minutes,
            start_proficiency=start_proficiency
        )
        exit(0)


# ==========================================
# ----------------- MAIN -------------------
# ==========================================
def main():
    """
    Main application loop. Shows menu, handles routing.
    (Adapted from original zi.py)
    """
    global g_random_mode, g_show_examples
    
    # Load data and sync progress at the very start
    data = load_data(DATA_FILE_PATH)
    progress = load_and_sync_progress(data)

    while True:
        # Refresh data and progress in case an item was added
        # This check ensures new items are picked up by the menu
        if len(data) != len(progress):
             data = load_data(DATA_FILE_PATH)
             progress = load_and_sync_progress(data)
             
        clear_terminal()
        print(f"\n{bcolors.HEADER}{bcolors.BOLD}--- 汉字 (Hànzì) Quiz Main Menu ---{bcolors.ENDC}")
        print(f"Total entries: {bcolors.BOLD}{len(data)}{bcolors.ENDC}")
        
        # Display current options
        print("\n--- Options ---")
        rand_status = f"{bcolors.OKGREEN}ON{bcolors.ENDC}" if g_random_mode else f"{bcolors.FAIL}OFF{bcolors.ENDC}"
        ex_status = f"{bcolors.OKGREEN}ON{bcolors.ENDC}" if g_show_examples else f"{bcolors.FAIL}OFF{bcolors.ENDC}"
        print(f"  [1] Random Order  ({rand_status})")
        print(f"  [2] Show Examples ({ex_status})")

        # Display main actions
        print("\n--- Actions ---")
        print(f"  [{bcolors.OKGREEN}S{bcolors.ENDC}] Start Quiz")
        print(f"  [{bcolors.OKBLUE}A{bcolors.ENDC}] Add New Entry")
        print(f"  [{bcolors.FAIL}Q{bcolors.ENDC}] Quit")

        choice = input(f"\n{bcolors.BOLD}Enter your choice (1, 2, S, A, Q): {bcolors.ENDC}").strip().lower()

        if choice == 'q':
            print(f"\n{bcolors.OKCYAN}再见! (Zàijiàn!){bcolors.ENDC}")
            break
        elif choice == 's':
            run_quiz_session(data, progress)
        elif choice == 'a':
            clear_terminal()
            # Pass the data list, get modified list back
            data = add_new_entry(data)
            # After adding, force a re-load and re-sync
            progress = load_and_sync_progress(data)
        elif choice == '1':
            g_random_mode = not g_random_mode
            print(f"{bcolors.WARNING}Random Order is now {'ON' if g_random_mode else 'OFF'}{bcolors.ENDC}")
            time.sleep(1)
        elif choice == '2':
            g_show_examples = not g_show_examples
            print(f"{bcolors.WARNING}Show Examples is now {'ON' if g_show_examples else 'OFF'}{bcolors.ENDC}")
            time.sleep(1)
        else:
            print(f"{bcolors.FAIL}Invalid choice. Please try again.{bcolors.ENDC}")
            time.sleep(1)

# --- Run the application ---
if __name__ == "__main__":
    main()
